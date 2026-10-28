from __future__ import annotations

from ctypes import Structure, WinError, byref, windll
from ctypes.wintypes import DWORD, LPCWSTR
import re
import subprocess
from pathlib import Path

RESOURCETYPE_DISK = 0x00000001
NO_ERROR = 0
ERROR_SESSION_CREDENTIAL_CONFLICT = 1219
CONNECT_INTERACTIVE = 0x00000008


class NETRESOURCEW(Structure):
    _fields_ = [
        ("dwScope", DWORD),
        ("dwType", DWORD),
        ("dwDisplayType", DWORD),
        ("dwUsage", DWORD),
        ("lpLocalName", LPCWSTR),
        ("lpRemoteName", LPCWSTR),
        ("lpComment", LPCWSTR),
        ("lpProvider", LPCWSTR),
    ]


def ensure_connection(source_root: str, smb_share: str, username: str, password: str, anonymous: bool = False) -> None:
    if Path(source_root).exists():
        return

    resource = NETRESOURCEW()
    resource.dwType = RESOURCETYPE_DISK
    resource.lpRemoteName = smb_share

    result = windll.mpr.WNetAddConnection2W(
        byref(resource),
        None if anonymous else password,
        None if anonymous else username,
        CONNECT_INTERACTIVE,
    )
    if result == NO_ERROR:
        return
    if result == ERROR_SESSION_CREDENTIAL_CONFLICT:
        _drop_existing_server_connections(smb_share)
        result = windll.mpr.WNetAddConnection2W(
            byref(resource),
            None if anonymous else password,
            None if anonymous else username,
            CONNECT_INTERACTIVE,
        )
        if result == NO_ERROR:
            return
    if result not in {NO_ERROR, 85, 1202}:
        raise WinError(result)


def _drop_existing_server_connections(smb_share: str) -> None:
    server_prefix = _server_prefix_from_share(smb_share)
    completed = subprocess.run(
        ["net", "use"],
        capture_output=True,
        text=True,
        encoding="cp866",
        errors="replace",
        check=False,
    )
    candidates = set(re.findall(r"\\\\[^\s]+\\[^\s]+", completed.stdout, flags=re.IGNORECASE))
    candidates = {item for item in candidates if item.lower().startswith(server_prefix.lower())}
    candidates.add(smb_share)

    for remote in sorted(candidates, reverse=True):
        subprocess.run(
            ["net", "use", remote, "/delete", "/y"],
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="replace",
            check=False,
        )


def _server_prefix_from_share(smb_share: str) -> str:
    match = re.match(r"^(\\\\[^\\]+\\)", smb_share)
    if not match:
        return smb_share
    return match.group(1)
