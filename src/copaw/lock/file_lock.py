# -*- coding: utf-8 -*-
"""File lock implementation for NAS storage using portalocker."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import portalocker
from portalocker.exceptions import AlreadyLocked

logger = logging.getLogger(__name__)


def _ensure_file_exists(path: Path) -> None:
    """Ensure file exists, create if not."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


@asynccontextmanager
async def file_lock(path: Path, mode: str = "r") -> AsyncGenerator:
    """File lock context manager (async wrapper).

    Args:
        path: File path to lock
        mode: 'r' for shared read lock, 'w' for exclusive write lock
    """
    lock_mode = portalocker.LOCK_SH if mode == "r" else portalocker.LOCK_EX
    lock_mode |= portalocker.LOCK_NB  # Non-blocking

    # Ensure lock file exists (needed for both read and write modes)
    await asyncio.to_thread(_ensure_file_exists, path)

    fd = None
    locked = False
    try:
        fd = await asyncio.to_thread(open, path, "r+")
        await asyncio.to_thread(portalocker.lock, fd, lock_mode)
        locked = True
        yield fd
    except AlreadyLocked:
        if fd:
            await asyncio.to_thread(fd.close)
        raise
    finally:
        if fd and locked:
            await asyncio.to_thread(portalocker.unlock, fd)
            await asyncio.to_thread(fd.close)


async def read_json_locked(path: Path) -> dict:
    """Read JSON file with shared lock.

    Uses the same .lock file as write_json_locked for coordination,
    ensuring read-write mutual exclusion while allowing concurrent reads.
    """
    import json

    # Use the same lock file as write_json_locked for coordination
    lock_path = path.with_suffix(".lock")
    async with file_lock(lock_path, mode="r"):
        # Now safe to read the actual file
        if not path.exists():
            return {}
        content = await asyncio.to_thread(path.read_text)
        return json.loads(content) if content else {}


async def write_json_locked(path: Path, data: dict) -> None:
    """Write JSON file with exclusive lock (atomic).

    Uses a separate lock file to avoid the inode replacement problem:
    when replacing a file with tmp_path.replace(path), the lock on the
    original file descriptor stays on the old inode, leaving the new file
    unprotected. By using a stable lock file, coordination is maintained.
    """
    import json

    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    # Use a separate lock file that remains stable across replacements
    lock_path = path.with_suffix(".lock")
    async with file_lock(lock_path, mode="w"):
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json_str, encoding="utf-8")
        tmp_path.replace(path)
