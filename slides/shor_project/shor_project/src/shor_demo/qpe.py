from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from collections import Counter
import math

from .qft import inverse_qft


def _binary_fraction_to_decimal(bitstring: str) -> float:
    value = 0.0
    for i, bit in enumerate(bitstring, start=1):
        value += int(bit) / (2 ** i)
    return value


def build_qpe_demo(counting_qubits: int = 4) -> QuantumCircuit:
    """
    Demo QPE per stimare theta = 1/3, usando U con autovalore e^(2πiθ).
    Si usa una controlled-phase su un eigenstate semplice.
    """
    total_qubits = counting_qubits + 1
    qc = QuantumCircuit(total_qubits, counting_qubits)

    # Counting register in superposition
    for q in range(counting_qubits):
        qc.h(q)

    # Eigenstate |1>
    target = counting_qubits
    qc.x(target)

    theta = 1 / 3
    lam = 2 * math.pi * theta

    # Controlled-U^(2^k)
    for control in range(counting_qubits):
        repetitions = 2 ** control
        for _ in range(repetitions):
            qc.cp(lam, control, target)

    qc.append(inverse_qft(counting_qubits), range(counting_qubits))
    qc.measure(range(counting_qubits), range(counting_qubits))
    return qc


def run_qpe_demo(shots: int = 2048) -> None:
    qc = build_qpe_demo(4)
    sim = AerSimulator()
    tqc = transpile(qc, sim)
    result = sim.run(tqc, shots=shots).result()
    counts = result.get_counts()

    print("Counts:")
    print(dict(counts))

    most_common = Counter(counts).most_common(1)[0][0]
    estimated_phase = _binary_fraction_to_decimal(most_common)
    precision = 2 ** (-len(most_common))

    print(f"Bitstring più probabile: {most_common}")
    print(f"Fase stimata: {estimated_phase}")
    print(f"Finestra di precisione: ±{precision}")
