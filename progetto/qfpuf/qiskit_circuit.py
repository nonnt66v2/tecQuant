from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel

from .challenge import Challenge


@dataclass(frozen=True)
class ChallengeResult:
    counts: Dict[str, int]
    probabilities: Dict[str, float]
    response: str
    shots: int


def build_challenge_circuit(
    num_qubits: int, depth: int, challenge: Challenge
) -> QuantumCircuit:
    challenge.validate(num_qubits)
    circuit = QuantumCircuit(num_qubits, name="qfpuf_challenge")

    circuit.h(range(num_qubits))

    for _ in range(depth):
        for qubit in range(num_qubits - 1):
            circuit.cx(qubit, qubit + 1)

        for qubit, angle in enumerate(challenge.angles):
            signed_angle = angle if challenge.bitstring[qubit] == "0" else -angle
            circuit.ry(signed_angle, qubit)

    return circuit


def _prepare_measured_circuit(circuit: QuantumCircuit) -> QuantumCircuit:
    measured = circuit.copy()
    if measured.num_clbits == 0:
        measured.measure_all()
    return measured


def _select_response(counts: Dict[str, int]) -> str:
    if not counts:
        raise ValueError("Empty counts from simulation")
    max_count = max(counts.values())
    candidates = sorted(k for k, v in counts.items() if v == max_count)
    return candidates[0]


def _counts_to_probabilities(counts: Dict[str, int], shots: int) -> Dict[str, float]:
    return {bitstring: count / shots for bitstring, count in counts.items()}


def simulate_challenge(
    circuit: QuantumCircuit,
    shots: int = 256,
    seed: int | None = None,
    noise_model: Optional[NoiseModel] = None,
) -> ChallengeResult:
    measured = _prepare_measured_circuit(circuit)
    simulator = AerSimulator(seed_simulator=seed, noise_model=noise_model)
    transpiled = transpile(measured, simulator, seed_transpiler=seed)
    result = simulator.run(transpiled, shots=shots).result()
    counts = result.get_counts(transpiled)
    response = _select_response(counts)
    probabilities = _counts_to_probabilities(counts, shots)
    return ChallengeResult(
        counts=counts, probabilities=probabilities, response=response, shots=shots
    )
