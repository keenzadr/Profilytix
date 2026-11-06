"""Offline release resources and launcher diagnostics, without needing PyInstaller."""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_packaging_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "packaging" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_demo_is_deterministic_and_contains_russian_financial_data(tmp_path):
    generate_demo = load_packaging_module("generate_demo").generate_demo
    first = generate_demo(tmp_path / "first.csv")
    second = generate_demo(tmp_path / "second.csv")
    assert first.read_bytes() == second.read_bytes()
    frame = pd.read_csv(first, sep=";", encoding="utf-8-sig")
    assert len(frame) == 180
    assert frame["Доход"].sum() > frame["Расход"].sum() > 0
    assert frame["Расход"].max() == 88000
    assert pd.to_datetime(frame["Дата"]).notna().all()


def test_windowless_launcher_records_exception_in_per_user_log(tmp_path, monkeypatch):
    launcher = load_packaging_module("launcher")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    previous_handlers = logging.getLogger().handlers[:]
    previous_level = logging.getLogger().level
    try:
        path = launcher.configure_logging()
        try:
            raise RuntimeError("Cyrillic startup failure: ошибка")
        except RuntimeError:
            launcher.report_exception(*sys.exc_info(), path)
        assert path == tmp_path / "Profilytix" / "logs" / "startup.log"
        text = path.read_text(encoding="utf-8")
        assert "RuntimeError" in text
        assert "ошибка" in text
    finally:
        for handler in logging.getLogger().handlers[:]:
            if handler not in previous_handlers:
                logging.getLogger().removeHandler(handler)
                handler.close()
        logging.getLogger().setLevel(previous_level)


def test_release_smoke_exercises_source_dependencies_and_five_exports(tmp_path):
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["LOCALAPPDATA"] = str(tmp_path / "local")
    environment["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "packaging")])
    result = subprocess.run(
        [sys.executable, str(ROOT / "packaging" / "launcher.py"), "--smoke-test", str(tmp_path / "smoke")],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=90,
    )
    log_path = tmp_path / "local" / "Profilytix" / "logs" / "startup.log"
    diagnostic = log_path.read_text(encoding="utf-8") if log_path.exists() else "No startup log"
    assert result.returncode == 0, result.stderr + diagnostic
    import json

    evidence = json.loads((tmp_path / "smoke" / "smoke-results.json").read_text(encoding="utf-8"))
    assert evidence["status"] == "passed"
    assert evidence["frozen"] is False
    assert set(evidence["exports"]) == {"pdf", "xlsx", "html", "png", "csv"}
