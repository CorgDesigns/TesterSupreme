from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace

import numpy as np

from normal_blobs.algorithms import (
    brush_stroke_cells,
    center_average_normalization,
    edge_gradient_cascade,
    voronoi_flow_cells,
)
from normal_blobs.algorithms.cell_common import compute_cell_averages
from normal_blobs.image_io import validate_normal_image
from normal_blobs.models import CommonOptions, RandomStreams


class AlgorithmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.image = np.full((64, 64, 3), [128.0, 128.0, 255.0])
        self.image[:4] = 0
        self.image[-4:] = 0
        self.image[:, :4] = 0
        self.image[:, -4:] = 0
        self.common = CommonOptions(
            black_threshold=10.0,
            blend_strength=1.0,
            similarity_threshold=12.0,
            hue_tweak=0.04,
            shade_tweak=12.0,
            renormalize=True,
        )

    def assert_valid_result(self, result: np.ndarray) -> None:
        self.assertEqual(result.shape, self.image.shape)
        self.assertTrue(np.isfinite(result).all())
        self.assertGreaterEqual(result.min(), 0)
        self.assertLessEqual(result.max(), 255)
        np.testing.assert_array_equal(result[0], self.image[0])

    def test_all_algorithms_process_a_small_image(self) -> None:
        cases = [
            (
                center_average_normalization,
                center_average_normalization.Config(64, 0.8),
            ),
            (
                edge_gradient_cascade,
                edge_gradient_cascade.Config(64, 0.8),
            ),
            (
                voronoi_flow_cells,
                voronoi_flow_cells.Config(24, 0.5, 2, 5, 8),
            ),
            (
                brush_stroke_cells,
                brush_stroke_cells.Config(24, 10, 30, 0.5, 5, 12, 4),
            ),
        ]
        for module, config in cases:
            with self.subTest(algorithm=module.NAME):
                result = module.process(
                    self.image.copy(),
                    self.common,
                    config,
                    RandomStreams(42, "legacy"),
                )
                self.assert_valid_result(result)

    def test_random_algorithm_is_repeatable_with_same_seed(self) -> None:
        config = brush_stroke_cells.Config(24, 10, 30, 0.5, 5, 12, 4)
        first = brush_stroke_cells.process(
            self.image.copy(),
            self.common,
            config,
            RandomStreams(123, "modern"),
        )
        second = brush_stroke_cells.process(
            self.image.copy(),
            self.common,
            config,
            RandomStreams(123, "modern"),
        )
        np.testing.assert_array_equal(first, second)

    def test_zero_blend_strength_is_a_true_no_op(self) -> None:
        no_blend = CommonOptions(
            black_threshold=10.0,
            blend_strength=0.0,
            similarity_threshold=12.0,
            hue_tweak=0.04,
            shade_tweak=12.0,
            renormalize=True,
        )
        cases = [
            (
                center_average_normalization,
                center_average_normalization.Config(64, 0.8),
            ),
            (
                edge_gradient_cascade,
                edge_gradient_cascade.Config(64, 0.8),
            ),
            (
                voronoi_flow_cells,
                voronoi_flow_cells.Config(24, 0.5, 2, 5, 8),
            ),
            (
                brush_stroke_cells,
                brush_stroke_cells.Config(24, 10, 30, 0.5, 5, 12, 4),
            ),
        ]
        for module, config in cases:
            with self.subTest(algorithm=module.NAME):
                result = module.process(
                    self.image.copy(),
                    no_blend,
                    config,
                    RandomStreams(42, "legacy"),
                )
                np.testing.assert_array_equal(result, self.image)

    def test_brush_assignment_uses_a_distinct_second_stroke(self) -> None:
        starts = np.array([[0.0, 1.0], [0.0, 6.0]])
        ends = np.array([[7.0, 1.0], [7.0, 6.0]])
        widths = np.ones(2)
        nearest, _, second, _ = brush_stroke_cells.assign_cells(
            8,
            8,
            starts,
            ends,
            widths,
            candidates=6,
            samples_per_stroke=3,
            edge_selection="distinct",
            chunk_rows=2,
        )
        self.assertTrue(np.all(nearest != second))

    def test_chunk_size_does_not_change_brush_assignment(self) -> None:
        config = brush_stroke_cells.Config(24, 10, 30, 0.5, 5, 12, 4)
        starts, ends, widths = brush_stroke_cells.generate_strokes(
            64, 64, config, RandomStreams(99, "legacy")
        )
        small_chunks = brush_stroke_cells.assign_cells(
            64, 64, starts, ends, widths, 12, 4, "legacy", 7
        )
        large_chunk = brush_stroke_cells.assign_cells(
            64, 64, starts, ends, widths, 12, 4, "legacy", 64
        )
        for small, large in zip(small_chunks, large_chunk, strict=True):
            np.testing.assert_array_equal(small, large)

    def test_chunk_size_does_not_change_multi_island_brush_output(self) -> None:
        generator = np.random.default_rng(6)
        image = np.zeros((64, 64, 3), dtype=np.float64)
        for _ in range(10):
            y, x = generator.integers(0, 56, size=2)
            height, width = generator.integers(3, 10, size=2)
            color = np.array([128, 128, 255]) + generator.integers(
                -2, 3, size=3
            )
            image[y : y + height, x : x + width] = color
        common = replace(self.common, similarity_threshold=255)
        config = brush_stroke_cells.Config(
            24, 10, 30, 0.5, 5, 12, 5, "distinct", 1, workers=1
        )

        one_row = brush_stroke_cells.process(
            image.copy(), common, config, RandomStreams(6, "legacy")
        )
        full_chunk = brush_stroke_cells.process(
            image.copy(),
            common,
            replace(config, chunk_rows=64),
            RandomStreams(6, "legacy"),
        )

        np.testing.assert_array_equal(one_row, full_chunk)

    def test_all_algorithms_keep_disconnected_islands_independent(self) -> None:
        common = replace(
            self.common,
            similarity_threshold=0,
            hue_tweak=0,
            shade_tweak=0,
        )
        first = np.zeros((64, 64, 3), dtype=np.float64)
        first[20:31, 20:31] = [255, 128, 128]
        first[33:44, 33:44] = [128, 255, 128]
        second = first.copy()
        second[33:44, 33:44] = [128, 128, 255]
        first_island = np.zeros((64, 64), dtype=bool)
        first_island[20:31, 20:31] = True
        cases = (
            (
                center_average_normalization,
                center_average_normalization.Config(64, 1.0),
            ),
            (
                edge_gradient_cascade,
                edge_gradient_cascade.Config(64, 1.0),
            ),
            (
                voronoi_flow_cells,
                voronoi_flow_cells.Config(24, 0.5, 2, 5, 8, 8),
            ),
            (
                brush_stroke_cells,
                brush_stroke_cells.Config(
                    24, 10, 30, 0.5, 5, 12, 5, "distinct", 8
                ),
            ),
        )

        for module, config in cases:
            with self.subTest(algorithm=module.NAME):
                first_output = module.process(
                    first.copy(),
                    common,
                    config,
                    RandomStreams(7, "legacy"),
                )
                second_output = module.process(
                    second.copy(),
                    common,
                    config,
                    RandomStreams(7, "legacy"),
                )
                np.testing.assert_array_equal(
                    first_output[first_island],
                    second_output[first_island],
                )
                np.testing.assert_array_equal(
                    first_output[first.sum(axis=-1) <= 10],
                    first[first.sum(axis=-1) <= 10],
                )

    def test_opposing_normal_average_uses_source_fallback(self) -> None:
        image = np.empty((64, 64, 3), dtype=np.float64)
        image[:, :32] = [255, 128, 128]
        image[:, 32:] = [0, 127, 127]
        result = center_average_normalization.process(
            image,
            replace(
                self.common,
                similarity_threshold=0,
                hue_tweak=0,
                shade_tweak=0,
            ),
            center_average_normalization.Config(64, 1.0),
            RandomStreams(1, "legacy"),
        )

        validate_normal_image(result, 10, True)
        center_vector = (result[32, 32] / 255.0) * 2.0 - 1.0
        self.assertGreater(np.linalg.norm(center_vector), 0.95)

    def test_worker_count_does_not_change_algorithm_4_output(self) -> None:
        config = brush_stroke_cells.Config(
            24, 10, 30, 0.5, 5, 12, 5, workers=1
        )
        single_threaded = brush_stroke_cells.process(
            self.image.copy(),
            self.common,
            config,
            RandomStreams(1234, "legacy"),
        )
        multi_threaded = brush_stroke_cells.process(
            self.image.copy(),
            self.common,
            replace(config, workers=4),
            RandomStreams(1234, "legacy"),
        )
        np.testing.assert_array_equal(single_threaded, multi_threaded)

    def test_algorithm_4_legacy_golden_output(self) -> None:
        yy, xx = np.mgrid[0:96, 0:96]
        image = np.stack(
            [
                96 + xx * 0.7,
                112 + yy * 0.6,
                np.full_like(xx, 230),
            ],
            axis=-1,
        ).astype(np.float64)
        image[:5] = 0
        image[-5:] = 0
        image[:, :5] = 0
        image[:, -5:] = 0

        config = brush_stroke_cells.Config(
            130, 60, 260, 0.5, 8, 18, 5, "legacy", 16
        )
        result = brush_stroke_cells.process(
            image,
            self.common,
            config,
            RandomStreams(314159, "legacy"),
        )
        pixels = np.clip(result, 0, 255).astype(np.uint8)
        digest = hashlib.sha256(pixels.tobytes()).hexdigest()
        self.assertEqual(
            digest,
            "1f07d56ae9cc6521dcf75326fd4ad3e10"
            "fb790fc618141763e78ead92ddf87fa",
        )

    def test_algorithm_4_size_profiles_have_documented_safe_limits(self) -> None:
        expected = {
            1024: (16, 256, 24.0, 160.0, 0.15),
            2048: (64, 1024, 48.0, 320.0, 0.20),
            4096: (256, 4096, 96.0, 640.0, 0.25),
        }
        for size, limits in expected.items():
            with self.subTest(size=size):
                profile = brush_stroke_cells.size_profile(size, size)
                self.assertEqual(
                    (
                        profile.minimum_cells,
                        profile.maximum_cells,
                        profile.minimum_length,
                        profile.maximum_length,
                        profile.maximum_priority_bias,
                    ),
                    limits,
                )

    def test_density_and_shape_size_stay_inside_resolution_limits(self) -> None:
        base = brush_stroke_cells.Config(
            130, 60, 260, 0.5, 8, 18, 5
        )
        for size in (1024, 2048, 4096):
            profile = brush_stroke_cells.size_profile(size, size)
            for density, expected_count in (
                (0.0, profile.minimum_cells),
                (1.0, profile.maximum_cells),
            ):
                with self.subTest(size=size, density=density):
                    config = replace(
                        base,
                        density=density,
                        shape_size=0.5,
                        length_variation=0.75,
                    )
                    starts, ends, _ = brush_stroke_cells.generate_strokes(
                        size, size, config, RandomStreams(7, "legacy")
                    )
                    lengths = np.linalg.norm(ends - starts, axis=1)
                    self.assertEqual(len(starts), expected_count)
                    self.assertGreaterEqual(
                        float(lengths.min()), profile.minimum_length
                    )
                    self.assertLessEqual(
                        float(lengths.max()), profile.maximum_length
                    )

    def test_all_brush_shapes_produce_valid_deterministic_results(self) -> None:
        image = np.full((128, 128, 3), [128.0, 128.0, 255.0])
        image[:4] = 0
        config = brush_stroke_cells.Config(
            24,
            10,
            30,
            0.5,
            5,
            12,
            5,
            "distinct",
            16,
            density=0.8,
            shape_size=0.7,
            overlap_order="later",
            overlap_priority=0.7,
        )
        outputs = {}
        for shape in brush_stroke_cells.BRUSH_SHAPES:
            with self.subTest(shape=shape):
                shape_config = replace(config, brush_shape=shape)
                first = brush_stroke_cells.process(
                    image.copy(),
                    self.common,
                    shape_config,
                    RandomStreams(88, "legacy"),
                )
                second = brush_stroke_cells.process(
                    image.copy(),
                    self.common,
                    shape_config,
                    RandomStreams(88, "legacy"),
                )
                self.assertEqual(first.shape, image.shape)
                self.assertTrue(np.isfinite(first).all())
                np.testing.assert_array_equal(first, second)
                outputs[shape] = first

        self.assertFalse(
            np.array_equal(outputs["capsule"], outputs["scale"])
        )
        self.assertFalse(
            np.array_equal(outputs["capsule"], outputs["swirl"])
        )
        self.assertFalse(
            np.array_equal(outputs["capsule"], outputs["hexagon"])
        )
        artistic_shapes = {
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
        self.assertTrue(artistic_shapes.issubset(outputs))
        artistic_digests = {
            hashlib.sha256(outputs[shape].tobytes()).hexdigest()
            for shape in artistic_shapes
        }
        self.assertEqual(len(artistic_digests), len(artistic_shapes))

    def test_new_organic_shapes_and_controls_are_distinct(self) -> None:
        image = np.full((128, 128, 3), [128.0, 128.0, 255.0])
        image[:4] = 0
        base = brush_stroke_cells.Config(
            24,
            10,
            30,
            0.5,
            5,
            12,
            5,
            "distinct",
            16,
            brush_shape="grass-clump",
            density=0.8,
            shape_size=0.7,
            curvature=0.0,
            segments=2,
            roughness=0.0,
            symmetry=1.0,
            branching=0.0,
        )
        high_detail = replace(
            base,
            curvature=1.0,
            segments=8,
            roughness=1.0,
            symmetry=0.0,
            branching=1.0,
        )
        low = brush_stroke_cells.process(
            image.copy(), self.common, base, RandomStreams(91, "legacy")
        )
        high = brush_stroke_cells.process(
            image.copy(), self.common, high_detail, RandomStreams(91, "legacy")
        )
        self.assertTrue(np.isfinite(high).all())
        self.assertFalse(np.array_equal(low, high))

        new_shapes = {
            "grass-blade",
            "grass-clump",
            "branching-twig",
            "feather",
            "fur-tuft",
            "fish-scale",
            "beetle-shell",
            "insect-wing",
            "moss-patch",
            "tentacle",
        }
        self.assertTrue(new_shapes.issubset(brush_stroke_cells.BRUSH_SHAPES))

    def test_organic_segments_are_capped_by_path_resolution(self) -> None:
        self.assertEqual(
            brush_stroke_cells.effective_segments(16, 5),
            4,
        )
        self.assertEqual(
            brush_stroke_cells.effective_segments(2, 2),
            1,
        )
        self.assertEqual(
            brush_stroke_cells.effective_segments(16, 32),
            16,
        )

        amounts = np.linspace(0.0, 1.0, 101)
        for shape in (
            "grass-blade",
            "grass-clump",
            "branching-twig",
            "feather",
            "fur-tuft",
            "fish-scale",
            "beetle-shell",
            "insect-wing",
            "moss-patch",
            "tentacle",
        ):
            with self.subTest(shape=shape):
                profile = brush_stroke_cells.taper_factor(
                    amounts,
                    shape,
                    segments=16,
                    roughness=1.0,
                    symmetry=0.0,
                    branching=1.0,
                    sample_count=5,
                )
                self.assertGreaterEqual(float(profile.min()), 0.08)
                self.assertLessEqual(float(profile.max()), 1.0)

    def test_shared_organic_controls_preserve_legacy_and_panel_geometry(self) -> None:
        image = np.full((64, 64, 3), [128.0, 128.0, 255.0])
        image[:3] = 0
        base = brush_stroke_cells.Config(
            24, 10, 30, 0.5, 5, 12, 5, "distinct", 8,
            density=0.7,
        )
        altered = replace(
            base,
            curvature=1.0,
            segments=16,
            roughness=1.0,
            symmetry=0.0,
            branching=1.0,
        )
        for shape in ("capsule", "hexagon"):
            with self.subTest(shape=shape):
                shape_base = replace(base, brush_shape=shape)
                shape_altered = replace(altered, brush_shape=shape)
                first = brush_stroke_cells.process(
                    image.copy(), self.common, shape_base,
                    RandomStreams(52, "legacy"),
                )
                second = brush_stroke_cells.process(
                    image.copy(), self.common, shape_altered,
                    RandomStreams(52, "legacy"),
                )
                np.testing.assert_array_equal(first, second)

    def test_hexagon_distance_has_six_regular_vertices(self) -> None:
        radius = 10.0
        half_height = np.sqrt(3.0) * radius / 2.0
        boundary_points = np.array(
            [
                [radius, 0.0],
                [radius / 2.0, half_height],
                [-radius / 2.0, half_height],
                [-radius, 0.0],
                [-radius / 2.0, -half_height],
                [radius / 2.0, -half_height],
                [0.0, half_height],
            ]
        )
        starts = np.array([[-radius, 0.0]])
        ends = np.array([[radius, 0.0]])
        candidates = np.zeros((len(boundary_points), 1), dtype=np.int64)

        distances = brush_stroke_cells.hexagon_distance(
            boundary_points[:, 0],
            boundary_points[:, 1],
            starts,
            ends,
            np.ones(1),
            candidates,
        )

        np.testing.assert_allclose(
            distances[:, 0],
            radius,
            rtol=0,
            atol=1e-10,
        )
        outside = brush_stroke_cells.hexagon_distance(
            np.array([0.0]),
            np.array([radius]),
            starts,
            ends,
            np.ones(1),
            np.zeros((1, 1), dtype=np.int64),
        )
        self.assertGreater(float(outside[0, 0]), radius)

    def test_centered_panel_distance_matches_expected_boundaries(self) -> None:
        radius = 10.0
        starts = np.array([[-radius, 0.0]])
        ends = np.array([[radius, 0.0]])
        widths = np.ones(1)

        diamond_points = np.array(
            [
                [radius, 0.0],
                [0.0, radius],
                [radius / 2.0, radius / 2.0],
            ]
        )
        diamond_candidates = np.zeros(
            (len(diamond_points), 1), dtype=np.int64
        )
        diamond_distances = brush_stroke_cells.panel_distance(
            diamond_points[:, 0],
            diamond_points[:, 1],
            starts,
            ends,
            widths,
            diamond_candidates,
            "diamond-panel",
        )
        np.testing.assert_allclose(
            diamond_distances[:, 0], radius, rtol=0, atol=1e-10
        )

        diagonal = radius / np.sqrt(2.0)
        octagon_points = np.array(
            [
                [radius, 0.0],
                [0.0, radius],
                [diagonal, diagonal],
            ]
        )
        octagon_candidates = np.zeros(
            (len(octagon_points), 1), dtype=np.int64
        )
        octagon_distances = brush_stroke_cells.panel_distance(
            octagon_points[:, 0],
            octagon_points[:, 1],
            starts,
            ends,
            widths,
            octagon_candidates,
            "octagon-panel",
        )
        np.testing.assert_allclose(
            octagon_distances[:, 0], radius, rtol=0, atol=1e-10
        )

    def test_hexagon_indexes_one_center_per_cell(self) -> None:
        starts = np.array([[0.0, 0.0], [10.0, 20.0]])
        ends = np.array([[10.0, 0.0], [20.0, 20.0]])

        tree, stroke_ids, points = (
            brush_stroke_cells.build_candidate_tree(
                starts,
                ends,
                samples_per_stroke=32,
                brush_shape="hexagon",
            )
        )

        self.assertEqual(tree.n, 2)
        np.testing.assert_array_equal(stroke_ids, [0, 1])
        np.testing.assert_allclose(
            points[:, 0],
            [[5.0, 0.0], [15.0, 20.0]],
        )

    def test_all_centered_panels_index_one_center_per_cell(self) -> None:
        starts = np.array([[0.0, 0.0], [10.0, 20.0]])
        ends = np.array([[10.0, 0.0], [20.0, 20.0]])
        for shape in brush_stroke_cells.CENTERED_PANEL_SHAPES:
            with self.subTest(shape=shape):
                tree, stroke_ids, points = (
                    brush_stroke_cells.build_candidate_tree(
                        starts,
                        ends,
                        samples_per_stroke=32,
                        brush_shape=shape,
                    )
                )
                self.assertEqual(tree.n, 2)
                np.testing.assert_array_equal(stroke_ids, [0, 1])
                np.testing.assert_allclose(
                    points[:, 0],
                    [[5.0, 0.0], [15.0, 20.0]],
                )

    def test_hex_honeycomb_centers_are_staggered_and_bounded(self) -> None:
        centers, spacing = brush_stroke_cells.hex_honeycomb_centers(
            1024,
            1024,
            target_count=64,
            jitter=0.0,
            rng=RandomStreams(7, "legacy"),
        )

        self.assertGreaterEqual(len(centers), 48)
        self.assertLessEqual(len(centers), 64)
        self.assertGreaterEqual(float(centers.min()), 0.0)
        self.assertLess(float(centers[:, 0].max()), 1024)
        self.assertLess(float(centers[:, 1].max()), 1024)
        first_y, second_y = np.unique(centers[:, 1])[:2]
        first_x = centers[centers[:, 1] == first_y, 0].min()
        second_x = centers[centers[:, 1] == second_y, 0].min()
        self.assertAlmostEqual(second_x - first_x, spacing / 2.0)

    def test_hex_honeycomb_jitter_is_seeded_and_bounded(self) -> None:
        first, spacing = brush_stroke_cells.hex_honeycomb_centers(
            1024,
            1024,
            target_count=64,
            jitter=0.5,
            rng=RandomStreams(11, "modern"),
        )
        second, _ = brush_stroke_cells.hex_honeycomb_centers(
            1024,
            1024,
            target_count=64,
            jitter=0.5,
            rng=RandomStreams(11, "modern"),
        )
        uniform, _ = brush_stroke_cells.hex_honeycomb_centers(
            1024,
            1024,
            target_count=64,
            jitter=0.0,
            rng=RandomStreams(11, "modern"),
        )

        np.testing.assert_array_equal(first, second)
        self.assertFalse(np.array_equal(first, uniform))
        self.assertLessEqual(
            float(np.abs(first - uniform).max()),
            spacing * 0.15 + 1e-10,
        )
        self.assertGreaterEqual(float(first.min()), 0.0)
        self.assertLessEqual(float(first[:, 0].max()), 1023.0)
        self.assertLessEqual(float(first[:, 1].max()), 1023.0)

    def test_hex_shape_size_controls_honeycomb_panel_count(self) -> None:
        base = brush_stroke_cells.Config(
            130,
            60,
            260,
            0.0,
            5,
            12,
            5,
            "distinct",
            16,
            brush_shape="hexagon",
            hex_layout="honeycomb",
        )
        small_starts, _, _ = brush_stroke_cells.generate_strokes(
            1024,
            1024,
            replace(base, shape_size=0.0),
            RandomStreams(5, "legacy"),
        )
        large_starts, _, _ = brush_stroke_cells.generate_strokes(
            1024,
            1024,
            replace(base, shape_size=1.0),
            RandomStreams(5, "legacy"),
        )

        self.assertGreater(len(small_starts), len(large_starts))
        self.assertLessEqual(
            len(small_starts),
            brush_stroke_cells.SIZE_PROFILES[1024].maximum_cells,
        )
        self.assertGreaterEqual(len(large_starts), 4)

    def test_overlap_priority_is_capped_by_resolution(self) -> None:
        starts = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
        ends = np.array([[10.0, 0.0], [20.0, 0.0], [30.0, 0.0]])
        for size in (1024, 2048, 4096):
            profile = brush_stroke_cells.size_profile(size, size)
            weights = brush_stroke_cells.overlap_weights(
                starts, ends, "larger", 1.0, profile
            )
            self.assertAlmostEqual(
                float(weights.min()),
                1.0 - profile.maximum_priority_bias,
            )
            self.assertAlmostEqual(
                float(weights.max()),
                1.0 + profile.maximum_priority_bias,
            )

    def test_overlap_priority_expands_candidate_search(self) -> None:
        base = brush_stroke_cells.requested_candidate_count(
            candidates=18,
            samples_per_stroke=5,
            edge_selection="distinct",
            has_overlap_priority=False,
        )
        prioritized = brush_stroke_cells.requested_candidate_count(
            candidates=18,
            samples_per_stroke=5,
            edge_selection="distinct",
            has_overlap_priority=True,
        )
        self.assertEqual(base, 18)
        self.assertEqual(prioritized, 36)

    def test_black_padding_isolates_uv_island_cell_averages(self) -> None:
        image = np.zeros((8, 12, 3), dtype=np.float64)
        image[1:4, 1:4] = [255.0, 128.0, 128.0]
        image[4:7, 8:11] = [128.0, 255.0, 128.0]
        nearest = np.zeros((8, 12), dtype=np.int64)
        second = np.zeros((8, 12), dtype=np.int64)
        positions = np.asarray([[6.0, 4.0]])

        isolated_positions, components = (
            brush_stroke_cells.isolate_cells_across_padding(
                image,
                nearest,
                second,
                positions,
                black_threshold=10.0,
                chunk_rows=2,
            )
        )
        averages, has_surface = compute_cell_averages(
            image,
            nearest,
            len(isolated_positions),
            black_threshold=10.0,
            chunk_rows=2,
        )

        first_cell = nearest[2, 2]
        second_cell = nearest[5, 9]
        self.assertNotEqual(first_cell, second_cell)
        self.assertEqual(len(np.unique(components)), 2)
        self.assertTrue(has_surface[first_cell])
        self.assertTrue(has_surface[second_cell])
        np.testing.assert_array_equal(
            averages[first_cell], [255.0, 128.0, 128.0]
        )
        np.testing.assert_array_equal(
            averages[second_cell], [128.0, 255.0, 128.0]
        )

    def test_taper_presets_point_the_requested_ends(self) -> None:
        amounts = np.array([0.0, 0.5, 1.0])
        sharp_start = brush_stroke_cells.taper_factor(
            amounts, "sharp-start"
        )
        sharp_end = brush_stroke_cells.taper_factor(amounts, "sharp-end")
        sharp_both = brush_stroke_cells.taper_factor(
            amounts, "sharp-both"
        )
        scale = brush_stroke_cells.taper_factor(amounts, "scale")

        self.assertLess(sharp_start[0], sharp_start[-1])
        self.assertGreater(sharp_end[0], sharp_end[-1])
        self.assertLess(sharp_both[0], sharp_both[1])
        self.assertLess(sharp_both[-1], sharp_both[1])
        self.assertLess(scale[0], scale[-1])

    def test_artistic_taper_profiles_are_bounded_and_distinct(self) -> None:
        amounts = np.linspace(0.0, 1.0, 101)
        tapered_shapes = (
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
        )
        profiles = []
        for shape in tapered_shapes:
            with self.subTest(shape=shape):
                profile = brush_stroke_cells.taper_factor(amounts, shape)
                self.assertTrue(np.isfinite(profile).all())
                self.assertGreaterEqual(float(profile.min()), 0.08)
                self.assertLessEqual(float(profile.max()), 1.0)
                profiles.append(profile)
        digests = {
            hashlib.sha256(profile.tobytes()).hexdigest()
            for profile in profiles
        }
        self.assertEqual(len(digests), len(tapered_shapes))

    def test_deformed_paths_keep_endpoints_and_change_centerlines(self) -> None:
        starts = np.array([[0.0, 0.0], [0.0, 10.0]])
        ends = np.array([[100.0, 0.0], [100.0, 10.0]])
        straight = brush_stroke_cells.build_path_points(
            starts, ends, 5, "capsule", 0.8
        )
        deformed = {}
        for shape in brush_stroke_cells.DEFORMED_PATH_SHAPES:
            with self.subTest(shape=shape):
                points = brush_stroke_cells.build_path_points(
                    starts, ends, 5, shape, 0.8
                )
                np.testing.assert_allclose(points[:, 0], starts)
                np.testing.assert_allclose(points[:, -1], ends)
                self.assertFalse(np.array_equal(points, straight))
                deformed[shape] = points
        digests = {
            hashlib.sha256(points.tobytes()).hexdigest()
            for points in deformed.values()
        }
        self.assertEqual(len(digests), len(deformed))

    def test_algorithm_4_rejects_unsafe_programmatic_workloads(self) -> None:
        unsafe_configs = (
            replace(
                brush_stroke_cells.Config(
                    24, 10, 30, 0.5, 5, 12, 4
                ),
                average_spacing=0.001,
            ),
            replace(
                brush_stroke_cells.Config(
                    24, 10, 30, 0.5, 5, 12, 4
                ),
                edge_softness=np.nan,
            ),
            replace(
                brush_stroke_cells.Config(
                    24, 10, 30, 0.5, 5, 12, 4
                ),
                candidates=1_000_000,
            ),
            replace(
                brush_stroke_cells.Config(
                    24, 10, 30, 0.5, 5, 12, 4
                ),
                density=2.0,
            ),
            replace(
                brush_stroke_cells.Config(
                    24, 10, 30, 0.5, 5, 12, 4
                ),
                workers=9,
            ),
        )
        for config in unsafe_configs:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    brush_stroke_cells.process(
                        self.image.copy(),
                        self.common,
                        config,
                        RandomStreams(42, "legacy"),
                    )


if __name__ == "__main__":
    unittest.main()
