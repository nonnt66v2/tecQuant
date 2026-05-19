from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


@dataclass(frozen=True)
class ChallengeResult:
    counts: Dict[str, int]
    response: str
    shots: int


def build_challenge_circuit(num_qubits: int, depth: int, seed: int) -> QuantumCircuit:
    rng = random.Random(seed)
    circuit = QuantumCircuit(num_qubits, name="qfpuf_challenge")

    for _ in range(depth):
        for qubit in range(num_qubits):
            axis = rng.choice(["rx", "ry", "rz"])
            angle = rng.random() * 2 * math.pi
            getattr(circuit, axis)(angle, qubit)

        for qubit in range(0, num_qubits - 1, 2):
            if rng.random() < 0.7:
                circuit.cx(qubit, qubit + 1)

        if num_qubits > 2 and rng.random() < 0.5:
            q1, q2 = rng.sample(range(num_qubits), 2)
            circuit.cz(q1, q2)

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


def simulate_challenge(
    circuit: QuantumCircuit, shots: int = 256, seed: int | None = None
) -> ChallengeResult:
    measured = _prepare_measured_circuit(circuit)
    simulator = AerSimulator(seed_simulator=seed)
    transpiled = transpile(measured, simulator, seed_transpiler=seed)
    result = simulator.run(transpiled, shots=shots).result()
    counts = result.get_counts(transpiled)
    response = _select_response(counts)
    return ChallengeResult(counts=counts, response=response, shots=shots)
