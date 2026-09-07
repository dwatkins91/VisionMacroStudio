"""Local, privacy-preserving readiness checks for source and portable builds."""

from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import shutil
import struct
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    key: str
    label: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


DEPENDENCIES = (
    ("pyside6", "Desktop interface", "PySide6"),
    ("mss", "Screen capture", "mss"),
    ("pillow", "Image processing", "PIL"),
    ("numpy", "Numeric processing", "numpy"),
    ("opencv", "Detection previews", "cv2"),
    ("pynput", "Mouse, keyboard, and hotkeys", "pynput"),
    ("torch", "Machine-learning runtime", "torch"),
    ("torchvision", "Vision runtime", "torchvision"),
    ("ultralytics", "YOLO training and detection", "ultralytics"),
    ("yaml", "Dataset configuration", "yaml"),
)


def _writable_directory(key: str, label: str, path: Path) -> CheckResult:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="vms_check_", dir=path, delete=True):
            pass
        return CheckResult(key, label, "pass", f"Writable: {path}")
    except OSError as exc:
        return CheckResult(key, label, "fail", f"Cannot write to {path}: {exc}")


def _dependency_check(
    key: str, label: str, module_name: str, *, deep: bool
) -> CheckResult:
    try:
        if deep:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", None)
        else:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                raise ModuleNotFoundError(module_name)
            version = None
        suffix = f" {version}" if version else ""
        return CheckResult(key, label, "pass", f"Available{suffix}")
    except Exception as exc:
        return CheckResult(
            key,
            label,
            "fail",
            f"{type(exc).__name__}: {exc}",
        )


def run_system_checks(
    project_directory: str | Path | None = None,
    *,
    deep: bool = True,
    include_display: bool = True,
) -> list[CheckResult]:
    """Return readiness results without capturing the screen or sending input."""

    results: list[CheckResult] = []
    if os.name == "nt":
        results.append(
            CheckResult("operating_system", "Windows", "pass", platform.platform())
        )
    else:
        results.append(
            CheckResult(
                "operating_system",
                "Windows",
                "warn",
                f"{platform.system()} detected; the public build is Windows-first.",
            )
        )

    architecture = struct.calcsize("P") * 8
    results.append(
        CheckResult(
            "architecture",
            "64-bit runtime",
            "pass" if architecture == 64 else "fail",
            f"{architecture}-bit Python {platform.python_version()}",
        )
    )
    python_ok = sys.version_info >= (3, 10) or bool(getattr(sys, "frozen", False))
    results.append(
        CheckResult(
            "python",
            "Python runtime",
            "pass" if python_ok else "fail",
            (
                f"Bundled Python {platform.python_version()}"
                if getattr(sys, "frozen", False)
                else f"Python {platform.python_version()}"
            ),
        )
    )

    from app.core.config import application_data_dir, default_project_dir

    app_data = application_data_dir()
    project_path = Path(project_directory) if project_directory else default_project_dir()
    results.append(_writable_directory("app_data", "App settings folder", app_data))
    results.append(_writable_directory("project_data", "Project folder", project_path))

    try:
        usage = shutil.disk_usage(project_path)
        free_gb = usage.free / (1024**3)
        status = "pass" if free_gb >= 5 else "warn"
        results.append(
            CheckResult(
                "disk_space",
                "Free project storage",
                status,
                f"{free_gb:.1f} GB available; training can require several GB.",
            )
        )
    except OSError as exc:
        results.append(CheckResult("disk_space", "Free project storage", "warn", str(exc)))

    for key, label, module_name in DEPENDENCIES:
        results.append(_dependency_check(key, label, module_name, deep=deep))

    if include_display:
        try:
            from app.capture.grabber import list_monitors

            monitors = list_monitors()
            physical = max(0, len(monitors) - 1)
            status = "pass" if physical else "fail"
            results.append(
                CheckResult(
                    "displays",
                    "Screen access",
                    status,
                    f"{physical} display(s) available; no screenshot was saved.",
                )
            )
        except Exception as exc:
            results.append(
                CheckResult(
                    "displays",
                    "Screen access",
                    "fail",
                    f"{type(exc).__name__}: {exc}",
                )
            )

    torch_result = next((item for item in results if item.key == "torch"), None)
    if deep and torch_result and torch_result.status == "pass":
        try:
            import torch

            if torch.cuda.is_available():
                detail = str(torch.cuda.get_device_name(0))
                results.append(CheckResult("acceleration", "GPU acceleration", "pass", detail))
            else:
                results.append(
                    CheckResult(
                        "acceleration",
                        "GPU acceleration",
                        "warn",
                        "No compatible CUDA GPU detected. CPU training still works but is slower.",
                    )
                )
        except Exception as exc:
            results.append(
                CheckResult("acceleration", "GPU acceleration", "warn", str(exc))
            )
    return results


def checks_summary(results: list[CheckResult]) -> dict[str, Any]:
    counts = {status: 0 for status in ("pass", "warn", "fail")}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "ready": counts["fail"] == 0,
        "counts": counts,
        "checks": [result.to_dict() for result in results],
    }
