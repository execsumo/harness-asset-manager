from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import Literal

from harness_asset_manager.atomic_files import atomic_write_text

# Keep matching the stamp we placed in data/hermes/harnessam_hermes_compat.py
STAMP_MARKER = '__version__ = "0.1.0"'
PTH_CONTENT = "import harnessam_hermes_compat\n"


def _find_hermes_site_packages(hermes_root: Path) -> Path | None:
    """Best-effort discovery of the Hermes virtualenv site-packages.

    Probes for the documented checkout layout: hermes-agent/venv/lib/python*/site-packages.
    Returns None if Hermes is absent or laid out differently.
    """
    lib_dir = hermes_root / "hermes-agent" / "venv" / "lib"
    if not lib_dir.is_dir():
        return None

    try:
        for py_dir in lib_dir.iterdir():
            if py_dir.is_dir() and py_dir.name.startswith("python"):
                site_packages = py_dir / "site-packages"
                if site_packages.is_dir():
                    return site_packages
    except OSError:
        pass

    return None


def status(hermes_root: Path) -> Literal["not-detected", "absent", "stale", "current"]:
    """Check the status of the Hermes compatibility sidecar.

    Returns:
        "not-detected" if Hermes or its venv site-packages is missing.
        "absent" if the sidecar files are missing.
        "stale" if the sidecar is present but out of date (needs refresh).
        "current" if the sidecar is installed and matches the current stamp.
    """
    site_packages = _find_hermes_site_packages(hermes_root)
    if not site_packages:
        return "not-detected"

    pth = site_packages / "harnessam_hermes_compat.pth"
    py = site_packages / "harnessam_hermes_compat.py"

    if not pth.exists() or not py.exists():
        return "absent"

    try:
        content = py.read_text(encoding="utf-8")
        if STAMP_MARKER in content:
            return "current"
        return "stale"
    except OSError:
        # If we can't read it, treat it as stale so the applier can try to overwrite it
        return "stale"


def _get_shim_content() -> str | None:
    try:
        return importlib.resources.files("harness_asset_manager.data.hermes").joinpath("harnessam_hermes_compat.py").read_text(encoding="utf-8")
    except Exception:
        return None


def apply_hermes_compat(hermes_root: Path) -> bool:
    """Best-effort install or refresh of the Hermes sidecar.

    Never raises. A missing Hermes, missing venv, or write permission denied
    resolves to False rather than an error.
    """
    site_packages = _find_hermes_site_packages(hermes_root)
    if not site_packages:
        return False

    if status(hermes_root) == "current":
        return True

    shim_content = _get_shim_content()
    if not shim_content:
        return False

    pth = site_packages / "harnessam_hermes_compat.pth"
    py = site_packages / "harnessam_hermes_compat.py"

    try:
        atomic_write_text(py, shim_content)
        atomic_write_text(pth, PTH_CONTENT)
    except OSError:
        return False

    return True


def remove_hermes_compat(hermes_root: Path) -> bool:
    """Best-effort teardown of the Hermes sidecar.

    Deletes the two sidecar files. Never raises.
    Returns True if teardown was successful OR if nothing needed to be done
    (because Hermes is not present or sidecar was already absent).
    Returns False only if deletion failed due to an error (e.g., permissions).
    """
    site_packages = _find_hermes_site_packages(hermes_root)
    if not site_packages:
        return True  # Nothing to do

    pth = site_packages / "harnessam_hermes_compat.pth"
    py = site_packages / "harnessam_hermes_compat.py"

    if not pth.exists() and not py.exists():
        return True  # Already absent

    try:
        pth.unlink(missing_ok=True)
        py.unlink(missing_ok=True)
    except OSError:
        return False

    return True
