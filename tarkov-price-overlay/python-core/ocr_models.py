"""EasyOCR model metadata shared by runtime validation and packaging."""

from pathlib import Path


MODEL_SPECS = {
    "craft_mlt_25k.pth": {
        "url": "https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip",
        "md5": "2f8227d2def4037cdb3b34389dcf9ec1",
    },
    "korean_g2.pth": {
        "url": "https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/korean_g2.zip",
        "md5": "befecf7b1ca2fffb5af814a51443682d",
    },
    "cyrillic_g2.pth": {
        "url": "https://github.com/JaidedAI/EasyOCR/releases/download/v1.6.1/cyrillic_g2.zip",
        "md5": "19f85f43d9128a89ac21b8d6a06973fe",
    },
    "zh_sim_g2.pth": {
        "url": "https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/zh_sim_g2.zip",
        "md5": "b601ce7143293387d3ec4f41a66edc07",
    },
}

_READER_MODEL_FILES = {
    ("ko", "en"): ("craft_mlt_25k.pth", "korean_g2.pth"),
    ("ru", "en"): ("craft_mlt_25k.pth", "cyrillic_g2.pth"),
    ("ch_sim", "en"): ("craft_mlt_25k.pth", "zh_sim_g2.pth"),
}


def required_model_files(langs: tuple[str, ...]) -> tuple[str, ...]:
    """Return model files required by the app's supported EasyOCR readers."""
    return _READER_MODEL_FILES.get(tuple(langs), ("craft_mlt_25k.pth",))


def missing_model_files(model_dir: str | Path, langs: tuple[str, ...]) -> tuple[str, ...]:
    root = Path(model_dir)
    return tuple(
        filename
        for filename in required_model_files(langs)
        if not (root / filename).is_file()
    )


def model_diagnostic(model_dir: str | Path, langs: tuple[str, ...]) -> str | None:
    missing = missing_model_files(model_dir, langs)
    if not missing:
        return None
    return (
        f"Packaged OCR model(s) missing for langs={langs}: "
        f"{', '.join(missing)} (expected in {Path(model_dir)})"
    )
