from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path


def asset_path(name: str) -> Path:
    """Return an application asset in source and PyInstaller builds."""
    package_asset = Path(__file__).resolve().parent / "assets" / name
    bundle_root_value = getattr(sys, "_MEIPASS", None)
    candidates = [package_asset]
    if bundle_root_value:
        bundle_root = Path(bundle_root_value)
        candidates.extend(
            (
                bundle_root / "assets" / name,
                bundle_root / "app" / "assets" / name,
            )
        )
    return next((path for path in candidates if path.is_file()), package_asset)


def portable_self_test(report_path: Path) -> int:
    """Exercise packaged imports and write a machine-readable build report."""
    checks: dict[str, dict[str, str | bool]] = {}
    modules = (
        "PySide6",
        "mss",
        "pynput",
        "PIL",
        "numpy",
        "cv2",
        "torch",
        "torchvision",
        "ultralytics",
        "yaml",
    )
    passed = True
    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
            checks[module_name] = {
                "ok": True,
                "version": str(getattr(module, "__version__", "available")),
            }
        except Exception as exc:
            passed = False
            checks[module_name] = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
    icon = asset_path("vision_macro_eye.png")
    checks["application_icon"] = {"ok": icon.is_file(), "path": str(icon)}
    passed = passed and icon.is_file()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "passed": passed,
                "platform": platform.platform(),
                "python": platform.python_version(),
                "checks": checks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if passed else 1


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--portable-self-test":
        return portable_self_test(Path(sys.argv[2]))

    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        print(
            "PySide6 is not installed. Run run_app.bat on Windows to install dependencies."
        )
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("Vision Macro Studio")
    app.setOrganizationName("Vision Macro Studio")
    app.setStyle("Fusion")
    icon_path = asset_path("vision_macro_eye.png")
    app_icon = QIcon(str(icon_path))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    try:
        from app.gui.main_window import MainWindow
        from app.gui.styles import APP_STYLE

        app.setStyleSheet(APP_STYLE)
        window = MainWindow()
        if not app_icon.isNull():
            window.setWindowIcon(app_icon)
        window.show()
        return app.exec()
    except Exception as exc:
        QMessageBox.critical(None, "Vision Macro Studio could not start", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
