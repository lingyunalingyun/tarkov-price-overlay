"""Download and verify the EasyOCR models needed by the packaged sidecar."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python-core"))

from ocr_models import MODEL_SPECS  # noqa: E402


MODEL_DIR = ROOT / "python-core" / "models" / "easyocr"


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_and_extract(
    filename: str,
    spec: dict[str, str],
    destination: Path,
    work_dir: Path,
) -> None:
    archive = work_dir / f"{filename}.zip"
    print(f"[ocr-models] downloading {filename}")
    urllib.request.urlretrieve(spec["url"], archive)
    with zipfile.ZipFile(archive) as bundle:
        members = [
            member for member in bundle.infolist()
            if Path(member.filename).name == filename
        ]
        if not members:
            raise RuntimeError(f"EasyOCR archive does not contain {filename}")
        member = members[0]
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        with bundle.open(member) as source, temporary.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        try:
            if _md5(temporary) != spec["md5"]:
                raise RuntimeError(f"MD5 mismatch for downloaded {filename}")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tarkov-easyocr-") as temporary:
        work_dir = Path(temporary)
        for filename, spec in MODEL_SPECS.items():
            destination = MODEL_DIR / filename
            if destination.is_file() and _md5(destination) == spec["md5"]:
                print(f"[ocr-models] verified {filename}")
                continue
            _download_and_extract(filename, spec, destination, work_dir)
            print(f"[ocr-models] ready {destination}")


if __name__ == "__main__":
    main()
