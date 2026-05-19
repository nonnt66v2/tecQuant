from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any

from .config import QFPUFConfig
from .netsquid_auth import authenticate_response
from .qiskit_circuit import build_challenge_circuit, simulate_challenge


def run_pipeline(config: QFPUFConfig) -> Dict[str, Any]:
    config.validate()

    circuit = build_challenge_circuit(
        num_qubits=config.num_qubits, depth=config.depth, seed=config.seed
    )
    challenge = simulate_challenge(circuit, shots=config.shots, seed=config.seed)

    expected_response = challenge.response
    received_response = challenge.response
    auth = authenticate_response(
        expected_response=expected_response,
        received_response=received_response,
        threshold=config.auth_threshold,
        seed=config.seed,
        flip_probability=config.flip_probability,
    )

    return {
        "config": config.to_dict(),
        "challenge": {
            "response": challenge.response,
            "counts": challenge.counts,
            "shots": challenge.shots,
            "num_qubits": config.num_qubits,
            "depth": config.depth,
        },
        "authentication": asdict(auth),
    }


def write_results(payload: Dict[str, Any], output_dir: Path, seed: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"qfpuf_result_seed{seed}.json"
    output_path = output_dir / file_name
    output_path.write_text(json.dumps(payload, indent=2))
    return output_path
