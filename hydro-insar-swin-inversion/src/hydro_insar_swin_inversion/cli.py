from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .config import load_config
from .demo import run_synthetic_demo


def cmd_info(_: argparse.Namespace) -> int:
    print("hydro-insar-swin-inversion")
    print("Container-oriented software scaffold for hydrologic inversion from InSAR and multisensor constraints.")
    return 0


def cmd_check_config(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    print(f"Config OK: {cfg.project_name}")
    print(f"Study area: {cfg.study_area.name} ({cfg.study_area.region})")
    return 0


def cmd_show_paths(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    print(json.dumps(asdict(cfg), indent=2, default=str))
    return 0


def cmd_demo_synthetic(args: argparse.Namespace) -> int:
    result = run_synthetic_demo(
        output_dir=args.output_dir,
        n_steps=args.n_steps,
        seed=args.seed,
    )
    print("Synthetic demo completed.")
    print(json.dumps(result.summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hisi")
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="Show package information.")
    p_info.set_defaults(func=cmd_info)

    p_check = sub.add_parser("check-config", help="Validate an example config file.")
    p_check.add_argument("config", help="Path to YAML config.")
    p_check.set_defaults(func=cmd_check_config)

    p_paths = sub.add_parser("show-paths", help="Print the parsed config content.")
    p_paths.add_argument("config", help="Path to YAML config.")
    p_paths.set_defaults(func=cmd_show_paths)

    p_demo = sub.add_parser("demo-synthetic", help="Run a minimal synthetic grouped inversion demo.")
    p_demo.add_argument(
        "--output-dir",
        default="/workspace/outputs/demo",
        help="Directory for demo outputs.",
    )
    p_demo.add_argument(
        "--n-steps",
        type=int,
        default=72,
        help="Number of synthetic time steps.",
    )
    p_demo.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    p_demo.set_defaults(func=cmd_demo_synthetic)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
