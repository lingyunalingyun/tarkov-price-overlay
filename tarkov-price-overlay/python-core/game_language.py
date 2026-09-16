"""Game-client language helpers shared by OCR and catalog requests."""

from typing import Literal, cast


GameLang = Literal["ko", "en", "ru", "zh"]

_OCR_LANGUAGES: dict[GameLang, tuple[str, ...]] = {
    "ko": ("ko", "en"),
    "en": ("ko", "en"),
    "ru": ("ru", "en"),
    "zh": ("ch_sim", "en"),
}


def normalize_game_lang(lang: str) -> GameLang:
    """Keep the existing Korean fallback for invalid client input."""
    if lang in _OCR_LANGUAGES:
        return cast(GameLang, lang)
    return "ko"


def ocr_languages(lang: str) -> tuple[str, ...]:
    """Map an EFT language code to EasyOCR language codes."""
    return _OCR_LANGUAGES[normalize_game_lang(lang)]


def catalog_locale(lang: str) -> GameLang:
    """Return the locale sent to tarkov.dev and JSON catalog sources.

    EasyOCR uses ``ch_sim`` internally, but catalog APIs use ``zh``.
    """
    return normalize_game_lang(lang)
