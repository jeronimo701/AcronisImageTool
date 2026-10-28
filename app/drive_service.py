from __future__ import annotations

from ctypes import byref, c_wchar_p, create_unicode_buffer, windll
from ctypes.wintypes import DWORD, LPCWSTR, ULARGE_INTEGER
from pathlib import Path

from .config import IGNORED_DIR_NAMES
from .models import DriveInfo

DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3


def list_target_drives() -> list[DriveInfo]:
    drives: list[DriveInfo] = []
    bitmask = windll.kernel32.GetLogicalDrives()
    for index in range(26):
        if not (bitmask & (1 << index)):
            continue

        letter = chr(ord("A") + index)
        root_text = f"{letter}:\\"
        drive_type = windll.kernel32.GetDriveTypeW(c_wchar_p(root_text))
        if drive_type not in {DRIVE_REMOVABLE, DRIVE_FIXED}:
            continue
        if letter.upper() == "C":
            continue

        label = _get_volume_label(root_text)
        free_bytes, total_bytes = _get_space(root_text)
        root = Path(root_text)
        is_ventoy = (root / "ventoy").is_dir() or (root / "ventoy.json").exists()
        if root.name in IGNORED_DIR_NAMES:
            continue

        drives.append(
            DriveInfo(
                root=root,
                label=label,
                free_bytes=free_bytes,
                total_bytes=total_bytes,
                drive_type="Removable" if drive_type == DRIVE_REMOVABLE else "Fixed",
                is_ventoy=is_ventoy,
            )
        )

    drives.sort(key=lambda item: (not item.is_ventoy, item.root.drive))
    return drives


def _get_volume_label(root_text: str) -> str:
    volume_name_buffer = create_unicode_buffer(1024)
    file_system_name_buffer = create_unicode_buffer(1024)
    serial_number = DWORD()
    max_component_len = DWORD()
    file_system_flags = DWORD()

    success = windll.kernel32.GetVolumeInformationW(
        LPCWSTR(root_text),
        volume_name_buffer,
        1024,
        byref(serial_number),
        byref(max_component_len),
        byref(file_system_flags),
        file_system_name_buffer,
        1024,
    )
    if not success:
        return ""
    return volume_name_buffer.value or ""


def _get_space(root_text: str) -> tuple[int, int]:
    free_bytes = ULARGE_INTEGER(0)
    total_bytes = ULARGE_INTEGER(0)
    total_free_bytes = ULARGE_INTEGER(0)
    success = windll.kernel32.GetDiskFreeSpaceExW(
        LPCWSTR(root_text),
        byref(free_bytes),
        byref(total_bytes),
        byref(total_free_bytes),
    )
    if not success:
        return 0, 0
    return free_bytes.value, total_bytes.value
