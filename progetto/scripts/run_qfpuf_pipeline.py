from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from progetto.qfpuf import (
    load_config,
    read_enrollment,
    run_enrollment,
    run_verification,
    write_enrollment,
    write_verification,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QFPUF pipeline")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("progetto/qfpuf_config.json"),
        help="Path to QFPUF config JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "enroll", "verify"],
        default="full",
        help="Pipeline mode: enroll, verify, or full",
    )
    parser.add_argument(
        "--enrollment-db",
        type=Path,
        default=None,
        help="Override enrollment database path",
    )
    parser.add_argument(
        "--verification-report",
        type=Path,
        default=None,
        help="Override verification report path",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    if args.output_dir is not None:
        config = config.__class__(
            **{
                **config.to_dict(),
                "output_dir": str(args.output_dir),
                "enrollment_db_path": str(
                    args.output_dir / "qfpuf_enrollment.json"
                ),
                "verification_report_path": str(
                    args.output_dir / "qfpuf_verification.json"
                ),
            }
        )
    if args.enrollment_db is not None:
        config = config.__class__(
            **{**config.to_dict(), "enrollment_db_path": str(args.enrollment_db)}
        )
    if args.verification_report is not None:
        config = config.__class__(
            **{
                **config.to_dict(),
                "verification_report_path": str(args.verification_report),
            }
        )

    if args.mode in {"full", "enroll"}:
        enrollment = run_enrollment(config)
        enrollment_path = write_enrollment(
            enrollment, Path(config.enrollment_db_path)
        )
        print(f"Saved enrollment database to {enrollment_path}")
    else:
        enrollment = read_enrollment(Path(config.enrollment_db_path))

    if args.mode in {"full", "verify"}:
        verification = run_verification(config, enrollment)
        report_path = write_verification(
            verification, Path(config.verification_report_path)
        )
        print(f"Saved verification report to {report_path}")


if __name__ == "__main__":
    main()
