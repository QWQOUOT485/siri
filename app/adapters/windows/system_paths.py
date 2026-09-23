"""Trusted Windows system document paths used by fixed catalog entries."""

from __future__ import annotations

import ctypes
import ntpath
import re
import sys


ALLOWED_MSC = frozenset({"devmgmt.msc", "services.msc", "eventvwr.msc", "diskmgmt.msc", "taskschd.msc"})


def windows_system_directory() -> str | None:
    """Ask Windows for its system directory; never derive it from request data."""

    if sys.platform != "win32":
        return None
    buffer = ctypes.create_unicode_buffer(32768)
    try:
        length = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
    except (AttributeError, OSError):
        return None
    if not 0 < length < len(buffer):
        return None
    path = buffer.value
    if not re.fullmatch(r"[A-Za-z]:[\\/].+", path) or path.startswith(("\\\\", "//")):
        return None
    if ".." in path.replace("/", "\\").split("\\") or ntpath.basename(path).casefold() != "system32":
        return None
    return ntpath.normpath(path)


def trusted_msc_path(name: str) -> str | None:
    if name.casefold() not in ALLOWED_MSC or ntpath.basename(name) != name:
        return None
    directory = windows_system_directory()
    return ntpath.join(directory, name) if directory else None
