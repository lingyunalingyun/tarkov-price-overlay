import importlib
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from ocr_models import missing_model_files, model_diagnostic, required_model_files


@contextmanager
def _stubbed_ocr_module():
    fake_cv2 = ModuleType("cv2")
    fake_easyocr = ModuleType("easyocr")
    fake_numpy = ModuleType("numpy")

    class FakeReader:
        calls = []

        def __init__(self, langs, **kwargs):
            self.langs = langs
            self.kwargs = kwargs
            FakeReader.calls.append((langs, kwargs))

    fake_easyocr.Reader = FakeReader
    fake_numpy.ndarray = object
    with patch.dict(
        sys.modules,
        {"cv2": fake_cv2, "easyocr": fake_easyocr, "numpy": fake_numpy},
    ):
        sys.modules.pop("ocr", None)
        module = importlib.import_module("ocr")
        try:
            yield module, FakeReader
        finally:
            sys.modules.pop("ocr", None)


class OCRModelTests(unittest.TestCase):
    def test_zh_reader_requires_shared_detector_and_chinese_model(self) -> None:
        self.assertEqual(
            required_model_files(("ch_sim", "en")),
            ("craft_mlt_25k.pth", "zh_sim_g2.pth"),
        )

    def test_existing_reader_models_remain_unchanged(self) -> None:
        self.assertEqual(
            required_model_files(("ko", "en")),
            ("craft_mlt_25k.pth", "korean_g2.pth"),
        )
        self.assertEqual(
            required_model_files(("ru", "en")),
            ("craft_mlt_25k.pth", "cyrillic_g2.pth"),
        )

    def test_missing_chinese_model_has_controlled_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            model_dir = Path(temp_dir)
            (model_dir / "craft_mlt_25k.pth").touch()
            self.assertEqual(
                missing_model_files(str(model_dir), ("ch_sim", "en")),
                ("zh_sim_g2.pth",),
            )
            diagnostic = model_diagnostic(model_dir, ("ch_sim", "en"))
            self.assertIn("zh_sim_g2.pth", diagnostic)
            self.assertIn("ch_sim", diagnostic)

    def test_reader_is_lazy_and_source_mode_allows_downloads(self) -> None:
        with _stubbed_ocr_module() as (ocr, reader):
            self.assertEqual(reader.calls, [])
            with patch.object(ocr, "_is_packaged", return_value=False):
                ocr._get_reader(("ch_sim", "en"))
            self.assertEqual(len(reader.calls), 1)
            self.assertTrue(reader.calls[0][1]["download_enabled"])

    def test_packaged_missing_chinese_model_is_controlled(self) -> None:
        with _stubbed_ocr_module() as (ocr, _reader):
            with tempfile.TemporaryDirectory() as temp_dir:
                ocr.MODEL_DIR = temp_dir
                Path(temp_dir, "craft_mlt_25k.pth").touch()
                with patch.object(ocr, "_is_packaged", return_value=True):
                    with self.assertRaises(ocr.OCRModelUnavailableError) as raised:
                        ocr._get_reader(("ch_sim", "en"))
                    self.assertIn("zh_sim_g2.pth", str(raised.exception))

    def test_packaged_missing_chinese_model_returns_no_fragments(self) -> None:
        with _stubbed_ocr_module() as (ocr, _reader):
            with tempfile.TemporaryDirectory() as temp_dir:
                ocr.MODEL_DIR = temp_dir
                Path(temp_dir, "craft_mlt_25k.pth").touch()
                with patch.object(ocr, "_is_packaged", return_value=True):
                    self.assertEqual(
                        ocr.recognize_text_fragments(object(), ("ch_sim", "en")),
                        [],
                    )

    def test_packaged_reader_load_error_is_controlled(self) -> None:
        with _stubbed_ocr_module() as (ocr, reader):
            with tempfile.TemporaryDirectory() as temp_dir:
                ocr.MODEL_DIR = temp_dir
                Path(temp_dir, "craft_mlt_25k.pth").touch()
                Path(temp_dir, "zh_sim_g2.pth").touch()
                with patch.object(ocr, "_is_packaged", return_value=True):
                    with patch.object(reader, "__init__", side_effect=OSError("corrupt model")):
                        with self.assertRaises(ocr.OCRModelUnavailableError) as raised:
                            ocr._get_reader(("ch_sim", "en"))
                    self.assertIn("failed to load", str(raised.exception))
                    self.assertIn("corrupt model", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
