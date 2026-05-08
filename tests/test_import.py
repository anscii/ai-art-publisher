import tempfile
from pathlib import Path

from scripts.import_local import find_image_files, parse_created_at


def test_parse_ms_timestamp():
    dt = parse_created_at("1680030203290_out.jpg")
    assert dt is not None
    assert dt.year == 2023


def test_parse_s_timestamp():
    dt = parse_created_at("1680030203_out.jpg")
    assert dt is not None
    assert dt.year == 2023


def test_parse_unknown_filename():
    assert parse_created_at("my_artwork.jpg") is None


def test_find_image_files():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "a.jpg").write_bytes(b"")
        (p / "b.png").write_bytes(b"")
        (p / "note.txt").write_bytes(b"")
        files = find_image_files(p)
        assert len(files) == 2
        assert all(f.suffix.lower() in {".jpg", ".png"} for f in files)
