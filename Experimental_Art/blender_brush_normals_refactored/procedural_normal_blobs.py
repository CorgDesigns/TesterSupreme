"""Command-line entry point for the modular normal-map processor."""

from pathlib import Path

from normal_blobs.cli import main


if __name__ == "__main__":
    raise SystemExit(main(project_dir=Path(__file__).resolve().parent))
