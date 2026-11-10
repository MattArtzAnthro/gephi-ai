"""Paths for a Windows Gephi when this server runs under WSL.

The two share the files but not the paths. A WSL path such as /tmp/qa.gexf, handed to Gephi on
Windows, is read as C:\\tmp\\qa.gexf: Gephi writes there and the server, reading /tmp, never sees
it. The Windows form of the same file is a drive path for the mounted Windows drives
(/mnt/c/... is C:\\...) and the WSL share for everything else (\\\\wsl$\\<distro>\\...), which
Windows programs read and write like any network path.
"""

import re

_MOUNTED_DRIVE = re.compile(r"^/mnt/([a-zA-Z])(?:/(.*))?$")


def windows_path(path: str, distro: str) -> str:
    """The Windows form of an absolute WSL path; anything else is returned unchanged."""
    if not path.startswith("/"):
        return path
    drive = _MOUNTED_DRIVE.match(path)
    if drive:
        return f"{drive.group(1).upper()}:\\" + (drive.group(2) or "").replace("/", "\\")
    return f"\\\\wsl$\\{distro}" + path.replace("/", "\\")
