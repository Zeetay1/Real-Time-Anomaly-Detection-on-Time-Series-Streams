"""Online anomaly scorer using River HalfSpaceTrees."""

from river import anomaly, compose, preprocessing

from src.stream.models import Observation

# Normalize raw River score (unbounded, high = anomaly) to [0, 1]
def _normalize_score(raw: float) -> float:
    return min(1.0, raw / (raw + 1.0))


def _observation_to_dict(obs: Observation) -> dict[str, float]:
    return {
        "temperature": obs.temperature,
        "pressure": obs.pressure,
        "vibration": obs.vibration,
    }


def _make_pipeline(seed: int = 42, n_trees: int = 10, height: int = 6, window_size: int = 100):
    return compose.Pipeline(
        preprocessing.MinMaxScaler(),
        anomaly.HalfSpaceTrees(
            n_trees=n_trees,
            height=height,
            window_size=window_size,
            seed=seed,
        ),
    )


class AnomalyDetector:
    """Online anomaly scorer: one observation at a time, returns score in [0, 1], supports reset."""

    def __init__(
        self,
        threshold: float = 0.5,
        seed: int = 42,
        n_trees: int = 10,
        height: int = 6,
        window_size: int = 100,
    ) -> None:
        self.threshold = threshold
        self._seed = seed
        self._n_trees = n_trees
        self._height = height
        self._window_size = window_size
        self._model = _make_pipeline(seed=seed, n_trees=n_trees, height=height, window_size=window_size)

    def score(self, obs: Observation) -> float:
        """Return anomaly score in [0, 1]. High = more anomalous."""
        x = _observation_to_dict(obs)
        raw = self._model.score_one(x)
        return _normalize_score(raw)

    def learn(self, obs: Observation) -> None:
        """Update model with one observation."""
        x = _observation_to_dict(obs)
        self._model.learn_one(x)

    def reset(self) -> None:
        """Reset internal state (e.g. after drift)."""
        self._model = _make_pipeline(
            seed=self._seed,
            n_trees=self._n_trees,
            height=self._height,
            window_size=self._window_size,
        )
