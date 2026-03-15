"""Async pipeline: generator -> scorer -> broadcaster."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from src.detector.anomaly import AnomalyDetector
from src.detector.drift import DriftDetector
from src.detector.metrics import RunningMetrics
from src.stream.models import Observation


def _broadcast_message(
    obs: Observation,
    anomaly_score: float,
    alert: bool,
    drift_event: bool,
    running_precision: float,
    running_recall: float,
    observation_index: int,
) -> dict[str, Any]:
    return {
        "timestamp": obs.timestamp,
        "temperature": obs.temperature,
        "pressure": obs.pressure,
        "vibration": obs.vibration,
        "anomaly_score": anomaly_score,
        "alert": alert,
        "drift_event": drift_event,
        "running_precision": running_precision,
        "running_recall": running_recall,
        "observation_index": observation_index,
    }


async def run_pipeline(
    stream: AsyncIterator[Observation],
    broadcaster: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    anomaly_threshold: float = 0.5,
    state: dict[str, Any] | None = None,
) -> None:
    """Run the detection pipeline: score each observation, detect drift, broadcast messages."""
    detector = AnomalyDetector(threshold=anomaly_threshold)
    drift_detector = DriftDetector()
    metrics = RunningMetrics()
    observation_index = 0

    async for obs in stream:
        score = detector.score(obs)
        detector.learn(obs)
        drift_detector.update(score)
        drift_event_flag = drift_detector.drift_detected
        if drift_event_flag:
            detector.reset()
        alert = score > anomaly_threshold
        metrics.update(ground_truth=(obs.label != "normal"), predicted=alert)

        if state is not None:
            state["total_observations"] = observation_index + 1
            state["total_anomalies_detected"] = state.get("total_anomalies_detected", 0) + (1 if alert else 0)
            state["total_drift_events"] = state.get("total_drift_events", 0) + (1 if drift_event_flag else 0)
            state["current_precision"] = metrics.precision
            state["current_recall"] = metrics.recall

        msg = _broadcast_message(
            obs=obs,
            anomaly_score=score,
            alert=alert,
            drift_event=drift_event_flag,
            running_precision=metrics.precision,
            running_recall=metrics.recall,
            observation_index=observation_index,
        )
        msg["total_anomalies_detected"] = state["total_anomalies_detected"] if state else 0
        msg["total_drift_events"] = state["total_drift_events"] if state else 0
        await broadcaster(msg)
        observation_index += 1
