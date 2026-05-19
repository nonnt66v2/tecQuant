from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class QFPUFConfig:
    num_qubits: int
    depth: int
    seed: int
    shots: int
    auth_threshold: int
    flip_probability: float
    output_dir: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QFPUFConfig":
        return cls(
            num_qubits=int(data.get("num_qubits", 4)),
            depth=int(data.get("depth", 3)),
            seed=int(data.get("seed", 42)),
            shots=int(data.get("shots", 256)),
            auth_threshold=int(data.get("auth_threshold", 1)),
            flip_probability=float(data.get("flip_probability", 0.0)),
            output_dir=str(data.get("output_dir", "progetto/risultati/qfpuf")),
        )

    def validate(self) -> None:
        if self.num_qubits <= 0:
            raise ValueError("num_qubits must be > 0")
        if self.depth <= 0:
            raise ValueError("depth must be > 0")
        if self.shots <= 0:
            raise ValueError("shots must be > 0")
        if self.auth_threshold < 0:
            raise ValueError("auth_threshold must be >= 0")
        if not 0.0 <= self.flip_probability <= 1.0:
            raise ValueError("flip_probability must be in [0, 1]")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_qubits": self.num_qubits,
            "depth": self.depth,
            "seed": self.seed,
            "shots": self.shots,
            "auth_threshold": self.auth_threshold,
            "flip_probability": self.flip_probability,
            "output_dir": self.output_dir,
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))


def load_config(path: Path) -> QFPUFConfig:
    data = json.loads(path.read_text())
    config = QFPUFConfig.from_dict(data)
    config.validate()
    return config
