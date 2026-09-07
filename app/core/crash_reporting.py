"""Last-resort local crash logging for unexpected GUI exceptions."""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from app import __version__
from app.core.config import application_data_dir
from app.core.diagnostics import redact_text


def write_crash_report(
    exception_type: type[BaseException],
    exception: BaseException,
    trace,
    directory: Path | None = None,
) -> Path:
    target_dir = directory or application_data_dir() / "crashes"
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = target_dir / f"crash_{timestamp}.txt"
    content = (
        f"Vision Macro Studio {__version__}\n"
        f"UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
        + "".join(traceback.format_exception(exception_type, exception, trace))
    )
    path.write_text(redact_text(content), encoding="utf-8")
    return path


def install_exception_hook() -> None:
    """Show a recoverable message and retain a scrubbed local report."""

    def handle(exception_type, exception, trace) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            sys.__excepthook__(exception_type, exception, trace)
            return
        try:
            report = write_crash_report(exception_type, exception, trace)
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                None,
                "Vision Macro Studio encountered an error",
                "An unexpected error was stopped before it could continue.\n\n"
                f"A scrubbed local crash report was saved to:\n{report}\n\n"
                "Restart the app, then use Logs > Create Diagnostic Package if you "
                "want to report the problem.",
            )
        except Exception:
            sys.__excepthook__(exception_type, exception, trace)

    sys.excepthook = handle
