from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from normal_blobs.image_io import (
    capture_padding_snapshot,
    inspect_png,
    load_normal_image,
    save_normal_image,
    validate_padding_preserved,
)
from normal_blobs.runner import compatible_size_message


class ImageInspectionTests(unittest.TestCase):
    def test_all_supported_square_sizes_are_accepted_automatically(self) -> None:
        for size in (1024, 2048, 4096):
            with self.subTest(size=size):
                self.assertIsNone(compatible_size_message(size, size, None))

    def test_non_square_and_unsupported_sizes_are_rejected(self) -> None:
        self.assertIn(
            "incompatible size 1024x2048",
            compatible_size_message(1024, 2048, None),
        )
        self.assertIn(
            "incompatible size 512x512",
            compatible_size_message(512, 512, None),
        )

    def test_png_inspection_rejects_a_mislabeled_non_png(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "not_really.png"
            Image.new("RGB", (1024, 1024), (128, 128, 255)).save(
                path, format="JPEG"
            )
            with self.assertRaisesRegex(ValueError, "actual format is JPEG"):
                inspect_png(path)

    def test_loader_rejects_non_opaque_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "alpha.png"
            Image.new("RGBA", (32, 32), (128, 128, 255, 128)).save(path)
            self.assertEqual(inspect_png(path), (32, 32))
            with self.assertRaisesRegex(ValueError, "non-opaque"):
                load_normal_image(path)

    def test_loader_accepts_fully_opaque_rgba(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "opaque.png"
            Image.new("RGBA", (32, 32), (128, 128, 255, 255)).save(path)
            self.assertEqual(inspect_png(path), (32, 32))
            self.assertEqual(load_normal_image(path).shape, (32, 32, 3))

    def test_png_inspection_rejects_16_bit_storage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sixteen_bit.png"
            pixels = np.full((32, 32), 32768, dtype=np.uint16)
            Image.fromarray(pixels).save(path)
            with self.assertRaisesRegex(ValueError, "bit depth is 16"):
                inspect_png(path)

    def test_png_inspection_rejects_animation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "animated.png"
            first = Image.new("RGB", (32, 32), (128, 128, 255))
            second = Image.new("RGB", (32, 32), (128, 255, 128))
            first.save(
                path,
                save_all=True,
                append_images=[second],
                duration=100,
                loop=0,
            )
            with self.assertRaisesRegex(ValueError, "animated"):
                inspect_png(path)

    def test_export_rejects_non_finite_pixels_without_writing_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.png"
            array = np.full((16, 16, 3), [128.0, 128.0, 255.0])
            array[4, 5, 1] = np.nan

            with self.assertRaisesRegex(ValueError, "non-finite"):
                save_normal_image(array, path)

            self.assertFalse(path.exists())
            self.assertEqual(list(path.parent.glob(".*.tmp.png")), [])

    def test_export_rejects_an_all_black_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "black.png"
            array = np.zeros((16, 16, 3), dtype=np.float64)

            with self.assertRaisesRegex(ValueError, "no surface-normal"):
                save_normal_image(array, path)

            self.assertFalse(path.exists())

    def test_export_rejects_non_unit_normals_when_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid_normals.png"
            array = np.full((16, 16, 3), [255.0, 255.0, 255.0])

            with self.assertRaisesRegex(ValueError, "non-unit"):
                save_normal_image(array, path)

            self.assertFalse(path.exists())

    def test_export_verifies_and_commits_a_valid_rgb_png(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "valid.png"
            array = np.full((16, 16, 3), [128.0, 128.0, 255.0])

            save_normal_image(array, path)

            with Image.open(path) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(image.size, (16, 16))

    def test_padding_integrity_gate_rejects_any_changed_padding(self) -> None:
        source = np.full((16, 16, 3), [128.0, 128.0, 255.0])
        source[:2] = 0
        snapshot = capture_padding_snapshot(source, 10.0)
        result = source.copy()
        result[0, 3] = [128.0, 128.0, 255.0]

        with self.assertRaisesRegex(ValueError, "black-padding pixel"):
            validate_padding_preserved(snapshot, result)

        validate_padding_preserved(snapshot, source.copy())

    def test_padding_snapshot_detects_in_place_input_mutation(self) -> None:
        source = np.full((16, 16, 3), [128.0, 128.0, 255.0])
        source[:2] = 0
        snapshot = capture_padding_snapshot(source, 10.0)
        source[0, 3] = [128.0, 128.0, 255.0]

        with self.assertRaisesRegex(ValueError, "black-padding pixel"):
            validate_padding_preserved(snapshot, source)


if __name__ == "__main__":
    unittest.main()
