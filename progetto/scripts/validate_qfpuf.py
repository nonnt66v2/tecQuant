from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from progetto.qfpuf import QFPUFConfig, run_pipeline


def main() -> None:
    config = QFPUFConfig(
        num_qubits=3,
        depth=2,
        seed=7,
        shots=64,
        auth_threshold=1,
        flip_probability=0.0,
        output_dir="progetto/risultati/qfpuf",
    )
    payload = run_pipeline(config)

    response = payload["challenge"]["response"]
    if len(response) != config.num_qubits:
        raise SystemExit("Response length does not match number of qubits")

    auth = payload["authentication"]
    if not auth["accepted"]:
        raise SystemExit("Authentication failed")

    print("QFPUF validation succeeded")


if __name__ == "__main__":
    main()
