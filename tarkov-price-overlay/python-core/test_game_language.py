import unittest

from game_language import catalog_locale, normalize_game_lang, ocr_languages
from tarkov_api import _canon, _is_junk_ocr


class GameLanguageTests(unittest.TestCase):
    def test_zh_is_accepted(self) -> None:
        self.assertEqual(normalize_game_lang("zh"), "zh")

    def test_zh_uses_simplified_chinese_easyocr(self) -> None:
        self.assertEqual(ocr_languages("zh"), ("ch_sim", "en"))

    def test_en_reuses_the_warmed_ko_en_reader(self) -> None:
        self.assertEqual(ocr_languages("en"), ("ko", "en"))

    def test_zh_catalog_locale_stays_zh(self) -> None:
        self.assertEqual(catalog_locale("zh"), "zh")
        self.assertNotIn("ch_sim", catalog_locale("zh"))

    def test_short_chinese_names_are_not_junk(self) -> None:
        self.assertFalse(_is_junk_ocr("枪"))
        self.assertFalse(_is_junk_ocr("钥匙"))
        self.assertTrue(_is_junk_ocr("."))

    def test_nfkc_normalizes_full_width_text_before_matching(self) -> None:
        self.assertEqual(_canon("ＡＫ－７４"), "ak-74")
        self.assertTrue(_is_junk_ocr("１２３"))


if __name__ == "__main__":
    unittest.main()
