"""Windowed executable entry point with writable per-user diagnostic logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import tempfile


def configure_logging() -> Path:
    """Keep diagnostics out of the installation directory and rotate old logs."""
    base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
    directory = base / "Profilytix" / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "startup.log"
    handler = RotatingFileHandler(target, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    return target


def report_exception(exc_type, exc_value, traceback, log_path: Path) -> None:
    """Log startup and uncaught Qt callback failures without relying on Qt imports."""
    logging.getLogger("Profilytix").critical(
        "Unhandled application error", exc_info=(exc_type, exc_value, traceback)
    )
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"Profilytix encountered an error.\n\nDetails: {log_path}",
            "Profilytix",
            0x10,
        )


def main() -> int:
    log_path = configure_logging()
    sys.excepthook = lambda *args: report_exception(*args, log_path)
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
            from frozen_smoke import run_smoke_test

            run_smoke_test(Path(sys.argv[2]))
            return 0
        from app.main import main as application_main

        return application_main()
    except Exception:
        report_exception(*sys.exc_info(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
