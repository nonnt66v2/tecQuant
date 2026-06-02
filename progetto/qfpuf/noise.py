from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

from qiskit_aer.noise import (
    NoiseModel,
    ReadoutError,
    depolarizing_error,
    thermal_relaxation_error,
)

from .config import NoiseConfig


def _jitter(value: float, variation: float, rng: random.Random, minimum: float = 0.0) -> float:
    jittered = value * (1.0 + rng.uniform(-variation, variation))
    return max(minimum, jittered)


def build_noise_model(
    config: NoiseConfig, seed: int, num_qubits: int = 4
) -> Tuple[NoiseModel, Dict[str, Any]]:
    """Costruisce un noise model con profilo PER-QUBIT unico per chip.

    A differenza di un rumore uniforme su tutti i qubit, ogni qubit fisico
    riceve i propri parametri T1/T2/depolarizing/readout, jitterati a partire
    dal `seed` del chip. Questo crea una "firma spaziale" irriproducibile:
    due chip con lo stesso livello medio di rumore ma seed diversi producono
    pattern di errore strutturalmente diversi (quale qubit e' piu' rumoroso,
    quale readout e' piu' asimmetrico, ...). E' il meccanismo che rende la
    QPUF unclonable: la firma non sta nel *quanto* rumore, ma nel *come* e'
    distribuito spazialmente sul chip.

    Nota: le distribuzioni grezze di chip diversi restano molto simili (derivano
    tutte dallo stesso circuito); la firma emerge confrontando lo *scostamento
    dall'ideale*, non le distribuzioni grezze. Vedi la metrica cosine-deviation
    usata in cross_verify_chips.py.
    """
    rng = random.Random(seed)
    noise_model = NoiseModel()

    # --- Errore a 1 qubit + thermal relaxation, indipendente per ogni qubit ---
    qubit_t: List[Tuple[float, float]] = []
    per_qubit: List[Dict[str, float]] = []
    for qubit in range(num_qubits):
        depol_1q = _jitter(config.depolarizing_1q, config.variation, rng)
        t1 = _jitter(config.t1, config.variation, rng, minimum=1.0)
        t2 = min(_jitter(config.t2, config.variation, rng, minimum=1.0), 2.0 * t1)
        gate_time_1q = _jitter(config.gate_time_1q, config.variation, rng, minimum=1.0)

        error_1q = depolarizing_error(depol_1q, 1).compose(
            thermal_relaxation_error(t1, t2, gate_time_1q)
        )
        noise_model.add_quantum_error(error_1q, ["h", "ry"], [qubit])
        qubit_t.append((t1, t2))
        per_qubit.append(
            {"qubit": qubit, "depolarizing_1q": depol_1q, "t1": t1, "t2": t2,
             "gate_time_1q": gate_time_1q}
        )

    # --- Errore a 2 qubit (CNOT) per ogni coppia adiacente usata dal circuito ---
    pairs: List[Dict[str, float]] = []
    for qubit in range(num_qubits - 1):
        depol_2q = _jitter(config.depolarizing_2q, config.variation, rng)
        gate_time_2q = _jitter(config.gate_time_2q, config.variation, rng, minimum=1.0)
        t1a, t2a = qubit_t[qubit]
        t1b, t2b = qubit_t[qubit + 1]
        relaxation_2q = thermal_relaxation_error(t1a, t2a, gate_time_2q).tensor(
            thermal_relaxation_error(t1b, t2b, gate_time_2q)
        )
        error_2q = depolarizing_error(depol_2q, 2).compose(relaxation_2q)
        noise_model.add_quantum_error(error_2q, ["cx"], [qubit, qubit + 1])
        pairs.append(
            {"pair": [qubit, qubit + 1], "depolarizing_2q": depol_2q,
             "gate_time_2q": gate_time_2q}
        )

    # --- Errore di readout per-qubit (asimmetrico): forte discriminante hardware ---
    readout: List[Dict[str, float]] = []
    if config.readout_error > 0.0:
        for qubit in range(num_qubits):
            p01 = min(_jitter(config.readout_error, config.variation, rng), 0.5)  # P(0|1)
            p10 = min(_jitter(config.readout_error, config.variation, rng), 0.5)  # P(1|0)
            noise_model.add_readout_error(
                ReadoutError([[1.0 - p10, p10], [p01, 1.0 - p01]]), [qubit]
            )
            readout.append({"qubit": qubit, "p01": p01, "p10": p10})

    summary: Dict[str, Any] = {
        "per_qubit": per_qubit,
        "pairs": pairs,
        "readout": readout,
        "variation": config.variation,
    }
    return noise_model, summary
