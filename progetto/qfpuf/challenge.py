from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Tuple, Dict, Any, List


@dataclass(frozen=True)
class Challenge:
    bitstring: str
    angles: Tuple[float, ...]

    def validate(self, num_qubits: int) -> None:
        if len(self.bitstring) != num_qubits:
            raise ValueError("Challenge bitstring length does not match num_qubits")
        if len(self.angles) != num_qubits:
            raise ValueError("Challenge angles length does not match num_qubits")
        if any(bit not in {"0", "1"} for bit in self.bitstring):
            raise ValueError("Challenge bitstring must contain only 0/1 values")

    def to_dict(self) -> Dict[str, Any]:
        return {"bitstring": self.bitstring, "angles": list(self.angles)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Challenge":
        return cls(
            bitstring=str(data.get("bitstring", "")),
            angles=tuple(float(angle) for angle in data.get("angles", [])),
        )


def generate_challenges(
    num_qubits: int,
    count: int,
    seed: int,
    angle_min: float = 0.0,
    angle_max: float = 2 * math.pi,
) -> List[Challenge]:
    rng = random.Random(seed)
    challenges: List[Challenge] = []
    for _ in range(count):
        bitstring = "".join(rng.choice("01") for _ in range(num_qubits))
        angles = tuple(rng.uniform(angle_min, angle_max) for _ in range(num_qubits))
        challenges.append(Challenge(bitstring=bitstring, angles=angles))
    return challenges
