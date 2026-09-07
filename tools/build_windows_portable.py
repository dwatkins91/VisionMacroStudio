"""Build and verify a self-contained Windows release of Vision Macro Studio."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PROJECT_ROOT / ".portable_build"
DIST_ROOT = BUILD_ROOT / "dist"
WORK_ROOT = BUILD_ROOT / "work"
RELEASE_ROOT = PROJECT_ROOT / "release"
APP_FOLDER_NAME = "VisionMacroStudio"
EXE_NAME = "VisionMacroStudio.exe"
SOURCE_URL = "https://github.com/dwatkins91/VisionMacroStudio"
RUNTIME_DISTRIBUTIONS = (
    "PySide6",
    "shiboken6",
    "mss",
    "pynput",
    "Pillow",
    "numpy",
    "opencv-python",
    "torch",
    "torchvision",
    "ultralytics",
    "PyYAML",
)


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
    write_windows_version_info()
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


def write_windows_version_info() -> Path:
    """Create Windows file metadata that always matches the application version."""
    parts = [int(value) for value in app_version().split(".")]
    if len(parts) > 4 or any(value < 0 or value > 65535 for value in parts):
        raise RuntimeError("The application version cannot be represented by Windows.")
    parts.extend([0] * (4 - len(parts)))
    dotted = ".".join(str(value) for value in parts)
    path = BUILD_ROOT / "windows_version_info.txt"
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({', '.join(str(value) for value in parts)}),
    prodvers=({', '.join(str(value) for value in parts)}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Dillard Watkins'),
         StringStruct('FileDescription', 'Vision Macro Studio'),
         StringStruct('FileVersion', '{dotted}'),
         StringStruct('InternalName', 'VisionMacroStudio'),
         StringStruct('LegalCopyright', 'Copyright (c) 2026 Dillard Watkins'),
         StringStruct('OriginalFilename', 'VisionMacroStudio.exe'),
         StringStruct('ProductName', 'Vision Macro Studio'),
         StringStruct('ProductVersion', '{dotted}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    return path


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


def collect_third_party_licenses(bundle: Path) -> int:
    target_root = bundle / "THIRD_PARTY_LICENSES"
    target_root.mkdir(exist_ok=True)
    copied = 0
    for distribution_name in RUNTIME_DISTRIBUTIONS:
        try:
            distribution = importlib.metadata.distribution(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            continue
        candidates = []
        for entry in distribution.files or []:
            filename = Path(str(entry)).name.casefold()
            if filename.startswith(("license", "copying", "notice", "authors")):
                candidates.append(entry)
        for index, entry in enumerate(candidates[:8], start=1):
            source = Path(distribution.locate_file(entry))
            try:
                if not source.is_file() or source.stat().st_size > 2_000_000:
                    continue
                safe_distribution = re.sub(
                    r"[^A-Za-z0-9_.-]+", "_", distribution_name
                )
                destination = (
                    target_root / f"{safe_distribution}-{index}-{source.name}"
                )
                shutil.copy2(source, destination)
                copied += 1
            except OSError:
                continue
    return copied


def write_build_info(bundle: Path, third_party_license_files: int) -> None:
    dependencies = {}
    for name in RUNTIME_DISTRIBUTIONS:
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = "not found"
    (bundle / "BUILD_INFO.json").write_text(
        json.dumps(
            {
                "application": "Vision Macro Studio",
                "version": app_version(),
                "source": f"{SOURCE_URL}/tree/v{app_version()}",
                "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "python": platform.python_version(),
                "platform": platform.platform(),
                "third_party_license_files": third_party_license_files,
                "dependencies": dependencies,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def verify_release_contents(archive_path: Path) -> None:
    required = {
        f"{APP_FOLDER_NAME}/{EXE_NAME}",
        f"{APP_FOLDER_NAME}/START_HERE.txt",
        f"{APP_FOLDER_NAME}/LICENSE.txt",
        f"{APP_FOLDER_NAME}/THIRD_PARTY_NOTICES.txt",
        f"{APP_FOLDER_NAME}/SOURCE_OFFER.txt",
        f"{APP_FOLDER_NAME}/PRIVACY.txt",
        f"{APP_FOLDER_NAME}/BUILD_INFO.json",
    }
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    missing = sorted(required - names)
    if missing:
        raise RuntimeError("Portable archive is missing: " + ", ".join(missing))


def write_checksum(archive_path: Path) -> Path:
    checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    path = RELEASE_ROOT / "SHA256SUMS.txt"
    path.write_text(f"{checksum}  {archive_path.name}\n", encoding="ascii")
    return path


def finish_release(bundle: Path, demo_project: Path | None) -> Path:
    shutil.copy2(PROJECT_ROOT / "PORTABLE_README.txt", bundle / "START_HERE.txt")
    shutil.copy2(PROJECT_ROOT / "LICENSE", bundle / "LICENSE.txt")
    shutil.copy2(
        PROJECT_ROOT / "THIRD_PARTY_NOTICES.md",
        bundle / "THIRD_PARTY_NOTICES.txt",
    )
    shutil.copy2(PROJECT_ROOT / "SOURCE_OFFER.txt", bundle / "SOURCE_OFFER.txt")
    shutil.copy2(PROJECT_ROOT / "docs" / "PRIVACY.md", bundle / "PRIVACY.txt")
    shutil.copy2(
        PROJECT_ROOT / "docs" / "USER_GUIDE.md", bundle / "USER_GUIDE.txt"
    )
    license_count = collect_third_party_licenses(bundle)
    write_build_info(bundle, license_count)
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
    archive_path = Path(result)
    verify_release_contents(archive_path)
    write_checksum(archive_path)
    return archive_path


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
