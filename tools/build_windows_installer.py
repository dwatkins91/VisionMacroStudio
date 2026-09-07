"""Build and self-test the unsigned Windows installer."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORTABLE_BUNDLE = PROJECT_ROOT / ".portable_build" / "dist" / "VisionMacroStudio"
RELEASE_ROOT = PROJECT_ROOT / "release"
INSTALLER_SCRIPT = PROJECT_ROOT / "installer" / "VisionMacroStudio.iss"
INSTALL_TEST_ROOT = PROJECT_ROOT / ".installer_test"


def app_version() -> str:
    text = (PROJECT_ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)', text)
    if not match:
        raise RuntimeError("Could not read the application version.")
    return match.group(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Inno Setup installer from the verified portable bundle."
    )
    parser.add_argument(
        "--skip-install-test",
        action="store_true",
        help="Compile without silently installing and running the packaged self-test.",
    )
    return parser.parse_args()


def require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("The Windows installer must be built on Windows.")


def find_iscc() -> Path:
    configured = os.environ.get("INNO_SETUP_COMPILER", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend(
        Path(root) / "Inno Setup 6" / "ISCC.exe"
        for root in (
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("ProgramFiles", ""),
        )
        if root
    )
    command = shutil.which("ISCC.exe") or shutil.which("iscc")
    if command:
        candidates.append(Path(command))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "Inno Setup 6 was not found. Install it with "
        "'choco install innosetup --no-progress -y' or set "
        "INNO_SETUP_COMPILER to ISCC.exe."
    )


def validate_inputs() -> None:
    if not (PORTABLE_BUNDLE / "VisionMacroStudio.exe").is_file():
        raise RuntimeError(
            "The verified portable bundle was not found. Run "
            "tools/build_windows_portable.py --no-prompt first."
        )
    if not INSTALLER_SCRIPT.is_file():
        raise RuntimeError(f"Installer definition is missing: {INSTALLER_SCRIPT}")


def compile_installer(iscc: Path) -> Path:
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    expected = RELEASE_ROOT / f"VisionMacroStudio-Setup-v{app_version()}.exe"
    if expected.exists():
        expected.unlink()
    subprocess.run(
        [str(iscc), f"/DMyAppVersion={app_version()}", str(INSTALLER_SCRIPT)],
        cwd=PROJECT_ROOT,
        check=True,
    )
    if not expected.is_file() or expected.stat().st_size < 1_000_000:
        raise RuntimeError(f"Installer compilation did not produce {expected.name}.")
    return expected


def self_test_installer(installer: Path) -> None:
    if INSTALL_TEST_ROOT.exists():
        shutil.rmtree(INSTALL_TEST_ROOT)
    INSTALL_TEST_ROOT.mkdir(parents=True)
    install_dir = INSTALL_TEST_ROOT / "installed"
    report = INSTALL_TEST_ROOT / "installer_self_test.json"
    try:
        completed = subprocess.run(
            [
                str(installer),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/SP-",
                f"/DIR={install_dir}",
            ],
            cwd=PROJECT_ROOT,
            timeout=900,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Silent installer test returned exit code {completed.returncode}."
            )
        executable = install_dir / "VisionMacroStudio.exe"
        if not executable.is_file():
            raise RuntimeError("The installer did not install VisionMacroStudio.exe.")
        completed = subprocess.run(
            [str(executable), "--portable-self-test", str(report)],
            cwd=install_dir,
            timeout=300,
            check=False,
        )
        if not report.is_file():
            raise RuntimeError("The installed application self-test did not start.")
        result = json.loads(report.read_text(encoding="utf-8"))
        if completed.returncode != 0 or not result.get("passed"):
            failures = [
                name
                for name, status in result.get("checks", {}).items()
                if not status.get("ok")
            ]
            raise RuntimeError(
                "The installed application self-test failed: "
                + ", ".join(failures or ["unknown error"])
            )
        uninstaller = install_dir / "unins000.exe"
        if not uninstaller.is_file():
            raise RuntimeError("The installer did not create its uninstaller.")
        completed = subprocess.run(
            [
                str(uninstaller),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
            ],
            cwd=PROJECT_ROOT,
            timeout=900,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Silent uninstall test returned exit code {completed.returncode}."
            )
        if executable.exists():
            raise RuntimeError("The uninstaller left the application executable behind.")
    finally:
        if INSTALL_TEST_ROOT.exists():
            shutil.rmtree(INSTALL_TEST_ROOT, ignore_errors=True)


def main() -> int:
    args = parse_args()
    try:
        require_windows()
        validate_inputs()
        installer = compile_installer(find_iscc())
        if not args.skip_install_test:
            self_test_installer(installer)
    except (RuntimeError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print()
        print(f"INSTALLER BUILD FAILED: {exc}")
        return 1
    print()
    print("INSTALLER BUILD COMPLETE")
    print(f"Unsigned installer: {installer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
