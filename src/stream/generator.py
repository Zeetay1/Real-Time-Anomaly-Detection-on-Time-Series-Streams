"""Synthetic multivariate stream generator with ground truth labels."""

import asyncio
import itertools
import random
from collections.abc import AsyncIterator, Iterator
from typing import Any

from src.stream.models import Observation, Label

# Baseline means for Phase A
BASELINE_TEMP = 25.0
BASELINE_PRESSURE = 101.3
BASELINE_VIBRATION = 0.5
# Standard deviation for correlated noise
NOISE_SIGMA = 0.5
# Correlation: shared latent factor weight
LATENT_WEIGHT = 0.7
INDEPENDENT_WEIGHT = (1 - LATENT_WEIGHT**2) ** 0.5


def _correlated_noise(rng: random.Random) -> tuple[float, float, float]:
    """Generate correlated noise: one latent factor, then map to three sensors."""
    z = rng.gauss(0, NOISE_SIGMA)
    eps_t = rng.gauss(0, NOISE_SIGMA * INDEPENDENT_WEIGHT)
    eps_p = rng.gauss(0, NOISE_SIGMA * INDEPENDENT_WEIGHT)
    eps_v = rng.gauss(0, NOISE_SIGMA * INDEPENDENT_WEIGHT)
    return (
        LATENT_WEIGHT * z + eps_t,
        LATENT_WEIGHT * z + eps_p,
        LATENT_WEIGHT * z + eps_v,
    )


def _generate_sync(
    *,
    phase_a_length: int = 300,
    phase_b_length: int = 200,
    phase_c_length: int = 300,
    drift_magnitude: float = 0.3,
    anomaly_rate: float = 0.05,
    point_ratio: float = 0.6,
    seed: int = 42,
) -> Iterator[Observation]:
    rng = random.Random(seed)
    t = 0.0
    # Phase A: normal baseline
    for i in range(phase_a_length):
        nt, np_, nv = _correlated_noise(rng)
        yield Observation(
            timestamp=t,
            temperature=BASELINE_TEMP + nt,
            pressure=BASELINE_PRESSURE + np_,
            vibration=BASELINE_VIBRATION + nv,
            label="normal",
        )
        t += 1.0

    # Phase B: linear drift
    for i in range(phase_b_length):
        alpha = (i + 1) / phase_b_length
        mt = BASELINE_TEMP + drift_magnitude * alpha
        mp = BASELINE_PRESSURE + drift_magnitude * alpha
        mv = BASELINE_VIBRATION + drift_magnitude * alpha
        nt, np_, nv = _correlated_noise(rng)
        yield Observation(
            timestamp=t,
            temperature=mt + nt,
            pressure=mp + np_,
            vibration=mv + nv,
            label="normal",
        )
        t += 1.0

    # Post-drift means
    end_temp = BASELINE_TEMP + drift_magnitude
    end_pressure = BASELINE_PRESSURE + drift_magnitude
    end_vibration = BASELINE_VIBRATION + drift_magnitude

    # Phase C: post-drift + anomalies
    # Anomaly injection: every ~1/anomaly_rate observations on average
    obs_count = 0
    anomaly_choice = itertools.cycle(["point_anomaly", "contextual_anomaly"])
    next_anomaly_step = max(1, int(rng.expovariate(anomaly_rate)))

    for i in range(phase_c_length):
        obs_count += 1
        nt, np_, nv = _correlated_noise(rng)

        if obs_count >= next_anomaly_step:
            # Inject anomaly; pick type by point_ratio
            if rng.random() < point_ratio:
                label: Label = "point_anomaly"
                # Spike in one or more sensors (3-5 sigma)
                spike = rng.uniform(3.0, 5.0) * NOISE_SIGMA
                which = rng.sample([0, 1, 2], k=rng.randint(1, 3))
                if 0 in which:
                    nt += spike * rng.choice([-1, 1])
                if 1 in which:
                    np_ += spike * rng.choice([-1, 1])
                if 2 in which:
                    nv += spike * rng.choice([-1, 1])
            else:
                label = "contextual_anomaly"
                # Jointly rare: high temp + low pressure (opposite to correlation)
                nt = 1.5 * NOISE_SIGMA
                np_ = -1.5 * NOISE_SIGMA
                nv = 0.0  # normal for vibration
            next_anomaly_step = obs_count + max(1, int(rng.expovariate(anomaly_rate)))
        else:
            label = "normal"

        yield Observation(
            timestamp=t,
            temperature=end_temp + nt,
            pressure=end_pressure + np_,
            vibration=end_vibration + nv,
            label=label,
        )
        t += 1.0


async def generate_stream(
    *,
    phase_a_length: int = 300,
    phase_b_length: int = 200,
    phase_c_length: int = 300,
    drift_magnitude: float = 0.3,
    anomaly_rate: float = 0.05,
    point_ratio: float = 0.6,
    delay: float = 0.0,
    seed: int = 42,
) -> AsyncIterator[Observation]:
    """Async generator yielding one observation at a time with optional delay."""
    sync_gen = _generate_sync(
        phase_a_length=phase_a_length,
        phase_b_length=phase_b_length,
        phase_c_length=phase_c_length,
        drift_magnitude=drift_magnitude,
        anomaly_rate=anomaly_rate,
        point_ratio=point_ratio,
        seed=seed,
    )
    for obs in sync_gen:
        if delay > 0:
            await asyncio.sleep(delay)
        yield obs
