# Su Kaggle, assicurati di installare qiskit se non è già presente:
# !pip install qiskit qiskit-aer

import math
from typing import Tuple
from dataclasses import dataclass

try:
    from qiskit import QuantumCircuit
except ImportError:
    print("Errore: Qiskit non è installato. Esegui: !pip install qiskit")


# --- Classi e funzioni del progetto ---

@dataclass(frozen=True)
class Challenge:
    bitstring: str
    angles: Tuple[float, ...]

    def validate(self, num_qubits: int) -> None:
        if len(self.bitstring) != num_qubits:
            raise ValueError("Challenge bitstring length does not match num_qubits")
        if len(self.angles) != num_qubits:
            raise ValueError("Challenge angles length does not match num_qubits")


def build_challenge_circuit(
        num_qubits: int, depth: int, challenge: Challenge
) -> "QuantumCircuit":
    challenge.validate(num_qubits)
    circuit = QuantumCircuit(num_qubits, name="qfpuf_challenge")

    # Layer iniziale di Hadamard
    circuit.h(range(num_qubits))

    # Layer ripetuti (Entanglement + Rotazioni)
    for _ in range(depth):
        # CNOT chain
        for qubit in range(num_qubits - 1):
            circuit.cx(qubit, qubit + 1)

        # Rotazioni RY condizionate dal bitstring del challenge
        for qubit, angle in enumerate(challenge.angles):
            signed_angle = angle if challenge.bitstring[qubit] == "0" else -angle
            circuit.ry(signed_angle, qubit)

    return circuit


# --- Esempio di utilizzo e salvataggio ---

def main():
    # Parametri configurabili
    num_qubits = 4
    depth = 1

    # Challenge di esempio
    bitstring = "1010"
    angles = (0.5, 1.2, 0.8, 1.5)
    challenge = Challenge(bitstring=bitstring, angles=angles)

    print(f"Generazione circuito: {num_qubits} qubits, profondità {depth}")
    print(f"Challenge: {bitstring}\n")

    try:
        circuit = build_challenge_circuit(num_qubits, depth, challenge)

        # 1. Ottieni il disegno testuale
        circuit_text = circuit.draw(output='mpl')
        print(circuit_text)

        # 2. Salva in un file TXT
        # filename = "circuit_output.png"
        # with open(filename, "w", encoding="utf-8") as f:
        #     f.write(f"Circuito QFPUF - {num_qubits} qubits, profondità {depth}\n")
        #     f.write(f"Challenge: {bitstring}\n")
        #     f.write("-" * 40 + "\n")
        #     f.write(str(circuit_text))

        # print(f"\n[OK] Circuito salvato in: {filename}")

        # 3. OPZIONALE: Salva immagine PNG (funziona se matplotlib è installato)
        circuit.draw(output='mpl', filename='circuit_drawing.png')

    except Exception as e:
        print(f"Errore durante la generazione o salvataggio: {e}")


if __name__ == "__main__":
    main()
