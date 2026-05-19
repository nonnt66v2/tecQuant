from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from progetto.qfpuf import load_config, run_pipeline, write_results


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
    args = parser.parse_args()

    config = load_config(args.config)
    if args.output_dir is not None:
        config = config.__class__(
            **{**config.to_dict(), "output_dir": str(args.output_dir)}
        )

    payload = run_pipeline(config)
    output_path = write_results(payload, Path(config.output_dir), config.seed)
    print(f"Saved results to {output_path}")


if __name__ == "__main__":
    main()
