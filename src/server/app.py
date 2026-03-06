"""FastAPI app: WebSocket broadcast, REST /stats, static dashboard."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.pipeline.runner import run_pipeline
from src.stream.generator import generate_stream


# Shared state updated by the pipeline, read by /stats
STATE: dict = {
    "total_observations": 0,
    "total_anomalies_detected": 0,
    "total_drift_events": 0,
    "current_precision": 0.0,
    "current_recall": 0.0,
}


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
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


async def _run_pipeline_task() -> None:
    stream = generate_stream(
        phase_a_length=300,
        phase_b_length=200,
        phase_c_length=300,
        delay=0.05,
        seed=42,
    )
    await run_pipeline(stream, manager.broadcast, state=STATE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_run_pipeline_task())
    yield
    task.cancel()
    try:
        await task
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
    await manager.connect(websocket)
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
