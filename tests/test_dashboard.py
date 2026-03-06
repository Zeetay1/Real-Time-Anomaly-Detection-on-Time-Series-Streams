"""Phase 4: Dashboard and single-command run tests."""

import subprocess
import sys
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from src.server.app import app

STATIC_DIR = Path(__file__).resolve().parent.parent / "src" / "server" / "static"


def test_index_html_contains_dashboard_elements():
    """Dashboard HTML has chart, counters, and script for dashboard.js."""
    index_path = STATIC_DIR / "index.html"
    assert index_path.exists()
    html = index_path.read_text()
    assert "id=\"chart\"" in html or "id='chart'" in html
    assert "total-anomalies" in html
    assert "total-drift" in html
    assert "precision" in html
    assert "recall" in html
    assert "dashboard.js" in html


def test_dashboard_js_connects_via_websocket_and_updates():
    """Dashboard JS contains WebSocket connection and real-time update logic."""
    js_path = STATIC_DIR / "dashboard.js"
    assert js_path.exists()
    js = js_path.read_text()
    assert "WebSocket" in js
    assert "/ws" in js
    assert "observation_index" in js
    assert "alert" in js
    assert "drift_event" in js
    assert "chart" in js or "Chart" in js


@pytest.mark.asyncio
async def test_root_serves_dashboard():
    """GET / returns the dashboard HTML."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "chart" in resp.text
    assert "dashboard.js" in resp.text


@pytest.mark.asyncio
async def test_static_serves_dashboard_js():
    """GET /static/dashboard.js returns the script."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/static/dashboard.js")
    assert resp.status_code == 200
    assert "WebSocket" in resp.text


def test_single_command_starts_server():
    """The entire system starts with one command (run.py or python -m src.server.app)."""
    import urllib.request
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.server.app"],
        cwd=str(Path(__file__).resolve().parent.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**__import__("os").environ},
    )
    try:
        for _ in range(15):
            time.sleep(1)
            try:
                req = urllib.request.urlopen("http://127.0.0.1:8000/", timeout=3)
                assert req.status == 200
                req.close()
                break
            except OSError:
                continue
        else:
            pytest.fail("Server did not respond within 15 seconds")
    finally:
        proc.terminate()
        proc.wait(timeout=8)
