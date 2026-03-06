"""Phase 2: Online anomaly detector and drift handling tests."""

import asyncio

import pytest

from src.detector.anomaly import AnomalyDetector
from src.detector.drift import DriftDetector
from src.detector.metrics import RunningMetrics
from src.stream.generator import generate_stream
from src.stream.models import Observation


@pytest.mark.asyncio
async def test_anomaly_scores_higher_for_injected_anomalies():
    """The anomaly scorer produces higher scores for injected anomalies than for normal on average."""
    detector = AnomalyDetector(threshold=0.5, window_size=50, n_trees=5, height=5)
    scores_normal: list[float] = []
    scores_anomaly: list[float] = []

    async for obs in generate_stream(
        phase_a_length=80,
        phase_b_length=60,
        phase_c_length=100,
        anomaly_rate=0.12,
        seed=42,
    ):
        score = detector.score(obs)
        detector.learn(obs)
        if obs.label == "normal":
            scores_normal.append(score)
        else:
            scores_anomaly.append(score)

    assert len(scores_anomaly) >= 5, "Need some anomalies in stream"
    assert sum(scores_anomaly) / len(scores_anomaly) > sum(scores_normal) / len(scores_normal), (
        "Mean score for anomalies should exceed mean score for normal"
    )


@pytest.mark.asyncio
async def test_drift_detector_emits_reset_in_phase_b():
    """The drift detector emits at least one reset signal during Phase B; none during Phase A."""
    detector = AnomalyDetector(threshold=0.5, window_size=40, n_trees=5, height=5)
    drift_det = DriftDetector(delta=0.01, grace_period=20)
    phase_a_len = 80
    phase_b_len = 100
    resets_in_a = 0
    resets_in_b = 0
    idx = 0

    async for obs in generate_stream(
        phase_a_length=phase_a_len,
        phase_b_length=phase_b_len,
        phase_c_length=50,
        drift_magnitude=0.4,
        seed=123,
    ):
        score = detector.score(obs)
        detector.learn(obs)
        if drift_det.update(score):
            if idx < phase_a_len:
                resets_in_a += 1
            elif idx < phase_a_len + phase_b_len:
                resets_in_b += 1
            detector.reset()
        idx += 1

    assert resets_in_a == 0, "No reset during Phase A"
    assert resets_in_b >= 1, "At least one reset during Phase B"


@pytest.mark.asyncio
async def test_no_reset_during_phase_a():
    """No reset signal is emitted during Phase A (normal period)."""
    detector = AnomalyDetector(threshold=0.5, window_size=50, n_trees=5, height=5)
    drift_det = DriftDetector(delta=0.002, grace_period=50)
    phase_a_len = 120
    any_reset_in_a = False

    async for obs in generate_stream(
        phase_a_length=phase_a_len,
        phase_b_length=0,
        phase_c_length=0,
        seed=999,
    ):
        score = detector.score(obs)
        detector.learn(obs)
        if drift_det.update(score):
            any_reset_in_a = True

    assert not any_reset_in_a, "No reset should occur in Phase A"


@pytest.mark.asyncio
async def test_running_precision_recall_hand_labeled():
    """Running precision and recall are computed correctly on a hand-labeled mini-stream."""
    # Build 20 hand-labeled (ground_truth, predicted) and expected P/R
    # Format: (is_anomaly_gt, predicted_positive)
    data = [
        (True, True),   # TP
        (True, True),   # TP
        (True, False),  # FN
        (False, False), # TN
        (False, True),  # FP
        (False, False), # TN
        (True, True),   # TP
        (False, False), # TN
        (False, True),  # FP
        (True, False),  # FN
        (True, True),   # TP
        (False, False), # TN
        (False, False), # TN
        (True, True),   # TP
        (False, True),  # FP
        (True, False),  # FN
        (False, False), # TN
        (True, True),   # TP
        (False, False), # TN
        (False, True),  # FP
    ]
    # TP=6, FP=4, FN=3, TN=7
    # precision = 6/(6+4) = 0.6, recall = 6/(6+3) = 2/3
    expected_precision = 6 / 10
    expected_recall = 6 / 9

    metrics = RunningMetrics()
    for gt, pred in data:
        metrics.update(ground_truth=gt, predicted=pred)

    assert abs(metrics.precision - expected_precision) < 1e-9
    assert abs(metrics.recall - expected_recall) < 1e-9
