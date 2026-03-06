"""Phase 1: Stream simulator tests."""

import asyncio
import statistics

import pytest

from src.stream.generator import generate_stream
from src.stream.models import Observation

# Baseline from generator
BASELINE_TEMP = 25.0
BASELINE_PRESSURE = 101.3
BASELINE_VIBRATION = 0.5
NOISE_SIGMA = 0.5


@pytest.mark.asyncio
async def test_generator_is_async():
    """The generator is async: confirmed by consuming it with async for."""
    count = 0
    async for obs in generate_stream(
        phase_a_length=10,
        phase_b_length=5,
        phase_c_length=10,
        seed=42,
    ):
        assert isinstance(obs, Observation)
        assert obs.timestamp >= 0
        assert obs.label in ("normal", "point_anomaly", "contextual_anomaly")
        count += 1
    assert count == 25


@pytest.mark.asyncio
async def test_phase_a_normality(stream_params_phase_a_only):
    """Phase A observations are statistically normal: means and variances match baselines."""
    obs_list: list[Observation] = []
    async for obs in generate_stream(**stream_params_phase_a_only):
        obs_list.append(obs)
    assert len(obs_list) == 200
    assert all(o.label == "normal" for o in obs_list)

    temps = [o.temperature for o in obs_list]
    pressures = [o.pressure for o in obs_list]
    vibrations = [o.vibration for o in obs_list]

    # Means within tolerance of baseline (allow for sampling variance)
    assert abs(statistics.mean(temps) - BASELINE_TEMP) < 0.15
    assert abs(statistics.mean(pressures) - BASELINE_PRESSURE) < 0.15
    assert abs(statistics.mean(vibrations) - BASELINE_VIBRATION) < 0.15

    # Variances in expected ballpark (noise sigma^2 ~ 0.25, sample var can vary)
    var_t = statistics.variance(temps)
    var_p = statistics.variance(pressures)
    var_v = statistics.variance(vibrations)
    assert 0.1 < var_t < 1.0
    assert 0.1 < var_p < 1.0
    assert 0.1 < var_v < 1.0


@pytest.mark.asyncio
async def test_phase_b_drift(stream_params_short):
    """Phase B observations show a measurable distribution shift by end of phase."""
    params = dict(stream_params_short)
    phase_a_len = params["phase_a_length"]
    phase_b_len = params["phase_b_length"]
    drift_mag = params["drift_magnitude"]

    obs_list: list[Observation] = []
    async for obs in generate_stream(**params):
        obs_list.append(obs)

    phase_a_temps = [o.temperature for o in obs_list[:phase_a_len]]
    phase_b_end_temps = [o.temperature for o in obs_list[phase_a_len + phase_b_len - 50 : phase_a_len + phase_b_len]]

    mean_a = statistics.mean(phase_a_temps)
    mean_b_end = statistics.mean(phase_b_end_temps)
    # Allow for sampling variance: require a measurable positive shift
    assert mean_b_end - mean_a >= drift_mag * 0.25, (
        "End of Phase B mean should shift; got mean_a=%s mean_b_end=%s" % (mean_a, mean_b_end)
    )


@pytest.mark.asyncio
async def test_phase_c_anomaly_count(stream_params_short):
    """Phase C contains the configured number of injected anomalies at the configured rate."""
    params = dict(stream_params_short)
    phase_c_len = params["phase_c_length"]
    anomaly_rate = params["anomaly_rate"]
    phase_a_len = params["phase_a_length"]
    phase_b_len = params["phase_b_length"]

    obs_list: list[Observation] = []
    async for obs in generate_stream(**params):
        obs_list.append(obs)

    phase_c = obs_list[phase_a_len + phase_b_len :]
    assert len(phase_c) == phase_c_len
    anomalies = [o for o in phase_c if o.label != "normal"]
    expected_min = int(phase_c_len * anomaly_rate * 0.5)
    expected_max = int(phase_c_len * anomaly_rate * 2) + 10
    assert expected_min <= len(anomalies) <= expected_max, (
        f"Expected roughly {phase_c_len * anomaly_rate:.0f} anomalies, got {len(anomalies)}"
    )
    point_count = sum(1 for o in phase_c if o.label == "point_anomaly")
    contextual_count = sum(1 for o in phase_c if o.label == "contextual_anomaly")
    assert point_count + contextual_count == len(anomalies)
