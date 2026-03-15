# Real-Time Anomaly Detection on Time-Series Streams

Production-style demo: online anomaly detection on a live multivariate sensor stream with concept-drift handling. No batch retraining; the model updates with every observation and resets when the score distribution shifts.

## Problem

In streaming settings, data distribution can change over time (concept drift). A fixed model may either miss new anomalies or flag normal behavior as anomalous. This project implements an **online** detector that adapts continuously and a **drift detector** on the anomaly score stream that triggers a model reset when the underlying distribution changes.

## Approach

- **Synthetic stream**: Three-phase generator (normal baseline → gradual drift → injected anomalies) with configurable rates and ground truth labels. Fully self-contained; no external data.
- **Online scorer**: River HalfSpaceTrees with MinMaxScaler; one observation at a time, score in [0, 1], configurable alert threshold.
- **Drift detection**: ADWIN monitors the **anomaly score** stream (not raw sensors). On drift, the anomaly model resets so it can adapt to the new regime.
- **Running metrics**: Precision and recall against ground truth are updated after every observation.
- **Real-time UI**: FastAPI + WebSocket broadcasts each scored observation; a minimal HTML/JS dashboard shows a rolling chart, anomaly and drift markers, and live counters. New visitors receive a replay of the last 200 points, then live updates. Counters reset at the start of each stream cycle (~40s).

## Tech stack

- **Python 3.10+**
- **River** — online anomaly detection (HalfSpaceTrees), drift detection (ADWIN)
- **FastAPI** — REST + WebSocket; static dashboard
- **asyncio** — async stream and pipeline
- **pytest** — tests (stream, detector, pipeline, server)

## Setup and run

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
python run.py
```

Open **http://localhost:8000/** (or http://127.0.0.1:8000/). The pipeline starts when the first client connects. The stream loops; metrics reset each cycle.

## Tests

```bash
pytest
```

All tests are self-contained (synthetic stream, no external services). Single invocation, no manual setup.

## Project layout

| Path | Role |
|------|------|
| `src/stream/` | Observation model, async synthetic generator (phases A/B/C) |
| `src/detector/` | Anomaly scorer (River pipeline), drift detector (ADWIN), running P/R |
| `src/pipeline/` | Async pipeline: stream → score → broadcast; state and replay |
| `src/server/` | FastAPI app, WebSocket + replay buffer, REST `/stats`, static dashboard |
| `tests/` | Pytest for stream, detector, pipeline, dashboard |

## Design choices

- **Drift on scores, not raw data**: ADWIN watches the anomaly score stream so resets align with changes in “what the model considers normal,” not raw sensor scale.
- **Replay on connect**: New clients get the last 200 messages immediately, then live; no need to wait for the next cycle.
- **Start on first connect**: Pipeline runs only when at least one client is connected; stream loops and state resets each cycle for a clean demo.
