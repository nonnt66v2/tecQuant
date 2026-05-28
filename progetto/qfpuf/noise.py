from __future__ import annotations

import random
from typing import Dict, Tuple

from qiskit_aer.noise import NoiseModel, depolarizing_error, thermal_relaxation_error

from .config import NoiseConfig


def _jitter(value: float, variation: float, rng: random.Random, minimum: float = 0.0) -> float:
    jittered = value * (1.0 + rng.uniform(-variation, variation))
    return max(minimum, jittered)


def build_noise_model(config: NoiseConfig, seed: int) -> Tuple[NoiseModel, Dict[str, float]]:
    rng = random.Random(seed)
    depolarizing_1q = _jitter(config.depolarizing_1q, config.variation, rng)
    depolarizing_2q = _jitter(config.depolarizing_2q, config.variation, rng)
    t1 = _jitter(config.t1, config.variation, rng, minimum=1.0)
    t2 = _jitter(config.t2, config.variation, rng, minimum=1.0)
    t2 = min(t2, 2.0 * t1)
    gate_time_1q = _jitter(config.gate_time_1q, config.variation, rng, minimum=1.0)
    gate_time_2q = _jitter(config.gate_time_2q, config.variation, rng, minimum=1.0)

    relaxation_1q = thermal_relaxation_error(t1, t2, gate_time_1q)
    relaxation_2q = thermal_relaxation_error(t1, t2, gate_time_2q).tensor(
        thermal_relaxation_error(t1, t2, gate_time_2q)
    )
    depol_1q = depolarizing_error(depolarizing_1q, 1)
    depol_2q = depolarizing_error(depolarizing_2q, 2)

    error_1q = depol_1q.compose(relaxation_1q)
    error_2q = depol_2q.compose(relaxation_2q)

    noise_model = NoiseModel()
    noise_model.add_all_qubit_quantum_error(error_1q, ["h", "ry"])
    noise_model.add_all_qubit_quantum_error(error_2q, ["cx"])

    return noise_model, {
        "depolarizing_1q": depolarizing_1q,
        "depolarizing_2q": depolarizing_2q,
        "t1": t1,
        "t2": t2,
        "gate_time_1q": gate_time_1q,
        "gate_time_2q": gate_time_2q,
        "variation": config.variation,
    }
