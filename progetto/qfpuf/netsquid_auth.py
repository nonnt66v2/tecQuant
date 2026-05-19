from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

try:
    import netsquid as ns
except ImportError:  # pragma: no cover - optional dependency
    ns = None


@dataclass(frozen=True)
class AuthenticationResult:
    accepted: bool
    distance: int
    threshold: int
    expected_response: str
    received_response: str
    used_netsquid: bool


def _seed_netsquid(seed: int) -> bool:
    if ns is None:
        return False
    if hasattr(ns, "sim_reset"):
        ns.sim_reset()
    if hasattr(ns, "set_random_state"):
        ns.set_random_state(seed)
        return True
    return False


def _apply_noise(response: str, flip_probability: float, seed: Optional[int]) -> str:
    if flip_probability <= 0:
        return response
    rng = random.Random(seed)
    bits = []
    for bit in response:
        if rng.random() < flip_probability:
            bits.append("1" if bit == "0" else "0")
        else:
            bits.append(bit)
    return "".join(bits)


def _hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        raise ValueError("Responses must have the same length")
    return sum(a != b for a, b in zip(left, right))


def authenticate_response(
    expected_response: str,
    received_response: str,
    threshold: int,
    seed: Optional[int] = None,
    flip_probability: float = 0.0,
) -> AuthenticationResult:
    used_netsquid = False
    if seed is not None:
        used_netsquid = _seed_netsquid(seed)

    noisy_response = _apply_noise(received_response, flip_probability, seed)
    distance = _hamming_distance(expected_response, noisy_response)
    accepted = distance <= threshold

    return AuthenticationResult(
        accepted=accepted,
        distance=distance,
        threshold=threshold,
        expected_response=expected_response,
        received_response=noisy_response,
        used_netsquid=used_netsquid,
    )
