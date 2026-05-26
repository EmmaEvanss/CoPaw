# -*- coding: utf-8 -*-
"""内部 asset 文件上传接口测试。"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from swe.app.routers import internal as internal_module
from swe.app.routers.internal import router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _set_working_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        internal_module,
        "WORKING_DIR",
        tmp_path,
        raising=False,
    )


def _enable_internal_token(monkeypatch) -> dict[str, str]:
    monkeypatch.setattr(
        internal_module,
        "_INTERNAL_TOKEN",
        "secret-token",
        raising=False,
    )
    return {"X-Internal-Token": "Bearer secret-token"}


def _post_upload(
    client: TestClient,
    headers: dict[str, str],
    file_name: str,
    content: bytes,
):
    if file_name:
        return client.post(
            "/internal/assets/upload",
            files={"file": (file_name, content, "application/octet-stream")},
            headers=headers,
        )

    boundary = "empty-filename-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename=""\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    body += content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request_headers = {
        **headers,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    return client.post(
        "/internal/assets/upload",
        content=body,
        headers=request_headers,
    )


def test_internal_asset_upload_saves_binary_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _set_working_dir(monkeypatch, tmp_path)
    headers = _enable_internal_token(monkeypatch)
    client = _build_client()
    content = b"\xff\x00raw-bytes"

    response = client.post(
        "/internal/assets/upload",
        files={
            "file": (
                "sample.bin",
                content,
                "application/octet-stream",
            ),
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "file_name": "sample.bin",
        "asset_path": "asset/sample.bin",
        "size": len(content),
    }
    assert (tmp_path / "asset" / "sample.bin").read_bytes() == content


def test_internal_asset_upload_rejects_invalid_token_without_writing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _set_working_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(
        internal_module,
        "_INTERNAL_TOKEN",
        "secret-token",
        raising=False,
    )
    client = _build_client()

    response = client.post(
        "/internal/assets/upload",
        files={
            "file": ("blocked.bin", b"blocked", "application/octet-stream"),
        },
        headers={"X-Internal-Token": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"
    assert not (tmp_path / "asset" / "blocked.bin").exists()


@pytest.mark.parametrize(
    "file_name",
    [
        "../escape.bin",
        "/tmp/escape.bin",
        "nested/escape.bin",
        "nested\\escape.bin",
        "",
        ".",
        "..",
    ],
)
def test_internal_asset_upload_rejects_invalid_file_names(
    monkeypatch,
    tmp_path: Path,
    file_name: str,
) -> None:
    _set_working_dir(monkeypatch, tmp_path)
    headers = _enable_internal_token(monkeypatch)
    client = _build_client()
    outside_file = tmp_path.parent / "escape.bin"
    outside_file.write_bytes(b"original")

    response = _post_upload(client, headers, file_name, b"changed")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file_name"
    assert outside_file.read_bytes() == b"original"


def test_internal_asset_upload_overwrites_matching_file_name(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _set_working_dir(monkeypatch, tmp_path)
    headers = _enable_internal_token(monkeypatch)
    asset_dir = tmp_path / "asset"
    asset_dir.mkdir(parents=True)
    target = asset_dir / "replace.bin"
    target.write_bytes(b"old")
    client = _build_client()

    response = client.post(
        "/internal/assets/upload",
        files={
            "file": (
                "replace.bin",
                b"new-content",
                "application/octet-stream",
            ),
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["size"] == len(b"new-content")
    assert target.read_bytes() == b"new-content"
