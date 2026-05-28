from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from progetto.qfpuf import QFPUFConfig, run_enrollment, run_verification


def main() -> None:
    defaults = QFPUFConfig.from_dict({})
    config = QFPUFConfig(
        num_qubits=3,
        depth=1,
        seed=7,
        shots=64,
        challenge_config=defaults.challenge_config,
        challenges=None,
        enrollment_instance_seed=7,
        verification_instance_seed=7,
        noise=defaults.noise,
        fidelity_threshold=0.75,
        qber_threshold=0.4,
        output_dir="progetto/risultati/qfpuf",
        enrollment_db_path="progetto/risultati/qfpuf/qfpuf_enrollment.json",
        verification_report_path="progetto/risultati/qfpuf/qfpuf_verification.json",
    )
    enrollment = run_enrollment(config)
    verification = run_verification(config, enrollment)

    entries = enrollment["entries"]
    if not entries:
        raise SystemExit("Enrollment produced no entries")
    response = entries[0]["response"]
    if len(response) != config.num_qubits:
        raise SystemExit("Response length does not match number of qubits")

    if not verification["accepted"]:
        raise SystemExit("Authentication failed")

    print("QFPUF validation succeeded")


if __name__ == "__main__":
    main()
