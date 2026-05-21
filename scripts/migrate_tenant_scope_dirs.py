#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把旧的裸租户目录迁移到 tenant/source 运行时 scope 目录。

该脚本用于把历史目录：
    ~/.swe/<tenant-id>/
    ~/.swe.secret/<tenant-id>/

迁移为当前运行时使用的 canonical scope 目录：
    ~/.swe/<encoded-tenant>.<encoded-source>/
    ~/.swe.secret/<encoded-tenant>.<encoded-source>/

脚本只迁移显式指定的 tenant，避免把模板目录或仍需保留的无 source
目录误判为历史数据。
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

# 允许直接通过 ``python scripts/...`` 运行时导入项目源码。
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# pylint: disable=wrong-import-position
from swe.config.context import encode_scope_id, is_valid_identity_value
from swe.constant import SECRET_DIR, WORKING_DIR

# pylint: enable=wrong-import-position

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MigrationResult:
    """记录一次目录迁移的执行结果。"""

    scope_id: str
    old_working_dir: Path
    new_working_dir: Path
    old_secret_dir: Path
    new_secret_dir: Path
    moved_working_dir: bool
    moved_secret_dir: bool
    rewritten_json_files: tuple[Path, ...]


def setup_logging(verbose: bool = False) -> None:
    """初始化脚本日志输出。"""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )


def _validate_identity(name: str, value: str) -> None:
    """校验 tenant/source 标识，避免生成不安全目录名。"""
    if not is_valid_identity_value(value):
        raise ValueError(f"Invalid {name}: {value!r}")


def _assert_target_absent(old_dir: Path, new_dir: Path) -> None:
    """在迁移前确认目标目录不会覆盖现有状态。"""
    if old_dir.exists() and new_dir.exists():
        raise FileExistsError(
            f"Target already exists, refusing to overwrite: {new_dir}",
        )


def parse_tenant_ids(raw_value: str) -> tuple[str, ...]:
    """解析逗号分隔的批量 tenant 输入。

    Args:
        raw_value: 形如 ``tenant-a,tenant-b`` 的参数值。

    Returns:
        去除空白后的 tenant ID 元组。

    Raises:
        ValueError: 输入为空或包含空 tenant 时抛出。
    """
    tenant_ids = tuple(part.strip() for part in raw_value.split(","))
    if not tenant_ids or any(not tenant_id for tenant_id in tenant_ids):
        raise ValueError("Invalid tenant_ids: expected comma-separated IDs")
    return tenant_ids


def _rewrite_working_json_paths(
    working_dir: Path,
    old_dir: Path,
    new_dir: Path,
) -> tuple[Path, ...]:
    """重写工作目录内引用旧 tenant 根路径的 JSON 文件。

    历史配置中常见 `workspace_dir` 以绝对路径落盘。迁移目录后如果不一并
    改写，运行时虽然能找到新目录，但 agent 配置仍会继续指向旧路径。
    """
    rewritten: list[Path] = []
    old_prefix = str(old_dir)
    new_prefix = str(new_dir)
    for path in sorted(working_dir.rglob("*.json")):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning("跳过非 UTF-8 JSON 文件: %s", path)
            continue
        if old_prefix not in content:
            continue
        path.write_text(
            content.replace(old_prefix, new_prefix),
            encoding="utf-8",
        )
        rewritten.append(path)
    return tuple(rewritten)


def migrate_tenant_scope_dirs(
    *,
    tenant_id: str,
    source_id: str,
    working_dir: Path = WORKING_DIR,
    secret_dir: Path = SECRET_DIR,
    dry_run: bool = False,
) -> MigrationResult:
    """迁移指定 tenant 在指定 source 下的历史裸目录。

    Args:
        tenant_id: 需要迁移的逻辑租户标识。
        source_id: 目标运行时来源标识。
        working_dir: 工作目录根路径，默认使用项目配置的 `WORKING_DIR`。
        secret_dir: 密钥目录根路径，默认使用项目配置的 `SECRET_DIR`。
        dry_run: 为 True 时只计算迁移计划，不改动文件系统。

    Returns:
        本次迁移的执行结果。

    Raises:
        ValueError: tenant/source 标识非法时抛出。
        FileExistsError: 目标 scope 目录已存在且源目录也存在时抛出。
    """
    _validate_identity("tenant_id", tenant_id)
    _validate_identity("source_id", source_id)

    normalized_working_dir = Path(working_dir).expanduser().resolve()
    normalized_secret_dir = Path(secret_dir).expanduser().resolve()
    scope_id = encode_scope_id(tenant_id, source_id)

    old_working_dir = normalized_working_dir / tenant_id
    new_working_dir = normalized_working_dir / scope_id
    old_secret_dir = normalized_secret_dir / tenant_id
    new_secret_dir = normalized_secret_dir / scope_id

    _assert_target_absent(old_working_dir, new_working_dir)
    _assert_target_absent(old_secret_dir, new_secret_dir)

    moved_working_dir = old_working_dir.exists()
    moved_secret_dir = old_secret_dir.exists()

    if dry_run:
        return MigrationResult(
            scope_id=scope_id,
            old_working_dir=old_working_dir,
            new_working_dir=new_working_dir,
            old_secret_dir=old_secret_dir,
            new_secret_dir=new_secret_dir,
            moved_working_dir=moved_working_dir,
            moved_secret_dir=moved_secret_dir,
            rewritten_json_files=(),
        )

    if moved_working_dir:
        old_working_dir.rename(new_working_dir)
        logger.info(
            "已迁移工作目录: %s -> %s",
            old_working_dir,
            new_working_dir,
        )
        rewritten_json_files = _rewrite_working_json_paths(
            new_working_dir,
            old_working_dir,
            new_working_dir,
        )
    else:
        rewritten_json_files = ()
        logger.info("未找到工作目录，跳过: %s", old_working_dir)

    if moved_secret_dir:
        old_secret_dir.rename(new_secret_dir)
        logger.info("已迁移密钥目录: %s -> %s", old_secret_dir, new_secret_dir)
    else:
        logger.info("未找到密钥目录，跳过: %s", old_secret_dir)

    return MigrationResult(
        scope_id=scope_id,
        old_working_dir=old_working_dir,
        new_working_dir=new_working_dir,
        old_secret_dir=old_secret_dir,
        new_secret_dir=new_secret_dir,
        moved_working_dir=moved_working_dir,
        moved_secret_dir=moved_secret_dir,
        rewritten_json_files=rewritten_json_files,
    )


def migrate_tenant_scope_dirs_batch(
    *,
    tenant_ids: tuple[str, ...],
    source_id: str,
    working_dir: Path = WORKING_DIR,
    secret_dir: Path = SECRET_DIR,
    dry_run: bool = False,
) -> tuple[MigrationResult, ...]:
    """批量迁移多个 tenant，并在执行前完成整批预检查。"""
    if not tenant_ids:
        raise ValueError("tenant_ids must not be empty")

    normalized_working_dir = Path(working_dir).expanduser().resolve()
    normalized_secret_dir = Path(secret_dir).expanduser().resolve()

    # 先把整批都预演一遍，确保任何一个租户冲突时都不会产生半迁移状态。
    planned_results = tuple(
        migrate_tenant_scope_dirs(
            tenant_id=tenant_id,
            source_id=source_id,
            working_dir=normalized_working_dir,
            secret_dir=normalized_secret_dir,
            dry_run=True,
        )
        for tenant_id in tenant_ids
    )
    if dry_run:
        return planned_results

    return tuple(
        migrate_tenant_scope_dirs(
            tenant_id=tenant_id,
            source_id=source_id,
            working_dir=normalized_working_dir,
            secret_dir=normalized_secret_dir,
        )
        for tenant_id in tenant_ids
    )


def _format_plan(result: MigrationResult) -> str:
    """把迁移结果格式化为便于人工核对的文本。"""
    lines = [
        f"scope_id: {result.scope_id}",
        f"working: {result.old_working_dir} -> {result.new_working_dir}",
        f"secret : {result.old_secret_dir} -> {result.new_secret_dir}",
        f"move working dir: {result.moved_working_dir}",
        f"move secret dir : {result.moved_secret_dir}",
    ]
    if result.rewritten_json_files:
        lines.append("rewritten json files:")
        lines.extend(f"  - {path}" for path in result.rewritten_json_files)
    return "\n".join(lines)


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="把旧 tenant 目录迁移为 tenant/source scope 目录",
    )
    tenant_group = parser.add_mutually_exclusive_group(required=True)
    tenant_group.add_argument("--tenant-id", help="待迁移 tenant ID")
    tenant_group.add_argument(
        "--tenant-ids",
        help="逗号分隔的待迁移 tenant 列表，例如 tenant-a,tenant-b",
    )
    parser.add_argument("--source-id", required=True, help="目标 source ID")
    parser.add_argument(
        "--working-dir",
        type=Path,
        default=WORKING_DIR,
        help="工作目录根路径，默认读取 SWE_WORKING_DIR 或 ~/.swe",
    )
    parser.add_argument(
        "--secret-dir",
        type=Path,
        default=SECRET_DIR,
        help="密钥目录根路径，默认读取 SWE_SECRET_DIR 或 ~/.swe.secret",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只展示迁移计划，不修改文件系统",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="输出调试日志",
    )
    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
        if args.tenant_ids is not None:
            results = migrate_tenant_scope_dirs_batch(
                tenant_ids=parse_tenant_ids(args.tenant_ids),
                source_id=args.source_id,
                working_dir=args.working_dir,
                secret_dir=args.secret_dir,
                dry_run=args.dry_run,
            )
        else:
            results = (
                migrate_tenant_scope_dirs(
                    tenant_id=args.tenant_id,
                    source_id=args.source_id,
                    working_dir=args.working_dir,
                    secret_dir=args.secret_dir,
                    dry_run=args.dry_run,
                ),
            )
    except (ValueError, FileExistsError) as exc:
        logger.error("%s", exc)
        return 1

    print("\n\n".join(_format_plan(result) for result in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
