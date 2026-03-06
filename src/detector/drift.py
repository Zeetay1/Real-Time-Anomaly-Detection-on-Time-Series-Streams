"""Drift detector that monitors the anomaly score stream (not raw sensor data)."""

from river import drift


class DriftDetector:
    """Wraps River ADWIN to monitor anomaly scores and emit reset signals."""

    def __init__(self, delta: float = 0.002, grace_period: int = 30) -> None:
        self._adwin = drift.ADWIN(delta=delta, grace_period=grace_period)
        self._last_drift_detected = False

    def update(self, anomaly_score: float) -> bool:
        """Update with one anomaly score. Returns True if drift was detected this step."""
        self._adwin.update(anomaly_score)
        self._last_drift_detected = self._adwin.drift_detected
        return self._last_drift_detected

    @property
    def drift_detected(self) -> bool:
        """Whether drift was detected on the last update."""
        return self._last_drift_detected
