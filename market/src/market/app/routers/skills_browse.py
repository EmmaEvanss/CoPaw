# -*- coding: utf-8 -*-
"""用户市场浏览 API 和我的技能 API."""
import asyncio
import io
import json
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Body,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
)

from ...marketplace.fs import get_user_skills_dir
from ...marketplace.schemas import (
    BatchOperationRequest,
    BatchOperationResponse,
    FileContentResponse,
    FileTreeNode,
    MarketSkillDetail,
    MarketSkillResponse,
    MySkillItem,
    OperationResponse,
    UploadSkillResponse,
)
from ..deps import require_source_id

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_ZIP_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
}


async def _read_validated_zip_upload(file: UploadFile) -> bytes:
    """Validate and read uploaded zip file."""
    if file.content_type and file.content_type not in _ALLOWED_ZIP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Expected a zip file, "
                f"got content-type: {file.content_type}"
            ),
        )

    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File too large ({len(data) // (1024 * 1024)} MB). "
                f"Maximum is {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
            ),
        )
    return data


def _decode_zip_filename(filename: str, info: zipfile.ZipInfo) -> str:
    """Decode zip filename, handling GBK encoding from Windows.

    ZIP file name encoding rules:
    - If flag_bits & 0x800: UTF-8 encoded (Python decodes correctly)
    - Otherwise: platform-specific encoding (often GBK on Chinese Windows)

    Python's zipfile module decodes non-UTF-8 filenames using cp437 by default,
    which causes Chinese characters to become garbled. We need to:
    1. Check if UTF-8 flag is set (already correct)
    2. Otherwise, reverse cp437 decoding and try GBK/UTF-8
    """
    # Check if UTF-8 flag is set (bit 11)
    if info.flag_bits & 0x800:
        return filename

    # Try to recover from cp437 mis-decoding
    try:
        raw = filename.encode("cp437")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return filename

    # Try GBK first (common on Chinese Windows)
    try:
        decoded = raw.decode("gbk")
        # Validate the result is printable
        if decoded.isprintable() or all(
            c.isprintable() or c in "\n\r\t" for c in decoded
        ):
            return decoded
    except UnicodeDecodeError:
        pass

    # Try UTF-8
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    return filename


def _extract_zip_skills(data: bytes) -> tuple[Path, list[tuple[Path, str]]]:
    """Extract and validate a skill zip.

    Returns ``(tmp_dir, found_skills)`` where each skill is ``(skill_dir, skill_name)``.
    """
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValueError("Uploaded file is not a valid zip archive")

    tmp_dir = Path(tempfile.mkdtemp(prefix="copaw_myskill_upload_"))
    root_path = tmp_dir.resolve()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        # Check total size
        total = sum(info.file_size for info in zf.infolist())
        if total > 200 * 1024 * 1024:  # 200MB limit
            raise ValueError("Uncompressed zip exceeds 200MB limit")

        # Security check for path traversal (use decoded filename)
        for info in zf.infolist():
            decoded_name = _decode_zip_filename(info.filename, info)
            target = (tmp_dir / decoded_name).resolve()
            if not target.is_relative_to(root_path):
                raise ValueError(f"Unsafe path in zip: {info.filename}")

        # Extract files with corrected encoding for Chinese filenames
        for info in zf.infolist():
            # Decode filename correctly
            decoded_name = _decode_zip_filename(info.filename, info)
            target = tmp_dir / decoded_name

            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                # Use ZipInfo object to read data, avoiding encoding issues with filename
                target.write_bytes(zf.read(info))

    # Find skill directories
    real_entries = [
        path
        for path in tmp_dir.iterdir()
        if not path.name.startswith(".") and not path.name.startswith("_")
    ]

    # Handle single skill at root
    extract_root = (
        real_entries[0]
        if len(real_entries) == 1 and real_entries[0].is_dir()
        else tmp_dir
    )

    if (extract_root / "SKILL.md").exists():
        skill_name = _resolve_skill_name(extract_root)
        found = [(extract_root, skill_name)]
    else:
        found = [
            (path, _resolve_skill_name(path))
            for path in sorted(extract_root.iterdir())
            if not path.name.startswith(".")
            and not path.name.startswith("_")
            and path.is_dir()
            and (path / "SKILL.md").exists()
        ]

    if not found:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValueError(
            "No valid skills found in uploaded zip (missing SKILL.md)",
        )

    return tmp_dir, found


def _resolve_skill_name(skill_dir: Path) -> str:
    """Resolve skill name from SKILL.md frontmatter or directory name."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return skill_dir.name

    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception:
        return skill_dir.name

    if not content.startswith("---"):
        return skill_dir.name

    # Parse YAML frontmatter
    for line in content.split("\n")[1:]:
        if line.startswith("---"):
            break
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
            if name:
                return name

    return skill_dir.name


def _import_skill_dir(
    skill_dir: Path,
    skills_root: Path,
    skill_name: str,
    overwrite: bool,
) -> bool:
    """Import a skill directory to the user skills folder."""
    target_dir = skills_root / skill_name
    if target_dir.exists() and not overwrite:
        return False

    if target_dir.exists():
        shutil.rmtree(target_dir)

    shutil.copytree(skill_dir, target_dir)
    return True


def _import_skill_from_zip(
    skills_dir: Path,
    data: bytes,
    user_id: str,
    user_name: str,
    bbk_id: str,
    overwrite: bool = False,
    target_name: str = "",
    category_id: int | None = None,
) -> dict[str, Any]:
    """Import skill from zip data to user skills directory."""
    imported: list[str] = []
    conflicts: list[dict[str, str]] = []
    tmp_dir: Path | None = None
    parsed_name: str | None = None
    parsed_description: str | None = None

    try:
        tmp_dir, found_skills = _extract_zip_skills(data)

        existing_names = (
            {p.name for p in skills_dir.iterdir() if p.is_dir()}
            if skills_dir.exists()
            else set()
        )

        for skill_dir, skill_name in found_skills:
            # Apply target_name if single skill
            if target_name and len(found_skills) == 1:
                skill_name = target_name.strip()

            if skill_name in existing_names and not overwrite:
                conflicts.append(
                    {
                        "reason": "already_exists",
                        "skill_name": skill_name,
                        "suggested_name": f"{skill_name}_1",
                    },
                )
                continue

            if _import_skill_dir(skill_dir, skills_dir, skill_name, overwrite):
                # Update skill.json with metadata
                skill_json_path = skills_dir / skill_name / "skill.json"
                skill_data: dict[str, Any] = {}
                if skill_json_path.exists():
                    try:
                        skill_data = json.loads(
                            skill_json_path.read_text(encoding="utf-8"),
                        )
                    except (json.JSONDecodeError, OSError):
                        pass

                # Ensure name and description are set
                skill_data["name"] = skill_data.get("name") or skill_name
                skill_data.setdefault("description", "")
                skill_data["source"] = "customized"
                skill_data["creator_id"] = user_id
                skill_data["creator_name"] = user_name
                skill_data["bbk_id"] = bbk_id
                if category_id is not None:
                    skill_data["category_id"] = category_id

                skill_json_path.write_text(
                    json.dumps(skill_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                imported.append(skill_name)

                # Capture parsed name and description from first skill
                if parsed_name is None:
                    parsed_name = skill_data.get("name")
                    parsed_description = skill_data.get("description")

    except zipfile.BadZipFile as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid zip file: {e}",
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    finally:
        # Clean up temp directory
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

    result = {
        "imported": imported,
        "count": len(imported),
        "name": parsed_name,
        "description": parsed_description,
    }
    if conflicts:
        result["conflicts"] = conflicts
    return result


@router.get("/market/skills", response_model=list[MarketSkillResponse])
async def list_skills(
    request: Request,
    category_id: Optional[int] = None,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_bbk_id: Optional[str] = Header(default=None, alias="X-Bbk-Id"),
):
    """浏览市场技能列表（按 source_id + bbk_id 过滤）."""
    source_id = require_source_id(x_source_id)
    user_bbk_id = x_bbk_id or "100"
    svc = request.app.state.marketplace
    return await svc.list_skills(
        source_id,
        user_bbk_id,
        category_id=category_id,
    )


@router.get("/market/skills/mine", response_model=list[MySkillItem])
async def get_my_skills(
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """我创建的技能列表."""
    source_id = require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )
    svc = request.app.state.marketplace
    all_skills = await svc.get_my_skills(source_id, x_user_id, agent_id)
    return [s for s in all_skills if not s.is_received]


@router.get("/market/skills/received", response_model=list[MySkillItem])
async def get_received_skills(
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """我接收的技能列表."""
    source_id = require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )
    svc = request.app.state.marketplace
    all_skills = await svc.get_my_skills(source_id, x_user_id, agent_id)
    return [s for s in all_skills if s.is_received]


@router.get("/market/skills/{item_id}", response_model=MarketSkillDetail)
async def get_skill_detail(
    item_id: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_bbk_id: Optional[str] = Header(default=None, alias="X-Bbk-Id"),
):
    """预览技能详情."""
    source_id = require_source_id(x_source_id)
    user_bbk_id = x_bbk_id or "100"
    svc = request.app.state.marketplace
    detail = await svc.get_skill_detail(source_id, item_id, user_bbk_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return detail


@router.post("/market/skills/upload", response_model=UploadSkillResponse)
async def upload_skill_to_workspace(
    request: Request,
    file: UploadFile = File(..., description="Skill zip file to upload"),
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
    x_bbk_id: Optional[str] = Header(default=None, alias="X-Bbk-Id"),
    enable: bool = True,
    overwrite: bool = False,
    target_name: str = "",
    category_id: Optional[int] = None,
):
    """上传技能到工作区，记录 user_id, bbk_id, user_name。可选指定分类。"""
    source_id = require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )

    svc = request.app.state.marketplace
    swe_root = svc.swe_root
    user_name = x_user_name or x_user_id
    bbk_id = x_bbk_id or "100"
    agent_id = "default"

    # Get user skills directory
    skills_dir = get_user_skills_dir(swe_root, x_user_id, agent_id)
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Read and validate zip
    data = await _read_validated_zip_upload(file)

    # Import skill
    result = await asyncio.to_thread(
        _import_skill_from_zip,
        skills_dir,
        data,
        x_user_id,
        user_name,
        bbk_id,
        overwrite=overwrite,
        target_name=target_name,
        category_id=category_id,
    )

    # Log upload operation
    if svc.db.is_connected and result.get("imported"):
        try:
            await svc.db.execute(
                """
                INSERT INTO swe_user_item_operation_logs
                    (source_id, operator_id, operator_name, operation,
                     item_type, item_id, item_name,
                     target_user_id, target_user_name, target_bbk_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_id,
                    x_user_id,
                    user_name,
                    "upload",
                    "skill",
                    "",
                    ",".join(result["imported"]),
                    x_user_id,
                    user_name,
                    bbk_id,
                ),
            )
        except Exception as e:
            logger.warning("Failed to log upload operation: %s", e)

    result["enabled"] = enable
    return result


@router.get(
    "/market/skills/mine/{skill_name}/files",
    response_model=list[FileTreeNode],
)
async def list_skill_files(
    skill_name: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """获取技能文件树."""
    require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )
    svc = request.app.state.marketplace
    return svc.list_skill_files(x_user_id, skill_name, agent_id)


@router.get(
    "/market/skills/mine/{skill_name}/files/{file_path:path}",
    response_model=FileContentResponse,
)
async def read_skill_file(
    skill_name: str,
    file_path: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """读取技能文件内容."""
    require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )
    svc = request.app.state.marketplace
    content, file_type = svc.read_skill_file(
        x_user_id,
        skill_name,
        file_path,
        agent_id,
    )
    if content is None:
        if file_type == "binary":
            raise HTTPException(
                status_code=400,
                detail="Binary file not supported for preview",
            )
        raise HTTPException(status_code=404, detail="File not found")
    return FileContentResponse(content=content, file_type=file_type)


@router.put(
    "/market/skills/mine/{skill_name}/files/{file_path:path}",
    response_model=OperationResponse,
)
async def save_skill_file(
    skill_name: str,
    file_path: str,
    request: Request,
    content: str = Body(..., embed=True),
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
    agent_id: str = "default",
):
    """保存技能文件内容（仅我创建的技能支持）."""
    source_id = require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )

    svc = request.app.state.marketplace
    skills = await svc.get_my_skills(source_id, x_user_id, agent_id)
    skill = next((s for s in skills if s.skill_name == skill_name), None)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    if skill.is_received:
        raise HTTPException(
            status_code=403,
            detail="Only created skills can be edited",
        )

    ok = svc.save_skill_file(
        x_user_id,
        skill_name,
        file_path,
        content,
        agent_id,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save file")
    return OperationResponse(success=True)


@router.delete(
    "/market/skills/mine/{skill_name}",
    response_model=OperationResponse,
)
async def delete_my_skill(
    skill_name: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """删除技能."""
    require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )

    svc = request.app.state.marketplace
    ok = svc.delete_skill(x_user_id, skill_name, agent_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Skill not found or delete failed",
        )
    return OperationResponse(success=True)


@router.post(
    "/market/skills/mine/{skill_name}/enable",
    response_model=OperationResponse,
)
async def enable_my_skill(
    skill_name: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """启用技能（含安全扫描）."""
    require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )
    svc = request.app.state.marketplace
    result = await svc.enable_skill(x_user_id, skill_name, agent_id)
    if not result.get("success"):
        if result.get("reason") == "security_scan_failed":
            raise HTTPException(
                status_code=422,
                detail=result,
            )
        raise HTTPException(
            status_code=404,
            detail=result.get("reason", "Skill not found"),
        )
    return OperationResponse(success=True)


@router.post(
    "/market/skills/mine/{skill_name}/disable",
    response_model=OperationResponse,
)
async def disable_my_skill(
    skill_name: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """禁用技能."""
    require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )
    svc = request.app.state.marketplace
    result = await svc.disable_skill(x_user_id, skill_name, agent_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=404,
            detail="Skill not found",
        )
    return OperationResponse(success=True)


@router.post(
    "/market/skills/mine/batch-delete",
    response_model=BatchOperationResponse,
)
async def batch_delete_my_skills(
    body: BatchOperationRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """批量删除技能."""
    require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )
    svc = request.app.state.marketplace
    results = await svc.batch_delete_skills(x_user_id, body.skills, agent_id)
    success_count = sum(1 for r in results.values() if r.get("success"))
    return BatchOperationResponse(
        results=results,
        success_count=success_count,
        failed_count=len(body.skills) - success_count,
    )


@router.post(
    "/market/skills/mine/batch-enable",
    response_model=BatchOperationResponse,
)
async def batch_enable_my_skills(
    body: BatchOperationRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """批量启用技能."""
    require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )
    svc = request.app.state.marketplace
    results = await svc.batch_enable_skills(x_user_id, body.skills, agent_id)
    success_count = sum(1 for r in results.values() if r.get("success"))
    return BatchOperationResponse(
        results=results,
        success_count=success_count,
        failed_count=len(body.skills) - success_count,
    )


@router.post(
    "/market/skills/mine/batch-disable",
    response_model=BatchOperationResponse,
)
async def batch_disable_my_skills(
    body: BatchOperationRequest,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """批量禁用技能."""
    require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )
    svc = request.app.state.marketplace
    results = await svc.batch_disable_skills(x_user_id, body.skills, agent_id)
    success_count = sum(1 for r in results.values() if r.get("success"))
    return BatchOperationResponse(
        results=results,
        success_count=success_count,
        failed_count=len(body.skills) - success_count,
    )
