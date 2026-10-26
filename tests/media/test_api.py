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
