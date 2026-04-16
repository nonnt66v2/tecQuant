from qiskit import QuantumCircuit
import numpy as np


def qft(n: int) -> QuantumCircuit:
    """Restituisce un circuito QFT su n qubit."""
    qc = QuantumCircuit(n, name=f"QFT_{n}")

    def qft_rotations(k: int) -> None:
        if k == 0:
            return
        k -= 1
        qc.h(k)
        for qubit in range(k):
            qc.cp(np.pi / (2 ** (k - qubit)), qubit, k)
        qft_rotations(k)

    qft_rotations(n)
    for qubit in range(n // 2):
        qc.swap(qubit, n - qubit - 1)
    return qc


def inverse_qft(n: int) -> QuantumCircuit:
    """Restituisce il circuito inverso della QFT."""
    return qft(n).inverse()
