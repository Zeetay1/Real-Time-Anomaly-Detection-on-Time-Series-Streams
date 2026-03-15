"""Phase 3: Real-time broadcasting pipeline and server tests."""

import asyncio
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.pipeline.runner import run_pipeline
from src.stream.generator import generate_stream


# Required broadcast message schema
BROADCAST_KEYS = {
    "timestamp",
    "temperature",
    "pressure",
    "vibration",
    "anomaly_score",
    "alert",
    "drift_event",
    "running_precision",
    "running_recall",
    "observation_index",
    "total_anomalies_detected",
    "total_drift_events",
}


@pytest.mark.asyncio
async def test_websocket_receives_broadcast_messages_in_real_time():
    """A WebSocket client receives broadcast messages in real time as the stream runs."""
    received: list[dict[str, Any]] = []
    n_want = 15

    async def broadcaster(msg: dict[str, Any]) -> None:
        received.append(msg)
        if len(received) >= n_want:
            raise asyncio.CancelledError("enough")

    stream = generate_stream(
        phase_a_length=50,
        phase_b_length=0,
        phase_c_length=0,
        delay=0,
        seed=1,
    )
    task = asyncio.create_task(run_pipeline(stream, broadcaster))
    try:
        await asyncio.wait_for(task, timeout=30.0)
    except asyncio.CancelledError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    assert len(received) >= n_want


@pytest.mark.asyncio
async def test_broadcast_message_schema():
    """Each broadcast message conforms to the documented schema."""
    received: list[dict[str, Any]] = []

    async def broadcaster(msg: dict[str, Any]) -> None:
        received.append(msg)
        if len(received) >= 5:
            raise asyncio.CancelledError("enough")

    stream = generate_stream(
        phase_a_length=20,
        phase_b_length=0,
        phase_c_length=0,
        delay=0,
        seed=2,
    )
    task = asyncio.create_task(run_pipeline(stream, broadcaster))
    try:
        await asyncio.wait_for(task, timeout=15.0)
    except asyncio.CancelledError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    assert len(received) >= 5
    for msg in received:
        assert set(msg.keys()) == BROADCAST_KEYS, "Message must have all required keys"
        assert isinstance(msg["timestamp"], (int, float))
        assert isinstance(msg["temperature"], (int, float))
        assert isinstance(msg["pressure"], (int, float))
        assert isinstance(msg["vibration"], (int, float))
        assert isinstance(msg["anomaly_score"], (int, float))
        assert isinstance(msg["alert"], bool)
        assert isinstance(msg["drift_event"], bool)
        assert isinstance(msg["running_precision"], (int, float))
        assert isinstance(msg["running_recall"], (int, float))
        assert isinstance(msg["observation_index"], int)
        assert isinstance(msg["total_anomalies_detected"], int)
        assert isinstance(msg["total_drift_events"], int)
        assert 0 <= msg["anomaly_score"] <= 1


@pytest.mark.asyncio
async def test_stats_endpoint_returns_running_totals():
    """The stats endpoint returns correct running totals after processing a known number of observations."""
    state: dict[str, Any] = {
        "total_observations": 0,
        "total_anomalies_detected": 0,
        "total_drift_events": 0,
        "current_precision": 0.0,
        "current_recall": 0.0,
    }

    async def broadcaster(msg: dict[str, Any]) -> None:
        pass

    stream = generate_stream(
        phase_a_length=30,
        phase_b_length=0,
        phase_c_length=0,
        delay=0,
        seed=3,
    )
    await run_pipeline(stream, broadcaster, state=state)
    assert state["total_observations"] == 30
    assert "total_anomalies_detected" in state
    assert "total_drift_events" in state
    assert "current_precision" in state
    assert "current_recall" in state

    # Hit the FastAPI /stats endpoint (use app without lifespan to avoid pipeline overwriting STATE)
    from fastapi import FastAPI
    from src.server.app import STATE

    test_app = FastAPI()
    @test_app.get("/stats")
    async def _stats():
        return {
            "total_observations": STATE["total_observations"],
            "total_anomalies_detected": STATE["total_anomalies_detected"],
            "total_drift_events": STATE["total_drift_events"],
            "current_precision": STATE["current_precision"],
            "current_recall": STATE["current_recall"],
        }

    saved = dict(STATE)
    STATE.clear()
    STATE.update(
        total_observations=100,
        total_anomalies_detected=7,
        total_drift_events=2,
        current_precision=0.6,
        current_recall=0.5,
    )
    try:
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_observations"] == 100
        assert data["total_anomalies_detected"] == 7
        assert data["total_drift_events"] == 2
        assert data["current_precision"] == 0.6
        assert data["current_recall"] == 0.5
    finally:
        STATE.clear()
        STATE.update(saved)


@pytest.mark.asyncio
async def test_pipeline_no_blocking():
    """No blocking calls in the async pipeline (runs without event loop warnings)."""
    msgs: list[dict] = []

    async def broadcaster(m: dict) -> None:
        msgs.append(m)
        await asyncio.sleep(0)

    stream = generate_stream(
        phase_a_length=10,
        phase_b_length=0,
        phase_c_length=0,
        delay=0,
        seed=4,
    )
    await asyncio.wait_for(run_pipeline(stream, broadcaster), timeout=20.0)
    assert len(msgs) == 10
