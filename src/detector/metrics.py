"""Running precision and recall against ground truth labels."""


class RunningMetrics:
    """Running TP, FP, TN, FN; precision and recall updated after every observation."""

    __slots__ = ("_tp", "_fp", "_tn", "_fn")

    def __init__(self) -> None:
        self._tp = 0
        self._fp = 0
        self._tn = 0
        self._fn = 0

    def update(self, ground_truth: bool, predicted: bool) -> None:
        """Update counts with one observation. ground_truth/predicted: True = anomaly."""
        if ground_truth and predicted:
            self._tp += 1
        elif not ground_truth and predicted:
            self._fp += 1
        elif ground_truth and not predicted:
            self._fn += 1
        else:
            self._tn += 1

    @property
    def precision(self) -> float:
        if self._tp + self._fp == 0:
            return 0.0
        return self._tp / (self._tp + self._fp)

    @property
    def recall(self) -> float:
        if self._tp + self._fn == 0:
            return 0.0
        return self._tp / (self._tp + self._fn)

    @property
    def tp(self) -> int:
        return self._tp

    @property
    def fp(self) -> int:
        return self._fp

    @property
    def fn(self) -> int:
        return self._fn

    @property
    def tn(self) -> int:
        return self._tn
