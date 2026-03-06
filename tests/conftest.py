"""Shared pytest fixtures."""

import pytest

from src.stream.generator import generate_stream
from src.stream.models import Observation


@pytest.fixture
def stream_params_short():
    """Short phase lengths for fast tests."""
    return {
        "phase_a_length": 100,
        "phase_b_length": 80,
        "phase_c_length": 100,
        "drift_magnitude": 0.3,
        "anomaly_rate": 0.08,
        "point_ratio": 0.6,
        "delay": 0.0,
        "seed": 42,
    }


@pytest.fixture
def stream_params_phase_a_only():
    """Phase A only for normality tests."""
    return {
        "phase_a_length": 200,
        "phase_b_length": 0,
        "phase_c_length": 0,
        "drift_magnitude": 0.3,
        "anomaly_rate": 0.05,
        "point_ratio": 0.6,
        "delay": 0.0,
        "seed": 123,
    }
