from __future__ import annotations

import unittest

from normal_blobs.algorithms import ALGORITHMS, brush_stroke_cells
from normal_blobs.resources import GIB, safe_cpu_budget_bytes
from normal_blobs.runner import fit_config_to_cpu_budget


class ResourceTests(unittest.TestCase):
    def test_automatic_budget_reserves_one_quarter_of_available_ram(self) -> None:
        self.assertEqual(safe_cpu_budget_bytes(4 * GIB, None), 3 * GIB)

    def test_user_limit_can_only_lower_the_automatic_budget(self) -> None:
        self.assertEqual(
            safe_cpu_budget_bytes(4 * GIB, 2 * GIB),
            2 * GIB,
        )
        self.assertEqual(
            safe_cpu_budget_bytes(4 * GIB, 8 * GIB),
            3 * GIB,
        )

    def test_unknown_available_memory_uses_conservative_fallback(self) -> None:
        self.assertEqual(safe_cpu_budget_bytes(None, None), 2 * GIB)
        self.assertEqual(
            safe_cpu_budget_bytes(None, 1 * GIB),
            1 * GIB,
        )

    def test_chunk_rows_are_reduced_before_a_file_is_skipped(self) -> None:
        config = brush_stroke_cells.Config(
            130,
            60,
            260,
            0.5,
            8,
            64,
            32,
            "distinct",
            128,
            brush_shape="scale",
            density=1.0,
            shape_size=1.0,
            overlap_order="later",
            overlap_priority=1.0,
        )
        adjusted, estimate, original_rows = fit_config_to_cpu_budget(
            ALGORITHMS["brush_stroke_cells"],
            4096,
            4096,
            config,
            5 * GIB,
        )

        self.assertEqual(original_rows, 128)
        self.assertLess(adjusted.chunk_rows, original_rows)
        self.assertGreaterEqual(adjusted.chunk_rows, 1)
        self.assertLessEqual(estimate.cpu_bytes, 5 * GIB)


if __name__ == "__main__":
    unittest.main()
