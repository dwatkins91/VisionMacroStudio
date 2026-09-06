"""Build and verify a self-contained Windows release of Vision Macro Studio."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PROJECT_ROOT / ".portable_build"
DIST_ROOT = BUILD_ROOT / "dist"
WORK_ROOT = BUILD_ROOT / "work"
RELEASE_ROOT = PROJECT_ROOT / "release"
APP_FOLDER_NAME = "VisionMacroStudio"
EXE_NAME = "VisionMacroStudio.exe"


def app_version() -> str:
    text = (PROJECT_ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)', text)
    if not match:
        raise RuntimeError("Could not read the application version.")
    return match.group(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the portable Windows edition of Vision Macro Studio."
    )
    parser.add_argument(
        "--demo-project",
        type=Path,
        help="Optional project ZIP exported from Vision Macro Studio.",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Build without asking whether to include a demo project.",
    )
    return parser.parse_args()


def require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError(
            "The Windows EXE must be built on Windows. Run this builder from the "
            "working Windows environment where Vision Macro Studio already opens."
        )
    if platform.architecture()[0] != "64bit":
        raise RuntimeError("A 64-bit Python installation is required.")


def ensure_app_dependencies() -> None:
    modules = ("PySide6", "mss", "pynput", "PIL", "cv2", "torch", "ultralytics")
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError(
            "The active environment is missing: "
            + ", ".join(missing)
            + ". Open the app successfully from this same environment before building."
        )


def ensure_pyinstaller() -> None:
    if importlib.util.find_spec("PyInstaller") is not None:
        return
    print("Installing the portable-build tool into this private environment...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(PROJECT_ROOT / "build-requirements.txt"),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


def prompt_for_demo_project(current: Path | None, no_prompt: bool) -> Path | None:
    if current is not None or no_prompt:
        return current
    print()
    print("Optional: include an exported project so your friend can test your model.")
    print("Drag the exported project ZIP into this window, or press Enter to skip.")
    value = input("Project ZIP: ").strip().strip('"')
    return Path(value) if value else None


def validate_demo_project(path: Path | None) -> Path | None:
    if path is None:
        return None
    path = path.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise RuntimeError("The demo project must be an existing exported ZIP file.")
    try:
        with zipfile.ZipFile(path) as archive:
            project_files = [
                name for name in archive.namelist() if Path(name).name == "project.json"
            ]
            if not project_files:
                raise RuntimeError(
                    "That ZIP does not contain a Vision Macro Studio project.json file."
                )
    except zipfile.BadZipFile as exc:
        raise RuntimeError("The selected demo project is not a valid ZIP file.") from exc
    return path


def prepare_build_directories() -> None:
    if BUILD_ROOT.exists():
        if BUILD_ROOT.parent != PROJECT_ROOT or BUILD_ROOT.name != ".portable_build":
            raise RuntimeError("Refusing to clean an unexpected build directory.")
        shutil.rmtree(BUILD_ROOT)
    DIST_ROOT.mkdir(parents=True)
    WORK_ROOT.mkdir(parents=True)
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)


def run_pyinstaller() -> Path:
    print()
    print("Building the Windows application. Torch makes this a large build;")
    print("ten to thirty minutes is normal, and the window may be quiet for a while.")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST_ROOT),
            "--workpath",
            str(WORK_ROOT),
            str(PROJECT_ROOT / "VisionMacroStudio.spec"),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
    bundle = DIST_ROOT / APP_FOLDER_NAME
    executable = bundle / EXE_NAME
    if not executable.is_file():
        raise RuntimeError(f"Build completed without producing {executable}.")
    return bundle


def verify_bundle(bundle: Path) -> None:
    executable = bundle / EXE_NAME
    report = BUILD_ROOT / "portable_self_test.json"
    print()
    print("Checking the packaged GUI, capture, Torch, and Ultralytics imports...")
    completed = subprocess.run(
        [str(executable), "--portable-self-test", str(report)],
        cwd=bundle,
        timeout=300,
        check=False,
    )
    if not report.is_file():
        raise RuntimeError(
            "The packaged self-test did not start. Windows security may have blocked it."
        )
    result = json.loads(report.read_text(encoding="utf-8"))
    if completed.returncode != 0 or not result.get("passed"):
        failures = [
            name
            for name, status in result.get("checks", {}).items()
            if not status.get("ok")
        ]
        raise RuntimeError(
            "The packaged self-test failed: " + ", ".join(failures or ["unknown error"])
        )
    print("Packaged self-test passed.")


def finish_release(bundle: Path, demo_project: Path | None) -> Path:
    shutil.copy2(PROJECT_ROOT / "PORTABLE_README.txt", bundle / "START_HERE.txt")
    if demo_project is not None:
        shutil.copy2(demo_project, bundle / "Demo_Project.zip")
    archive_base = RELEASE_ROOT / f"VisionMacroStudio-Portable-v{app_version()}"
    archive_path = archive_base.with_suffix(".zip")
    if archive_path.exists():
        archive_path.unlink()
    result = shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=DIST_ROOT,
        base_dir=APP_FOLDER_NAME,
    )
    return Path(result)


def main() -> int:
    args = parse_args()
    try:
        require_windows()
        ensure_app_dependencies()
        ensure_pyinstaller()
        demo_project = validate_demo_project(
            prompt_for_demo_project(args.demo_project, args.no_prompt)
        )
        prepare_build_directories()
        bundle = run_pyinstaller()
        verify_bundle(bundle)
        archive = finish_release(bundle, demo_project)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print()
        print(f"BUILD FAILED: {exc}")
        return 1
    print()
    print("BUILD COMPLETE")
    print(f"Share this ZIP with your friend: {archive}")
    print(f"Uncompressed portable folder: {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
