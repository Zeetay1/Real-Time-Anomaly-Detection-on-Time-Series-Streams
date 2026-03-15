"""FastAPI app: WebSocket broadcast, REST /stats, static dashboard."""

import asyncio
import json
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.pipeline.runner import run_pipeline
from src.stream.generator import generate_stream

REPLAY_BUFFER_SIZE = 200

# Shared state updated by the pipeline, read by /stats
STATE: dict = {
    "total_observations": 0,
    "total_anomalies_detected": 0,
    "total_drift_events": 0,
    "current_precision": 0.0,
    "current_recall": 0.0,
}

# Last N messages sent to clients; new connections get this replay first
replay_buffer: deque = deque(maxlen=REPLAY_BUFFER_SIZE)

# Pipeline runs only when at least one client is connected; started on first connect
_pipeline_task: asyncio.Task | None = None


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def register(self, websocket: WebSocket) -> None:
        """Add an already-accepted websocket to the connection list (e.g. after replay)."""
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        text = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def _broadcast_with_replay(message: dict) -> None:
    replay_buffer.append(message)
    await manager.broadcast(message)


def _reset_state() -> None:
    STATE["total_observations"] = 0
    STATE["total_anomalies_detected"] = 0
    STATE["total_drift_events"] = 0
    STATE["current_precision"] = 0.0
    STATE["current_recall"] = 0.0


async def _run_pipeline_loop() -> None:
    """Run pipeline in a loop; start on first client connect. Resets state each cycle."""
    while True:
        _reset_state()
        stream = generate_stream(
            phase_a_length=300,
            phase_b_length=200,
            phase_c_length=300,
            delay=0.05,
            anomaly_rate=0.08,
            seed=42,
        )
        await run_pipeline(
            stream, _broadcast_with_replay, state=STATE, anomaly_threshold=0.49
        )


def _ensure_pipeline_running() -> None:
    global _pipeline_task
    if _pipeline_task is None or _pipeline_task.done():
        _pipeline_task = asyncio.create_task(_run_pipeline_loop())


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    global _pipeline_task
    if _pipeline_task is not None and not _pipeline_task.done():
        _pipeline_task.cancel()
        try:
            await _pipeline_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Real-Time Anomaly Detection", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/dashboard")
async def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    for msg in replay_buffer:
        try:
            await websocket.send_text(json.dumps(msg))
        except Exception:
            break
    manager.register(websocket)
    _ensure_pipeline_running()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


@app.get("/stats")
async def stats():
    return {
        "total_observations": STATE["total_observations"],
        "total_anomalies_detected": STATE["total_anomalies_detected"],
        "total_drift_events": STATE["total_drift_events"],
        "current_precision": STATE["current_precision"],
        "current_recall": STATE["current_recall"],
    }


def main() -> None:
    import uvicorn
    uvicorn.run("src.server.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
