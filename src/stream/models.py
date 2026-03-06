"""Data models for the synthetic stream."""

from dataclasses import dataclass
from typing import Literal

Label = Literal["normal", "point_anomaly", "contextual_anomaly"]


@dataclass(frozen=True)
class Observation:
    """A single multivariate sensor observation with ground truth label."""

    timestamp: float
    temperature: float
    pressure: float
    vibration: float
    label: Label
