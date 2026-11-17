from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from normal_blobs import __version__
from normal_blobs.cli import main
from normal_blobs.cli import build_parser
from normal_blobs.image_io import load_normal_image, stage_normal_image
from normal_blobs.resources import GIB
from normal_blobs.runner import (
    acquire_destination_lock,
    append_issue,
    consume_unchanged_source,
    _process_is_alive,
    release_destination_lock,
    source_fingerprint,
)


class CliTests(unittest.TestCase):
    @staticmethod
    def write_normal(path: Path, size: int) -> None:
        Image.new("RGB", (size, size), (128, 128, 255)).save(path)

    def test_issue_lock_pid_probe_is_non_destructive(self) -> None:
        self.assertTrue(_process_is_alive(os.getpid()))
        self.assertFalse(_process_is_alive(2147483647))

    def test_processes_one_file_without_deleting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.png"
            output = root / "results"
            self.write_normal(source, 1024)

            exit_code = main(
                [
                    "center_average_normalization",
                    "--input",
                    str(source),
                    "--output-dir",
                    str(output),
                    "--block-size",
                    "256",
                    "--seed",
                    "7",
                ],
                project_dir=root,
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(source.exists())
            self.assertTrue((output / "input_processed.png").exists())

    def test_delete_source_is_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "queued.png"
            self.write_normal(source, 1024)

            exit_code = main(
                [
                    "center_average_normalization",
                    "--input",
                    str(source),
                    "--output-dir",
                    str(root / "results"),
                    "--block-size",
                    "256",
                    "--delete-source",
                ],
                project_dir=root,
            )

            self.assertEqual(exit_code, 0)
            self.assertFalse(source.exists())

    def test_empty_queue_is_logged_and_require_output_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            inputs.mkdir()
            output = root / "results"

            exit_code = main(
                [
                    "center_average_normalization",
                    "--input",
                    str(inputs),
                    "--output-dir",
                    str(output),
                    "--require-output",
                ],
                project_dir=root,
            )

            self.assertEqual(exit_code, 1)
            log = (output / "processing_errors.log").read_text(
                encoding="utf-8"
            )
            self.assertIn("NO_INPUT", log)
            manifest = json.loads(
                (output / "export_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["run"]["outcome"], "failed")
            self.assertEqual(manifest["run"]["expected_exit_code"], 1)
            self.assertEqual(manifest["counts"]["discovered"], 0)
            self.assertEqual(manifest["files"][0]["category"], "NO_INPUT")

    def test_file_seed_scope_is_independent_of_queue_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            inputs.mkdir()
            prior = inputs / "a_prior.png"
            target = inputs / "b_target.png"
            self.write_normal(prior, 1024)
            self.write_normal(target, 1024)
            alone_output = root / "alone"
            queued_output = root / "queued"
            common_args = [
                "center_average_normalization",
                "--block-size",
                "256",
                "--seed",
                "42",
                "--seed-scope",
                "file",
            ]

            self.assertEqual(
                main(
                    [
                        *common_args,
                        "--input",
                        str(target),
                        "--output-dir",
                        str(alone_output),
                    ],
                    project_dir=root,
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        *common_args,
                        "--input",
                        str(inputs),
                        "--output-dir",
                        str(queued_output),
                    ],
                    project_dir=root,
                ),
                0,
            )

            alone_hash = hashlib.sha256(
                (alone_output / "b_target_processed.png").read_bytes()
            ).digest()
            queued_hash = hashlib.sha256(
                (queued_output / "b_target_processed.png").read_bytes()
            ).digest()
            self.assertEqual(alone_hash, queued_hash)

    def test_locked_destination_is_not_processed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.png"
            output = root / "results"
            output.mkdir()
            self.write_normal(source, 1024)
            destination = output / "input_processed.png"
            descriptor, lock_path = acquire_destination_lock(destination)
            try:
                exit_code = main(
                    [
                        "center_average_normalization",
                        "--input",
                        str(source),
                        "--output-dir",
                        str(output),
                    ],
                    project_dir=root,
                )
            finally:
                release_destination_lock(descriptor, lock_path)

            self.assertEqual(exit_code, 1)
            self.assertFalse(destination.exists())

    def test_error_log_rotates_at_its_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "processing_errors.log"
            log.write_text("0123456789", encoding="utf-8")
            with patch("normal_blobs.runner.MAX_ERROR_LOG_BYTES", 10):
                append_issue(log, root / "input.png", "ERROR", "new")

            archive = root / "processing_errors.previous.log"
            self.assertEqual(
                archive.read_text(encoding="utf-8"), "0123456789"
            )
            self.assertIn("new", log.read_text(encoding="utf-8"))

    def test_invalid_input_normals_are_logged_before_processing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "invalid.png"
            output = root / "results"
            Image.new("RGB", (1024, 1024), (255, 255, 255)).save(source)

            exit_code = main(
                [
                    "center_average_normalization",
                    "--input",
                    str(source),
                    "--output-dir",
                    str(output),
                ],
                project_dir=root,
            )

            self.assertEqual(exit_code, 1)
            self.assertFalse((output / "invalid_processed.png").exists())
            log = (output / "processing_errors.log").read_text(
                encoding="utf-8"
            )
            self.assertIn("exceeding the safe 1.00% limit", log)

    def test_sparse_non_unit_input_normals_are_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "repairable.png"
            output = root / "results"
            image = Image.new("RGB", (1024, 1024), (128, 128, 255))
            for x in range(1000):
                image.putpixel((x, 0), (255, 255, 255))
            image.save(source)

            exit_code = main(
                [
                    "center_average_normalization",
                    "--input",
                    str(source),
                    "--output-dir",
                    str(output),
                ],
                project_dir=root,
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "repairable_processed.png").exists())
            log = (output / "processing_errors.log").read_text(
                encoding="utf-8"
            )
            self.assertIn("INPUT_NORMALS_REPAIRED", log)
            manifest = json.loads(
                (output / "export_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["files"][0]["notices"][0]["category"],
                "INPUT_NORMALS_REPAIRED",
            )

    def test_input_output_directory_overlap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "asset.png"
            self.write_normal(source, 1024)
            original = source.read_bytes()

            with self.assertRaises(SystemExit):
                main(
                    [
                        "center_average_normalization",
                        "--input",
                        str(root),
                        "--output-dir",
                        str(root),
                        "--overwrite",
                        "--delete-source",
                    ],
                    project_dir=root,
                )

            self.assertEqual(source.read_bytes(), original)
            self.assertFalse((root / "asset_processed.png").exists())
            manifest = json.loads(
                (root / "export_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["files"][0]["category"], "PREFLIGHT_ERROR")

    def test_source_delete_failure_preserves_processed_output_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.png"
            output = root / "results"
            self.write_normal(source, 1024)
            original_unlink = Path.unlink

            def fail_source_delete(
                path: Path, *args: object, **kwargs: object
            ) -> None:
                if path.name.endswith(".delete-pending"):
                    raise PermissionError("simulated delete denial")
                original_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", fail_source_delete):
                exit_code = main(
                    [
                        "center_average_normalization",
                        "--input",
                        str(source),
                        "--output-dir",
                        str(output),
                        "--delete-source",
                    ],
                    project_dir=root,
                )

            self.assertEqual(exit_code, 1)
            self.assertTrue(source.exists())
            self.assertTrue((output / "input_processed.png").exists())
            manifest = json.loads(
                (output / "export_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["counts"]["processed"], 1)
            self.assertEqual(manifest["counts"]["failed"], 0)
            self.assertEqual(manifest["counts"]["warnings"], 1)
            self.assertEqual(
                manifest["files"][0]["category"],
                "PROCESSED_WITH_WARNINGS",
            )
            self.assertFalse(
                list(root.glob(".*.delete-pending"))
            )

    def test_source_replaced_at_delete_claim_is_recovered_not_deleted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.png"
            self.write_normal(source, 1024)
            expected = source_fingerprint(source)
            replacement = Image.new(
                "RGB", (1024, 1024), (128, 255, 128)
            )
            original_replace = os.replace

            def replace_source_then_claim(path: object, target: object) -> None:
                if Path(path) == source:
                    replacement.save(source)
                    changed_time = expected.modified_ns + 1_000_000_000
                    os.utime(source, ns=(changed_time, changed_time))
                original_replace(path, target)

            with patch(
                "normal_blobs.runner.os.replace",
                side_effect=replace_source_then_claim,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "source changed while it was being claimed",
                ):
                    consume_unchanged_source(source, expected, "test-run")

            self.assertTrue(source.exists())
            with Image.open(source) as recovered:
                self.assertEqual(recovered.getpixel((0, 0)), (128, 255, 128))
            self.assertFalse(
                list(root.glob(".*.delete-pending"))
            )

    def test_issue_log_escapes_record_breaking_characters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "processing_errors.log"
            append_issue(
                log,
                root / "input\tname.png",
                "BAD\nCATEGORY",
                "line one\r\nline two",
            )

            records = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(records), 1)
            self.assertIn("input\\tname.png", records[0])
            self.assertIn("BAD\\nCATEGORY", records[0])
            self.assertIn("line one\\r\\nline two", records[0])

    def test_lock_cleanup_failure_is_controlled_and_manifested(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.png"
            output = root / "results"
            self.write_normal(source, 1024)
            original_unlink = Path.unlink

            def fail_lock_delete(
                path: Path, *args: object, **kwargs: object
            ) -> None:
                if path.name.endswith(".lock"):
                    raise PermissionError("simulated lock cleanup denial")
                original_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", fail_lock_delete):
                exit_code = main(
                    [
                        "center_average_normalization",
                        "--input",
                        str(source),
                        "--output-dir",
                        str(output),
                    ],
                    project_dir=root,
                )

            self.assertEqual(exit_code, 1)
            self.assertTrue((output / "input_processed.png").exists())
            self.assertTrue((output / "export_summary.json").exists())
            manifest = json.loads(
                (output / "export_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["counts"]["warnings"], 1)
            (output / ".input_processed.png.lock").unlink(missing_ok=True)

    def test_manifest_write_failure_returns_controlled_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.png"
            output = root / "results"
            self.write_normal(source, 1024)

            with patch(
                "normal_blobs.runner.write_manifest_atomic",
                side_effect=PermissionError("simulated manifest denial"),
            ):
                exit_code = main(
                    [
                        "center_average_normalization",
                        "--input",
                        str(source),
                        "--output-dir",
                        str(output),
                    ],
                    project_dir=root,
                )

            self.assertEqual(exit_code, 1)
            self.assertTrue((output / "input_processed.png").exists())
            self.assertFalse((output / "export_summary.json").exists())
            log = (output / "processing_errors.log").read_text(
                encoding="utf-8"
            )
            self.assertIn("MANIFEST_WRITE_FAILED", log)

    def test_source_replacement_after_preflight_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.png"
            output = root / "results"
            self.write_normal(source, 1024)

            def load_then_replace(path: Path):
                array = load_normal_image(path)
                Image.new("RGB", (1024, 1024), (128, 255, 128)).save(
                    path
                )
                return array

            with patch(
                "normal_blobs.runner.load_normal_image",
                side_effect=load_then_replace,
            ):
                exit_code = main(
                    [
                        "center_average_normalization",
                        "--input",
                        str(source),
                        "--output-dir",
                        str(output),
                    ],
                    project_dir=root,
                )

            self.assertEqual(exit_code, 1)
            self.assertFalse((output / "input_processed.png").exists())
            manifest = json.loads(
                (output / "export_summary.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                "source changed",
                manifest["files"][0]["message"],
            )

    def test_source_replacement_during_export_staging_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.png"
            output = root / "results"
            self.write_normal(source, 1024)

            def stage_then_replace(*args, **kwargs):
                staged = stage_normal_image(*args, **kwargs)
                Image.new("RGB", (1024, 1024), (128, 255, 128)).save(
                    source
                )
                return staged

            with patch(
                "normal_blobs.runner.stage_normal_image",
                side_effect=stage_then_replace,
            ):
                exit_code = main(
                    [
                        "center_average_normalization",
                        "--input",
                        str(source),
                        "--output-dir",
                        str(output),
                    ],
                    project_dir=root,
                )

            self.assertEqual(exit_code, 1)
            self.assertFalse((output / "input_processed.png").exists())
            manifest = json.loads(
                (output / "export_summary.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                "source changed after export staging",
                manifest["files"][0]["message"],
            )

    def test_resolution_presets_are_accepted(self) -> None:
        parser = build_parser()
        presets = {
            "1024": 1024,
            "1024x1024": 1024,
            "2048": 2048,
            "4096": 4096,
            "4096x4096": 4096,
            "auto": None,
            "source": None,
        }
        for resolution, expected in presets.items():
            with self.subTest(resolution=resolution):
                args = parser.parse_args(
                    [
                        "brush_stroke_cells",
                        "--resolution",
                        resolution,
                    ]
                )
                self.assertEqual(args.resolution, expected)
                self.assertEqual(args.rng_mode, "legacy")
                config = args.algorithm_spec.make_config(args)
                self.assertEqual(config.edge_selection, "legacy")
                self.assertEqual(args.workers, 0)

    def test_brush_help_renders_hexagon_options(self) -> None:
        parser = build_parser()
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as exit:
            parser.parse_args(["brush_stroke_cells", "--help"])

        self.assertEqual(exit.exception.code, 0)
        rendered = output.getvalue()
        self.assertIn("--hex-layout", rendered)
        self.assertIn("--hex-jitter", rendered)
        self.assertIn("--curvature", rendered)
        self.assertIn("Foliage:", rendered)
        self.assertIn("30% of panel spacing", rendered)

    def test_brush_organic_controls_are_parsed_into_config(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "brush_stroke_cells",
                "--brush-shape",
                "grass-clump",
                "--curvature",
                "0.8",
                "--segments",
                "7",
                "--roughness",
                "0.6",
                "--symmetry",
                "0.4",
                "--branching",
                "0.9",
            ]
        )
        config = args.algorithm_spec.make_config(args)
        self.assertEqual(config.brush_shape, "grass-clump")
        self.assertEqual(config.curvature, 0.8)
        self.assertEqual(config.segments, 7)
        self.assertEqual(config.roughness, 0.6)
        self.assertEqual(config.symmetry, 0.4)
        self.assertEqual(config.branching, 0.9)

    def test_general_help_command_compares_every_algorithm(self) -> None:
        output = io.StringIO()
        with patch("normal_blobs.cli.run_batch") as run_batch:
            with redirect_stdout(output):
                exit_code = main(["help"])

        self.assertEqual(exit_code, 0)
        run_batch.assert_not_called()
        rendered = output.getvalue()
        for algorithm in (
            "center_average_normalization",
            "edge_gradient_cascade",
            "voronoi_flow_cells",
            "brush_stroke_cells",
        ):
            self.assertIn(algorithm, rendered)
        self.assertIn("Help commands:", rendered)
        self.assertIn("--help-all", rendered)

    def test_focused_help_command_explains_algorithm_and_options(
        self,
    ) -> None:
        output = io.StringIO()
        with patch("normal_blobs.cli.run_batch") as run_batch:
            with redirect_stdout(output):
                exit_code = main(["help", "voronoi_flow_cells"])

        self.assertEqual(exit_code, 0)
        run_batch.assert_not_called()
        rendered = output.getvalue()
        self.assertIn("Algorithm 3 scatters weighted seed points", rendered)
        self.assertIn("--average-cell-size", rendered)
        self.assertIn("--size-variance", rendered)
        self.assertIn("--elongation-max", rendered)
        self.assertIn("Examples:", rendered)
        self.assertIn("Start with:", rendered)

    def test_help_all_option_renders_every_detailed_reference(self) -> None:
        option_output = io.StringIO()
        alias_output = io.StringIO()
        with patch("normal_blobs.cli.run_batch") as run_batch:
            with redirect_stdout(option_output):
                option_exit = main(["--help-all"])
            with redirect_stdout(alias_output):
                alias_exit = main(["help", "all"])

        self.assertEqual(option_exit, 0)
        self.assertEqual(alias_exit, 0)
        run_batch.assert_not_called()
        self.assertEqual(option_output.getvalue(), alias_output.getvalue())
        rendered = option_output.getvalue()
        for text in (
            "Algorithm 1 divides each UV island",
            "Algorithm 2 divides each UV island",
            "Algorithm 3 scatters weighted seed points",
            "Algorithm 4 scatters strokes or panel centers",
            "--block-size",
            "--average-cell-size",
            "--brush-shape",
        ):
            self.assertIn(text, rendered)

    def test_unknown_help_topic_is_a_controlled_cli_error(self) -> None:
        errors = io.StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit) as exit:
            main(["help", "unknown"])

        self.assertEqual(exit.exception.code, 2)
        self.assertIn("unknown help topic", errors.getvalue())

    def test_unsafe_padding_threshold_and_suffix_are_rejected(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "center_average_normalization",
                    "--black-threshold",
                    "151",
                ]
            )
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "center_average_normalization",
                    "--suffix",
                    ":alternate-stream",
                ]
            )

    def test_zero_blend_uses_lightweight_validation_export_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.png"
            output = root / "results"
            self.write_normal(source, 1024)

            exit_code = main(
                [
                    "brush_stroke_cells",
                    "--input",
                    str(source),
                    "--output-dir",
                    str(output),
                    "--blend-strength",
                    "0",
                    "--cpu-memory-limit-gb",
                    "0.25",
                ],
                project_dir=root,
            )

            self.assertEqual(exit_code, 0)
            manifest = json.loads(
                (output / "export_summary.json").read_text(encoding="utf-8")
            )
            record = manifest["files"][0]
            self.assertEqual(record["status"], "processed")
            self.assertEqual(
                record["resources"]["processing_mode"],
                "validation_and_export_only",
            )

    def test_non_finite_and_unsafe_brush_controls_are_rejected(self) -> None:
        parser = build_parser()
        unsafe_cases = (
            ("--edge-softness", "nan"),
            ("--length-max", "inf"),
            ("--average-spacing", "0.001"),
            ("--candidates", "1000000"),
            ("--samples-per-stroke", "1000000"),
            ("--chunk-rows", "1000000"),
            ("--workers", "9"),
        )
        for option, value in unsafe_cases:
            with self.subTest(option=option, value=value):
                with self.assertRaises(SystemExit):
                    parser.parse_args(
                        ["brush_stroke_cells", option, value]
                    )

    def test_swirl_requires_enough_path_samples(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "brush_stroke_cells",
                "--brush-shape",
                "swirl",
                "--samples-per-stroke",
                "2",
            ]
        )
        with self.assertRaisesRegex(ValueError, "requires.*3"):
            args.algorithm_spec.make_config(args)

    def test_deformed_brushes_enforce_their_minimum_path_samples(
        self,
    ) -> None:
        parser = build_parser()
        cases = {
            "vine": 5,
            "crack": 5,
            "chevron": 3,
            "circuit-trace": 5,
        }
        for shape, minimum in cases.items():
            with self.subTest(shape=shape):
                args = parser.parse_args(
                    [
                        "brush_stroke_cells",
                        "--brush-shape",
                        shape,
                        "--samples-per-stroke",
                        str(minimum - 1),
                    ]
                )
                with self.assertRaisesRegex(
                    ValueError, rf"requires.*{minimum}"
                ):
                    args.algorithm_spec.make_config(args)

                accepted = parser.parse_args(
                    [
                        "brush_stroke_cells",
                        "--brush-shape",
                        shape,
                        "--samples-per-stroke",
                        str(minimum),
                    ]
                )
                accepted.algorithm_spec.make_config(accepted)

    def test_new_artistic_brush_choices_are_registered(self) -> None:
        parser = build_parser()
        expected = {
            "leaf",
            "petal",
            "pine-needle",
            "scallop",
            "vine",
            "bark",
            "pebble",
            "boulder",
            "crack",
            "crystal",
            "shard",
            "chevron",
            "circuit-trace",
            "diamond-panel",
            "octagon-panel",
        }
        for shape in expected:
            with self.subTest(shape=shape):
                args = parser.parse_args(
                    ["brush_stroke_cells", "--brush-shape", shape]
                )
                config = args.algorithm_spec.make_config(args)
                self.assertEqual(config.brush_shape, shape)

    def test_shape_aware_edge_selection_defaults_preserve_compatibility(
        self,
    ) -> None:
        parser = build_parser()
        capsule_args = parser.parse_args(["brush_stroke_cells"])
        scale_args = parser.parse_args(
            ["brush_stroke_cells", "--brush-shape", "scale"]
        )
        hexagon_args = parser.parse_args(
            ["brush_stroke_cells", "--brush-shape", "hexagon"]
        )
        panel_args = parser.parse_args(
            ["brush_stroke_cells", "--brush-shape", "octagon-panel"]
        )
        explicit_legacy_args = parser.parse_args(
            [
                "brush_stroke_cells",
                "--brush-shape",
                "scale",
                "--edge-selection",
                "legacy",
            ]
        )

        self.assertEqual(
            capsule_args.algorithm_spec.make_config(
                capsule_args
            ).edge_selection,
            "legacy",
        )
        self.assertEqual(
            scale_args.algorithm_spec.make_config(scale_args).edge_selection,
            "distinct",
        )
        self.assertEqual(
            hexagon_args.algorithm_spec.make_config(
                hexagon_args
            ).edge_selection,
            "distinct",
        )
        hexagon_config = hexagon_args.algorithm_spec.make_config(
            hexagon_args
        )
        self.assertEqual(hexagon_config.hex_layout, "honeycomb")
        self.assertEqual(hexagon_config.hex_jitter, 0.0)
        self.assertEqual(hexagon_config.width_variance, 0.0)
        self.assertEqual(hexagon_config.flow_jitter, 0.0)
        self.assertEqual(
            hexagon_config.length_min,
            hexagon_config.length_max,
        )
        panel_config = panel_args.algorithm_spec.make_config(panel_args)
        self.assertEqual(panel_config.edge_selection, "distinct")
        self.assertEqual(panel_config.width_variance, 0.0)
        self.assertEqual(panel_config.flow_jitter, 0.0)
        self.assertEqual(panel_config.length_min, panel_config.length_max)
        self.assertEqual(
            explicit_legacy_args.algorithm_spec.make_config(
                explicit_legacy_args
            ).edge_selection,
            "legacy",
        )

    def test_inactive_or_conflicting_brush_options_are_rejected(self) -> None:
        parser = build_parser()
        cases = (
            (
                ["--density", "0.5", "--average-spacing", "100"],
                "alternative controls",
            ),
            (
                ["--shape-size", "0.5", "--length-min", "20"],
                "cannot be combined",
            ),
            (
                ["--length-variation", "0.2"],
                "requires --shape-size",
            ),
            (
                ["--swirl-strength", "0.8"],
                "requires --brush-shape swirl",
            ),
            (
                [
                    "--brush-shape",
                    "hexagon",
                    "--samples-per-stroke",
                    "5",
                ],
                "does not apply",
            ),
            (
                [
                    "--brush-shape",
                    "diamond-panel",
                    "--samples-per-stroke",
                    "5",
                ],
                "does not apply",
            ),
            (
                ["--hex-layout", "scattered"],
                "requires --brush-shape hexagon",
            ),
            (
                ["--hex-jitter", "0.2"],
                "requires --brush-shape hexagon",
            ),
            (
                [
                    "--brush-shape",
                    "hexagon",
                    "--hex-layout",
                    "scattered",
                    "--hex-jitter",
                    "0.2",
                ],
                "only to --hex-layout honeycomb",
            ),
            (
                [
                    "--brush-shape",
                    "hexagon",
                    "--density",
                    "0.4",
                    "--shape-size",
                    "0.5",
                ],
                "control the same panel scale",
            ),
            (
                [
                    "--brush-shape",
                    "hexagon",
                    "--hex-layout",
                    "scattered",
                    "--flow-jitter",
                    "0.2",
                ],
                "requires --flow-angle",
            ),
            (
                ["--flow-jitter", "0.2"],
                "requires --flow-angle",
            ),
            (
                ["--overlap-priority", "0.5"],
                "has no effect",
            ),
            (
                ["--overlap-order", "later"],
                "requires a positive",
            ),
            (
                [
                    "--shape-size",
                    "0.5",
                    "--length-variation",
                    "0",
                    "--overlap-order",
                    "larger",
                    "--overlap-priority",
                    "0.5",
                ],
                "requires varying stroke lengths",
            ),
            (
                [
                    "--length-min",
                    "100",
                    "--length-max",
                    "100",
                    "--overlap-order",
                    "smaller",
                    "--overlap-priority",
                    "0.5",
                ],
                "requires varying stroke lengths",
            ),
        )
        for options, message in cases:
            with self.subTest(options=options):
                args = parser.parse_args(["brush_stroke_cells", *options])
                with self.assertRaisesRegex(ValueError, message):
                    args.algorithm_spec.make_config(args)

    def test_active_shape_specific_options_are_accepted(self) -> None:
        parser = build_parser()
        cases = (
            [
                "--brush-shape",
                "swirl",
                "--swirl-strength",
                "0.8",
            ],
            [
                "--brush-shape",
                "scale",
                "--flow-jitter",
                "0.2",
            ],
            [
                "--brush-shape",
                "hexagon",
                "--shape-size",
                "0.55",
                "--flow-angle",
                "30",
                "--flow-jitter",
                "0.2",
            ],
            [
                "--flow-angle",
                "30",
                "--flow-jitter",
                "0.2",
            ],
            [
                "--overlap-order",
                "later",
                "--overlap-priority",
                "0.5",
            ],
        )
        for options in cases:
            with self.subTest(options=options):
                args = parser.parse_args(["brush_stroke_cells", *options])
                args.algorithm_spec.make_config(args)

    def test_automatic_mode_skips_and_logs_incompatible_size(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            inputs.mkdir()
            compatible = inputs / "compatible.png"
            incompatible = inputs / "incompatible.png"
            output = root / "results"
            self.write_normal(compatible, 1024)
            self.write_normal(incompatible, 512)

            exit_code = main(
                [
                    "center_average_normalization",
                    "--input",
                    str(inputs),
                    "--output-dir",
                    str(output),
                    "--block-size",
                    "256",
                ],
                project_dir=root,
            )

            self.assertEqual(exit_code, 0)
            with Image.open(output / "compatible_processed.png") as result:
                self.assertEqual(result.size, (1024, 1024))
            self.assertFalse((output / "incompatible_processed.png").exists())
            log = (output / "processing_errors.log").read_text(encoding="utf-8")
            self.assertIn("SKIPPED_SIZE", log)
            self.assertIn("incompatible.png", log)
            self.assertIn("incompatible size 512x512", log)
            manifest_path = output / "export_summary.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["tool"]["version"], __version__)
            self.assertIn("python", manifest["runtime"])
            self.assertIn("numpy", manifest["runtime"]["dependencies"])
            self.assertEqual(
                manifest["algorithm"]["name"],
                "center_average_normalization",
            )
            self.assertEqual(manifest["counts"]["discovered"], 2)
            self.assertEqual(manifest["counts"]["processed"], 1)
            self.assertEqual(manifest["counts"]["skipped"], 1)
            self.assertEqual(manifest["counts"]["failed"], 0)
            self.assertEqual(manifest["run"]["outcome"], "partial")
            self.assertEqual(manifest["run"]["expected_exit_code"], 0)
            records = {
                Path(record["source"]).name: record
                for record in manifest["files"]
            }
            self.assertEqual(records["compatible.png"]["status"], "processed")
            self.assertEqual(
                records["incompatible.png"]["category"],
                "SKIPPED_SIZE",
            )
            self.assertEqual(
                records["compatible.png"]["dimensions"],
                {"height": 1024, "width": 1024},
            )
            artifact = records["compatible.png"]["output_artifact"]
            destination = output / "compatible_processed.png"
            self.assertEqual(
                artifact["sha256"],
                hashlib.sha256(destination.read_bytes()).hexdigest(),
            )
            self.assertEqual(artifact["bytes"], destination.stat().st_size)
            self.assertFalse(
                list(output.glob(".export_summary.json.*.tmp"))
            )

    def test_requested_size_processes_only_matching_pngs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            inputs.mkdir()
            selected = inputs / "selected.png"
            filtered = inputs / "filtered.png"
            output = root / "results"
            self.write_normal(selected, 1024)
            self.write_normal(filtered, 2048)

            exit_code = main(
                [
                    "center_average_normalization",
                    "--input",
                    str(inputs),
                    "--output-dir",
                    str(output),
                    "--resolution",
                    "1024x1024",
                    "--block-size",
                    "256",
                ],
                project_dir=root,
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "selected_processed.png").exists())
            self.assertFalse((output / "filtered_processed.png").exists())
            log = (output / "processing_errors.log").read_text(encoding="utf-8")
            self.assertIn("filtered.png", log)
            self.assertIn("does not match requested filter 1024x1024", log)

    def test_bad_png_is_logged_and_later_file_still_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            inputs.mkdir()
            bad = inputs / "a_bad.png"
            good = inputs / "z_good.png"
            output = root / "results"
            Image.new("RGB", (1024, 1024), (128, 128, 255)).save(
                bad, format="JPEG"
            )
            self.write_normal(good, 1024)

            exit_code = main(
                [
                    "center_average_normalization",
                    "--input",
                    str(inputs),
                    "--output-dir",
                    str(output),
                    "--block-size",
                    "256",
                ],
                project_dir=root,
            )

            self.assertEqual(exit_code, 1)
            self.assertTrue((output / "z_good_processed.png").exists())
            log = (output / "processing_errors.log").read_text(encoding="utf-8")
            self.assertIn("ERROR", log)
            self.assertIn("a_bad.png", log)
            self.assertIn("actual format is JPEG", log)

    def test_resource_limit_skips_large_png_and_continues_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            inputs.mkdir()
            small = inputs / "a_small.png"
            large = inputs / "b_large.png"
            output = root / "results"
            self.write_normal(small, 1024)
            self.write_normal(large, 2048)

            with patch(
                "normal_blobs.runner.available_system_memory_bytes",
                return_value=8 * GIB,
            ):
                exit_code = main(
                    [
                        "center_average_normalization",
                        "--input",
                        str(inputs),
                        "--output-dir",
                        str(output),
                        "--block-size",
                        "256",
                        "--cpu-memory-limit-gb",
                        "0.3",
                    ],
                    project_dir=root,
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "a_small_processed.png").exists())
            self.assertFalse((output / "b_large_processed.png").exists())
            self.assertTrue(small.exists())
            self.assertTrue(large.exists())
            log = (output / "processing_errors.log").read_text(encoding="utf-8")
            self.assertIn("SKIPPED_RESOURCE_LIMIT", log)
            self.assertIn("b_large.png", log)
            self.assertIn("estimated CPU peak", log)

    def test_duplicate_input_stems_are_rejected_before_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_dir = root / "first"
            second_dir = root / "second"
            first_dir.mkdir()
            second_dir.mkdir()
            first = first_dir / "same.png"
            second = second_dir / "same.png"
            output = root / "results"
            self.write_normal(first, 1024)
            self.write_normal(second, 1024)

            with self.assertRaises(SystemExit):
                main(
                    [
                        "center_average_normalization",
                        "--input",
                        str(first),
                        "--input",
                        str(second),
                        "--output-dir",
                        str(output),
                    ],
                    project_dir=root,
                )

            self.assertFalse((output / "same_processed.png").exists())


if __name__ == "__main__":
    unittest.main()
