"""Command-line parser and dispatch for all modular algorithms."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from normal_blobs import __version__
from normal_blobs.algorithms import ALGORITHMS
from normal_blobs.image_io import MAX_SAFE_BLACK_THRESHOLD
from normal_blobs.models import CommonOptions
from normal_blobs.resources import GIB
from normal_blobs.runner import BatchOptions, run_batch
from normal_blobs.validation import (
    filename_suffix,
    float_in_range,
    integer_in_range,
    non_negative_float,
    resolution_size,
)

HELP_COMMAND = "help"
HELP_ALL_OPTION = "--help-all"


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    workflow = parser.add_argument_group("input and output")
    workflow.add_argument(
        "-i",
        "--input",
        type=Path,
        action="append",
        dest="inputs",
        metavar="PATH",
        help=(
            "PNG file or flat directory to process; repeat for multiple inputs. "
            "Defaults to this project's to_process directory."
        ),
    )
    workflow.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        metavar="DIR",
        help="Output directory (default: this project's export directory).",
    )
    workflow.add_argument(
        "--suffix",
        type=filename_suffix,
        default="_processed",
        metavar="TEXT",
        help="Text appended to output stems (default: _processed).",
    )
    workflow.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Allow an existing destination PNG to be atomically replaced. "
            "Without this flag, that file is skipped safely."
        ),
    )
    workflow.add_argument(
        "--delete-source",
        action="store_true",
        help=(
            "Consume each source only after its output is verified and saved. "
            "Sources are preserved by default."
        ),
    )
    workflow.add_argument(
        "--resolution",
        type=resolution_size,
        default=None,
        metavar="{auto,1024,2048,4096}",
        help=(
            "Optional input-size filter; this never resizes an image. Without "
            "it, all supported square sizes are accepted: 1024, 2048, and "
            "4096 (default: auto)."
        ),
    )
    workflow.add_argument(
        "--cpu-memory-limit-gb",
        type=float_in_range(0.25, 128.0),
        metavar="GIB",
        help=(
            "Optional per-file CPU memory ceiling from 0.25 to 128 GiB. "
            "The automatic available-RAM safety budget can only lower this "
            "limit; chunked algorithms reduce chunk rows before skipping."
        ),
    )
    workflow.add_argument(
        "--require-output",
        action="store_true",
        help=(
            "Return a failure status when the batch produces zero outputs, "
            "including empty or fully skipped queues. Useful for automated "
            "export pipelines."
        ),
    )

    shared = parser.add_argument_group("shared algorithm options")
    shared.add_argument(
        "--seed",
        type=integer_in_range(0, 2**32 - 1),
        help=(
            "Random seed from 0 to 4294967295 for repeatable output "
            "(default: random)."
        ),
    )
    shared.add_argument(
        "--seed-scope",
        choices=("batch", "file"),
        default="batch",
        help=(
            "Batch preserves legacy queue-order randomness; file derives an "
            "order-independent stream per filename and requires --seed "
            "(default: batch)."
        ),
    )
    shared.add_argument(
        "--rng-mode",
        choices=("legacy", "modern"),
        default="legacy",
        help=(
            "Legacy reproduces the original random streams; modern uses "
            "NumPy's newer generator and produces different seeded geometry "
            "(default: legacy)."
        ),
    )
    shared.add_argument(
        "--black-threshold",
        type=float_in_range(0.0, MAX_SAFE_BLACK_THRESHOLD),
        default=10.0,
        metavar="RGB_SUM",
        help=(
            "RGB-sum cutoff used to identify black UV padding from 0 to 150. "
            "Pixels at or below it are never crossed or modified. The safe "
            "maximum cannot hide a valid unit normal (default: 10)."
        ),
    )
    shared.add_argument(
        "--blend-strength",
        type=float_in_range(0.0, 1.0),
        default=1.0,
        metavar="RATIO",
        help=(
            "Strength of the generated effect from 0 (validated copy/no "
            "effect) to 1 (full effect; default: 1)."
        ),
    )
    shared.add_argument(
        "--similarity-threshold",
        type=non_negative_float,
        default=12.0,
        metavar="DISTANCE",
        help="RGB distance below which neighboring cells are nudged (default: 12).",
    )
    shared.add_argument(
        "--hue-tweak",
        type=float_in_range(0.0, 1.0),
        default=0.04,
        metavar="RATIO",
        help="Maximum random hue nudge for similar cells (default: 0.04).",
    )
    shared.add_argument(
        "--shade-tweak",
        type=float_in_range(0.0, 255.0),
        default=12.0,
        metavar="LEVELS",
        help="Maximum random brightness nudge for similar cells (default: 12).",
    )
    shared.add_argument(
        "--no-renormalize",
        action="store_false",
        dest="renormalize",
        help=(
            "Do not restore processed RGB normals to unit length. Leave "
            "renormalization enabled for normal-map-safe output."
        ),
    )
    shared.set_defaults(renormalize=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="procedural_normal_blobs.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Add procedural patterns to object-space normal-map PNGs.\n"
            "Choose one algorithm, then place shared and algorithm-specific "
            "options after its name."
        ),
        epilog=(
            "Help commands:\n"
            "  py procedural_normal_blobs.py help\n"
            "  py procedural_normal_blobs.py help ALGORITHM\n"
            "  py procedural_normal_blobs.py help all\n"
            "  py procedural_normal_blobs.py --help-all\n\n"
            "Inputs are preserved by default. Outputs remain object-space "
            "normal maps."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        HELP_ALL_OPTION,
        action="store_true",
        help="Show detailed help and options for every algorithm, then exit.",
    )
    subparsers = parser.add_subparsers(
        dest="algorithm", metavar="ALGORITHM"
    )
    algorithm_parsers: dict[str, argparse.ArgumentParser] = {}
    for spec in ALGORITHMS.values():
        algorithm_parser = subparsers.add_parser(
            spec.name,
            help=spec.summary,
            description=spec.description,
            epilog=spec.help_epilog,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        add_common_arguments(algorithm_parser)
        spec.add_arguments(algorithm_parser)
        algorithm_parser.set_defaults(algorithm_spec=spec)
        algorithm_parsers[spec.name] = algorithm_parser
    setattr(parser, "_algorithm_help_parsers", algorithm_parsers)
    return parser


def print_all_help(parser: argparse.ArgumentParser) -> None:
    """Print general help followed by every algorithm's detailed help."""

    algorithm_parsers = getattr(parser, "_algorithm_help_parsers")
    print(parser.format_help().rstrip())
    for name in ALGORITHMS:
        print(f"\n{'=' * 78}\n{name}\n{'=' * 78}")
        print(algorithm_parsers[name].format_help().rstrip())


def handle_help_request(
    parser: argparse.ArgumentParser,
    arguments: list[str],
) -> bool:
    """Handle friendly help aliases before required subcommand parsing."""

    if not arguments or arguments[0] != HELP_COMMAND:
        return False
    if len(arguments) == 1:
        parser.print_help()
        return True
    if len(arguments) > 2:
        parser.error("help accepts at most one topic: an algorithm name or all")

    topic = arguments[1]
    if topic == "all":
        print_all_help(parser)
        return True
    algorithm_parsers = getattr(parser, "_algorithm_help_parsers")
    if topic not in algorithm_parsers:
        choices = ", ".join(ALGORITHMS)
        parser.error(f"unknown help topic {topic!r}; choose one of: {choices}, all")
    algorithm_parsers[topic].print_help()
    return True


def main(
    argv: Sequence[str] | None = None, project_dir: Path | None = None
) -> int:
    project_dir = project_dir or Path(__file__).resolve().parents[1]
    parser = build_parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if handle_help_request(parser, arguments):
        return 0
    args = parser.parse_args(arguments)
    if args.help_all:
        print_all_help(parser)
        return 0
    if args.algorithm is None:
        parser.error("an ALGORITHM is required; run 'help' to compare choices")
    if args.seed_scope == "file" and args.seed is None:
        parser.error("--seed-scope file requires --seed")
    spec = args.algorithm_spec
    try:
        algorithm_config = spec.make_config(args)
    except ValueError as error:
        parser.error(str(error))

    common = CommonOptions(
        black_threshold=args.black_threshold,
        blend_strength=args.blend_strength,
        similarity_threshold=args.similarity_threshold,
        hue_tweak=args.hue_tweak,
        shade_tweak=args.shade_tweak,
        renormalize=args.renormalize,
    )
    batch = BatchOptions(
        inputs=args.inputs or [project_dir / "to_process"],
        output_dir=args.output_dir or project_dir / "export",
        suffix=args.suffix,
        overwrite=args.overwrite,
        delete_source=args.delete_source,
        seed=args.seed,
        rng_mode=args.rng_mode,
        resolution_filter=args.resolution,
        cpu_memory_limit_bytes=(
            None
            if args.cpu_memory_limit_gb is None
            else int(args.cpu_memory_limit_gb * GIB)
        ),
        require_output=args.require_output,
        seed_scope=args.seed_scope,
    )
    try:
        result = run_batch(spec, algorithm_config, common, batch)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 1 if result.failed or result.warnings or (
        batch.require_output and result.processed == 0
    ) else 0
