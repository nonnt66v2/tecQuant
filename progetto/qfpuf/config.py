from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from .challenge import Challenge


@dataclass(frozen=True)
class ChallengeConfig:
    count: int
    seed: int
    angle_min: float
    angle_max: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChallengeConfig":
        return cls(
            count=int(data.get("count", 8)),
            seed=int(data.get("seed", 123)),
            angle_min=float(data.get("angle_min", 0.0)),
            angle_max=float(data.get("angle_max", 6.283185307179586)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "seed": self.seed,
            "angle_min": self.angle_min,
            "angle_max": self.angle_max,
        }


@dataclass(frozen=True)
class NoiseConfig:
    depolarizing_1q: float
    depolarizing_2q: float
    t1: float
    t2: float
    gate_time_1q: float
    gate_time_2q: float
    variation: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NoiseConfig":
        return cls(
            depolarizing_1q=float(data.get("depolarizing_1q", 0.001)),
            depolarizing_2q=float(data.get("depolarizing_2q", 0.01)),
            t1=float(data.get("t1", 50000.0)),
            t2=float(data.get("t2", 70000.0)),
            gate_time_1q=float(data.get("gate_time_1q", 50.0)),
            gate_time_2q=float(data.get("gate_time_2q", 300.0)),
            variation=float(data.get("variation", 0.1)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "depolarizing_1q": self.depolarizing_1q,
            "depolarizing_2q": self.depolarizing_2q,
            "t1": self.t1,
            "t2": self.t2,
            "gate_time_1q": self.gate_time_1q,
            "gate_time_2q": self.gate_time_2q,
            "variation": self.variation,
        }


@dataclass(frozen=True)
class QFPUFConfig:
    num_qubits: int
    depth: int
    seed: int
    shots: int
    challenge_config: ChallengeConfig
    challenges: Optional[Tuple[Challenge, ...]]
    enrollment_instance_seed: int
    verification_instance_seed: int
    noise: NoiseConfig
    fidelity_threshold: float
    qber_threshold: float
    output_dir: str
    enrollment_db_path: str
    verification_report_path: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QFPUFConfig":
        output_dir = str(data.get("output_dir", "progetto/risultati/qfpuf"))
        challenge_data = data.get("challenges")
        challenges = None
        if challenge_data:
            challenges = tuple(Challenge.from_dict(item) for item in challenge_data)
        challenge_config = ChallengeConfig.from_dict(data.get("challenge_config", {}))
        noise = NoiseConfig.from_dict(data.get("noise", {}))
        return cls(
            num_qubits=int(data.get("num_qubits", 4)),
            depth=int(data.get("depth", 1)),
            seed=int(data.get("seed", 42)),
            shots=int(data.get("shots", 256)),
            challenge_config=challenge_config,
            challenges=challenges,
            enrollment_instance_seed=int(
                data.get("enrollment_instance_seed", data.get("seed", 42))
            ),
            verification_instance_seed=int(
                data.get("verification_instance_seed", data.get("seed", 42))
            ),
            noise=noise,
            fidelity_threshold=float(data.get("fidelity_threshold", 0.9)),
            qber_threshold=float(data.get("qber_threshold", 0.2)),
            output_dir=output_dir,
            enrollment_db_path=str(
                data.get(
                    "enrollment_db_path",
                    f"{output_dir}/qfpuf_enrollment.json",
                )
            ),
            verification_report_path=str(
                data.get(
                    "verification_report_path",
                    f"{output_dir}/qfpuf_verification.json",
                )
            ),
        )

    def validate(self) -> None:
        if self.num_qubits <= 0:
            raise ValueError("num_qubits must be > 0")
        if self.depth <= 0:
            raise ValueError("depth must be > 0")
        if self.shots <= 0:
            raise ValueError("shots must be > 0")
        if self.challenge_config.count <= 0:
            raise ValueError("challenge_config.count must be > 0")
        if self.challenge_config.angle_min >= self.challenge_config.angle_max:
            raise ValueError("challenge_config.angle_min must be < angle_max")
        if not 0.0 <= self.noise.variation <= 1.0:
            raise ValueError("noise.variation must be in [0, 1]")
        if self.fidelity_threshold < 0.0 or self.fidelity_threshold > 1.0:
            raise ValueError("fidelity_threshold must be in [0, 1]")
        if self.qber_threshold < 0.0 or self.qber_threshold > 1.0:
            raise ValueError("qber_threshold must be in [0, 1]")
        if self.challenges:
            for challenge in self.challenges:
                challenge.validate(self.num_qubits)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_qubits": self.num_qubits,
            "depth": self.depth,
            "seed": self.seed,
            "shots": self.shots,
            "challenge_config": self.challenge_config.to_dict(),
            "challenges": [challenge.to_dict() for challenge in self.challenges]
            if self.challenges
            else None,
            "enrollment_instance_seed": self.enrollment_instance_seed,
            "verification_instance_seed": self.verification_instance_seed,
            "noise": self.noise.to_dict(),
            "fidelity_threshold": self.fidelity_threshold,
            "qber_threshold": self.qber_threshold,
            "output_dir": self.output_dir,
            "enrollment_db_path": self.enrollment_db_path,
            "verification_report_path": self.verification_report_path,
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))


def load_config(path: Path) -> QFPUFConfig:
    data = json.loads(path.read_text())
    config = QFPUFConfig.from_dict(data)
    config.validate()
    return config
