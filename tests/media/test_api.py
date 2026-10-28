"""B7: API (httpx TestClient) — import, buyruqlar va undo/redo, fayl berish (Range), vazifalar + WebSocket,
xavfsizlik (yo'l chiqib ketishi)."""

import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from darsstudio.api.app import create_app


def test_api_flow(tmp_path: Path, test_media: dict[str, Any]) -> None:
    app = create_app(tmp_path, start_scheduler=True)
    with TestClient(app) as c:
        assert c.get("/api/health").json()["ok"]
        r = c.post("/api/projects", json={"video": test_media["av_offset.mov"]["path"],
                                          "slides": test_media["lesson.pptx"]["path"], "name": "d1",
                                          "meta": {"fan": "Fizika"}, "prepare": False})
        assert r.status_code == 200, r.text
        assert [p["name"] for p in c.get("/api/projects").json()] == ["d1"]
        p = c.get("/api/projects/d1").json()
        assert p["project"]["total_frames"] == 300 and not p["can_undo"]

        r = c.post("/api/projects/d1/commands", json={"label": "chegara", "values": {"key.tolerance": 0.2}})
        assert r.json()["project"]["key"]["tolerance"] == 0.2 and r.json()["undo_label"] == "chegara"
        bad = c.post("/api/projects/d1/commands", json={"label": "x", "values": {"total_frames": -5}})
        assert bad.status_code == 400
        assert c.post("/api/projects/d1/undo").json()["project"]["key"]["tolerance"] != 0.2
        assert c.post("/api/projects/d1/redo").json()["project"]["key"]["tolerance"] == 0.2

        # xato import: o'zbekcha tushunarli xabar
        r = c.post("/api/projects", json={"video": test_media["beep.mov"]["path"],
                                          "slides": test_media["lesson.pptx"]["path"], "prepare": False})
        assert r.status_code == 400 and "1920x1080" in r.json()["detail"]
        assert c.get("/api/projects/..%2F..").status_code in (400, 404)
        assert c.get("/api/projects/yoq").status_code == 404

        with c.websocket_connect("/ws") as ws:
            jid = c.post("/api/projects/d1/jobs", json={"type": "sleep", "args": {"seconds": 0.5}}).json()["id"]
            seen = set()
            t0 = time.time()
            while "tayyor" not in seen and time.time() - t0 < 60:
                m = ws.receive_json()
                if m["job"]["id"] == jid:
                    seen.add(m["job"]["status"])
            assert {"ishlanmoqda", "tayyor"} <= seen
        jobs = c.get("/api/jobs", params={"project": "d1"}).json()
        assert jobs[-1]["status"] == "tayyor"
        assert c.post("/api/projects/d1/jobs", json={"type": "rm_rf"}).status_code == 400


def test_api_range_request(tmp_path: Path, test_media: dict[str, Any]) -> None:
    from darsstudio.project import importer
    importer.import_project(Path(test_media["av_offset.mov"]["path"]), Path(test_media["lesson.pptx"]["path"]),
                            "demo", tmp_path, name="d2", make_proxy=True)
    with TestClient(create_app(tmp_path, start_scheduler=False)) as c:
        r = c.get("/api/projects/d2/proxy", headers={"Range": "bytes=0-99"})
        assert r.status_code == 206 and len(r.content) == 100


def test_lower_third_preview_and_export_task(tmp_path: Path) -> None:
    from darsstudio.jobs.tasks import TASKS
    with TestClient(create_app(tmp_path, start_scheduler=False)) as c:
        meta = {"oqituvchi": "Asadov Shavkat Gʻaybullayevich", "ish_joyi": "Gumanitar va ijtimoiy fanlar maktabi",
                "lavozim": "professori", "ilmiy_unvon": "Yuridik fanlari doktori"}
        r = c.post("/api/lower-third-preview", json={"template": "akademiya", "meta": meta})
        assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
        assert c.post("/api/lower-third-preview", json={"template": "../x", "meta": {}}).status_code == 400
    assert "export" in TASKS


def test_lines_from_ui_fields() -> None:
    from darsstudio.render import overlays
    name, sub = overlays._lines({"oqituvchi": "A B", "ish_joyi": "Maktab", "lavozim": "dotsenti",
                                 "ilmiy_unvon": "(PhD)"})
    assert (name, sub) == ("A B", ["Maktab dotsenti", "(PhD)"])
    assert overlays._lines({"oqituvchi": "A", "lavozim": "dotsenti"})[1] == ["dotsenti"]
    assert overlays._lines({"oqituvchi": "A", "unvon": "x | y"})[1] == ["x", "y"]       # eski loyihalar


def test_reveal_cmd_quotes_only_path() -> None:
    from darsstudio.api.app import reveal_cmd
    assert reveal_cmd(Path(r"D:\projects\ai montaj\x\v6.mp4")) == r'explorer /select,"D:\projects\ai montaj\x\v6.mp4"'


def test_waveform_one_value_per_frame(tmp_path: Path, test_media: dict[str, Any]) -> None:
    from darsstudio.audio.extract import extract_all
    from darsstudio.media.probe import probe
    from darsstudio.project import importer
    from darsstudio.project.store import ProjectStore
    src = Path(test_media["av_offset.mov"]["path"])
    importer.import_project(src, Path(test_media["lesson.pptx"]["path"]), "demo", tmp_path, name="d3")
    with TestClient(create_app(tmp_path, start_scheduler=False)) as c:
        assert c.get("/api/projects/d3/waveform").status_code == 404
        extract_all(probe(src), ProjectStore(tmp_path / "d3").cache("audio"))
        r = c.get("/api/projects/d3/waveform")
        assert r.status_code == 200
        frames = c.get("/api/projects/d3").json()["project"]["total_frames"]
        assert abs(len(r.content) - frames) <= 1 and max(r.content) > 200


def test_final_preview_stale_after_edit(tmp_path: Path, test_media: dict[str, Any]) -> None:
    from darsstudio.jobs.tasks import final_key
    from darsstudio.project import importer
    from darsstudio.project.store import atomic_write_json
    importer.import_project(Path(test_media["av_offset.mov"]["path"]), Path(test_media["lesson.pptx"]["path"]),
                            "demo", tmp_path, name="d4")
    root = tmp_path / "d4"
    with TestClient(create_app(tmp_path, start_scheduler=False)) as c:
        assert c.get("/api/projects/d4/final-preview").json() == {"file": None}
        # render vazifasi natijasi (GPU'siz taqlid): mp4 + render paytidagi holat
        d = root / "cache" / "preview"
        d.mkdir(parents=True)
        (d / f"final_{final_key(root)}.mp4").write_bytes(b"x")
        atomic_write_json(d / f"final_{final_key(root)}.json", {"key": final_key(root), "keep": [[0, 300]]})
        r = c.get("/api/projects/d4/final-preview").json()
        assert r["keep"] == [[0, 300]] and not r["stale"] and r["file"].startswith("cache/preview/final_")
        c.post("/api/projects/d4/commands", json={"label": "x", "values": {"key.tolerance": 0.3}})
        assert c.get("/api/projects/d4/final-preview").json()["stale"]


def test_preview_start_maps_source_time_past_cuts(tmp_path: Path, test_media: dict[str, Any]) -> None:
    """"Haqiqiy ko'rinish": start_s asl video vaqti, render boshi esa kesishlardan keyingi chiqish kadri."""
    from darsstudio.project import importer
    importer.import_project(Path(test_media["av_offset.mov"]["path"]), Path(test_media["lesson.pptx"]["path"]),
                            "demo", tmp_path, name="d5")
    with TestClient(create_app(tmp_path, start_scheduler=False)) as c:
        cuts = [{"start": 25, "end": 75, "reason": "manual", "status": "tasdiqlangan"}]
        assert c.post("/api/projects/d5/commands", json={"label": "k", "values": {"cuts": cuts}}).status_code == 200
        fps = c.get("/api/projects/d5").json()["project"]["fps"]
        num, den = (int(x) for x in fps.split("/"))
        r = c.post("/api/projects/d5/preview", params={"start_s": 100 * den / num, "duration_s": 2}).json()
        assert r["file"].endswith("preview_50_2000.mp4")      # 100-kadr: oldidan 50 kadr kesilgan
        r = c.post("/api/projects/d5/preview", params={"start_s": 40 * den / num, "duration_s": 2}).json()
        assert r["file"].endswith("preview_25_2000.mp4")      # kesilgan joy ichida: keyingi saqlangan kadr
