from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from .challenge import Challenge, generate_challenges
from .config import QFPUFConfig
from .noise import build_noise_model
from .qiskit_circuit import build_challenge_circuit, simulate_challenge


def _resolve_challenges(config: QFPUFConfig) -> List[Challenge]:
    if config.challenges:
        return list(config.challenges)
    return generate_challenges(
        num_qubits=config.num_qubits,
        count=config.challenge_config.count,
        seed=config.challenge_config.seed,
        angle_min=config.challenge_config.angle_min,
        angle_max=config.challenge_config.angle_max,
    )


def _classical_fidelity(
    expected: Dict[str, float], measured: Dict[str, float]
) -> float:
    keys = set(expected) | set(measured)
    return sum(math.sqrt(expected.get(key, 0.0) * measured.get(key, 0.0)) for key in keys)


def _qber(expected_response: str, received_response: str) -> float:
    if len(expected_response) != len(received_response):
        raise ValueError("Responses must have the same length")
    distance = sum(a != b for a, b in zip(expected_response, received_response))
    return distance / len(expected_response)


def run_enrollment(config: QFPUFConfig) -> Dict[str, Any]:
    config.validate()
    challenges = _resolve_challenges(config)
    noise_model, noise_parameters = build_noise_model(
        config.noise, config.enrollment_instance_seed
    )

    entries = []
    for index, challenge in enumerate(challenges):
        circuit = build_challenge_circuit(config.num_qubits, config.depth, challenge)
        result = simulate_challenge(
            circuit,
            shots=config.shots,
            seed=config.seed + index,
            noise_model=noise_model,
        )
        entries.append(
            {
                "challenge": challenge.to_dict(),
                "counts": result.counts,
                "probabilities": result.probabilities,
                "response": result.response,
                "shots": result.shots,
            }
        )

    return {
        "num_qubits": config.num_qubits,
        "depth": config.depth,
        "shots": config.shots,
        "noise_parameters": noise_parameters,
        "entries": entries,
    }


def run_verification(
    config: QFPUFConfig, enrollment: Dict[str, Any]
) -> Dict[str, Any]:
    config.validate()
    noise_model, noise_parameters = build_noise_model(
        config.noise, config.verification_instance_seed
    )

    results = []
    fidelity_values = []
    qber_values = []
    entries = enrollment.get("entries", [])

    for index, entry in enumerate(entries):
        challenge = Challenge.from_dict(entry["challenge"])
        circuit = build_challenge_circuit(config.num_qubits, config.depth, challenge)
        result = simulate_challenge(
            circuit,
            shots=config.shots,
            seed=config.seed + 1000 + index,
            noise_model=noise_model,
        )
        expected_probs = entry.get("probabilities", {})
        fidelity = _classical_fidelity(expected_probs, result.probabilities)
        qber = _qber(entry["response"], result.response)
        fidelity_values.append(fidelity)
        qber_values.append(qber)
        results.append(
            {
                "challenge": challenge.to_dict(),
                "expected_response": entry["response"],
                "received_response": result.response,
                "fidelity": fidelity,
                "qber": qber,
                "counts": result.counts,
                "probabilities": result.probabilities,
            }
        )

    avg_fidelity = sum(fidelity_values) / len(fidelity_values) if fidelity_values else 0.0
    avg_qber = sum(qber_values) / len(qber_values) if qber_values else 1.0
    accepted = avg_fidelity >= config.fidelity_threshold and avg_qber <= config.qber_threshold

    return {
        "noise_parameters": noise_parameters,
        "average_fidelity": avg_fidelity,
        "average_qber": avg_qber,
        "accepted": accepted,
        "thresholds": {
            "fidelity": config.fidelity_threshold,
            "qber": config.qber_threshold,
        },
        "results": results,
    }


def run_pipeline(config: QFPUFConfig, mode: str = "full") -> Dict[str, Any]:
    config.validate()
    mode = mode.lower()

    if mode not in {"full", "enroll", "verify"}:
        raise ValueError("mode must be one of: full, enroll, verify")

    enrollment_payload: Optional[Dict[str, Any]] = None
    verification_payload: Optional[Dict[str, Any]] = None

    if mode in {"full", "enroll"}:
        enrollment_payload = run_enrollment(config)

    if mode in {"full", "verify"}:
        if enrollment_payload is None:
            enrollment_payload = read_enrollment(Path(config.enrollment_db_path))
        verification_payload = run_verification(config, enrollment_payload)

    return {
        "config": config.to_dict(),
        "enrollment": enrollment_payload,
        "verification": verification_payload,
        "mode": mode,
    }


def write_enrollment(enrollment: Dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(enrollment, indent=2))
    return output_path


def read_enrollment(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def write_verification(report: Dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    return output_path
