from fractions import Fraction
from math import gcd
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import UnitaryGate
from qiskit_aer import AerSimulator
import numpy as np

from .qft import inverse_qft


def _multiplication_unitary_mod_15(a: int) -> np.ndarray:
    dim = 16
    U = np.zeros((dim, dim), dtype=complex)
    for x in range(15):
        y = (a * x) % 15
        U[y, x] = 1.0
    U[15, 15] = 1.0
    return U


def controlled_modular_multiplication_gate(a: int, power: int) -> UnitaryGate:
    dim = 16
    base = _multiplication_unitary_mod_15(a)
    op = np.eye(dim, dtype=complex)
    for _ in range(2 ** power):
        op = base @ op
    gate = UnitaryGate(op, label=f"{a}^(2^{power}) mod 15")
    return gate.control(1)


def build_shor_15_qpe_16q(a: int = 7, counting_qubits: int = 12) -> QuantumCircuit:
    """
    Demo didattica di Shor per N=15 usando 16 qubit totali:
    - 12 qubit di counting
    - 4 qubit di work/system register
    """
    system_qubits = 4
    total_qubits = counting_qubits + system_qubits
    if total_qubits != 16:
        raise ValueError("Questa demo e' fissata a 16 qubit totali (12 counting + 4 system).")

    qc = QuantumCircuit(total_qubits, counting_qubits)

    for q in range(counting_qubits):
        qc.h(q)

    # |0001> nel registro di lavoro
    qc.x(total_qubits - 1)

    for k in range(counting_qubits):
        gate = controlled_modular_multiplication_gate(a, k)
        qc.append(gate, [k] + list(range(counting_qubits, total_qubits)))

    qc.append(inverse_qft(counting_qubits), range(counting_qubits))
    qc.measure(range(counting_qubits), range(counting_qubits))
    return qc


def estimate_order_from_counts(counts: dict[str, int], N: int) -> int | None:
    best = max(counts, key=counts.get)
    phase = int(best, 2) / (2 ** len(best))
    frac = Fraction(phase).limit_denominator(N)
    return frac.denominator


def nontrivial_factors_from_order(a: int, N: int, r: int) -> tuple[int, int] | None:
    if r % 2 != 0:
        return None

    x = pow(a, r // 2)
    if x % N == N - 1:
        return None

    p = gcd(x - 1, N)
    q = gcd(x + 1, N)
    if 1 < p < N and 1 < q < N and p * q == N:
        return (p, q)
    return None


def run_shor_16q_demo(shots: int = 2048) -> None:
    a = 7
    N = 15

    if gcd(a, N) != 1:
        print(f"Fattore trovato banalmente: gcd({a}, {N}) = {gcd(a, N)}")
        return

    qc = build_shor_15_qpe_16q(a=a, counting_qubits=12)
    print(f"Circuito creato con {qc.num_qubits} qubit totali e {qc.num_clbits} bit classici.")

    sim = AerSimulator()
    tqc = transpile(qc, sim)
    result = sim.run(tqc, shots=shots).result()
    counts = result.get_counts()

    top_counts = dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10])
    print("Top counts:")
    print(top_counts)

    r = estimate_order_from_counts(counts, N)
    print(f"Ordine stimato r = {r}")

    if r is None:
        print("Impossibile stimare r")
        return

    factors = nontrivial_factors_from_order(a, N, r)
    if factors is None:
        print("Nessun fattore non banale trovato in questo run.")
        return

    print(f"Fattori trovati: {factors[0]} e {factors[1]}")
