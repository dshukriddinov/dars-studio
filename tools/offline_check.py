"""Offline sinov (AC-13, FR-22): import -> audio -> ASR -> sinxron -> kesish -> eksport -> qayta ochish, tarmoqqa
har qanday ulanish taqiqlangan holda. Har jarayonga `sitecustomize` orqali socket qo'riqchisi qo'yiladi:
127.0.0.1 / ::1 dan boshqa manzilga ulanish urinishi xato beradi va jurnalga yoziladi.

    python tools/offline_check.py VIDEO SLAYDLAR [--workdir DIR] [--no-eye]

Haqiqiy tarmoqni o'chirmaydi (foydalanuvchi kompyuteriga tegmaydi), lekin dastur tarmoqqa chiqmoqchi bo'lsa ushlanadi.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

GUARD = r'''
import socket, os
_orig = socket.socket.connect
_ALLOWED = ("127.0.0.1", "::1", "localhost")
def _guard(self, addr, *a, **k):
    host = addr[0] if isinstance(addr, tuple) else str(addr)
    if host not in _ALLOWED:
        with open(os.environ["DARS_OFFLINE_LOG"], "a", encoding="utf-8") as f:
            f.write(f"BLOCKED {host}\n")
        raise OSError(f"offline sinov: tarmoqqa ulanish taqiqlangan ({host})")
    return _orig(self, addr, *a, **k)
socket.socket.connect = _guard
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("slides")
    ap.add_argument("--workdir")
    ap.add_argument("--no-eye", action="store_true")
    a = ap.parse_args()
    guard_dir = Path(tempfile.mkdtemp(prefix="dars_offline_"))
    (guard_dir / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
    log = guard_dir / "blocked.log"
    log.write_text("", encoding="utf-8")
    wd = Path(a.workdir or tempfile.mkdtemp(prefix="dars_offline_wd_"))
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(guard_dir), os.environ.get("PYTHONPATH", "")]),
           "DARS_OFFLINE_LOG": str(log), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    name = "offline_" + time.strftime("%H%M%S")
    proj = str(wd / name)
    steps = [["import", a.video, a.slides, "--name", name, "--workdir", str(wd), "--meta", "fan=Offline sinov"],
             ["audio", proj], ["asr", proj], ["sync", proj], ["cuts", proj, "--approve-all"]]
    if not a.no_eye:
        steps.append(["eyecontact", proj])
    steps += [["export", proj], ["info", proj]]
    t0 = time.time()
    for s in steps:
        t = time.time()
        r = subprocess.run([sys.executable, "-m", "darsstudio.cli", *s], env=env, capture_output=True,
                           encoding="utf-8", errors="replace")
        print(f"{s[0]:<10} kod {r.returncode}  {time.time() - t:6.1f} s  {(r.stdout.strip().splitlines() or [''])[-1]}")
        if r.returncode != 0:
            print(r.stderr[-2000:])
            return 1
    blocked = log.read_text(encoding="utf-8").strip()
    print(f"Jami {time.time() - t0:.0f} s. Tarmoqqa urinishlar: {blocked or 'yoq'}")
    print(f"Loyiha: {proj}")
    return 0 if not blocked else 2


if __name__ == "__main__":
    sys.exit(main())
