"""Bitta nusxa: ishlab turgan server bo'lsa, ikkinchi ishga tushirish uning URL'ini oladi (yangi server ochilmaydi)."""

from pathlib import Path

import pytest

from darsstudio import app_window


def test_running_instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "app_instance.txt"
    monkeypatch.setattr(app_window, "instance_file", lambda: f)
    assert app_window.running_instance() is None                       # fayl yo'q
    f.write_text("http://127.0.0.1:1", encoding="utf-8")
    monkeypatch.setattr(app_window, "wait_ready", lambda url, timeout=30.0: False)
    assert app_window.running_instance() is None                       # eski fayl, server o'lgan
    monkeypatch.setattr(app_window, "wait_ready", lambda url, timeout=30.0: True)
    assert app_window.running_instance() == "http://127.0.0.1:1"
