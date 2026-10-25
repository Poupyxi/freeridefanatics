#!/usr/bin/env python3
"""Portrait filenames resolve both legacy and descriptive Drive formats."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import import_images


with tempfile.TemporaryDirectory() as library:
    library_path = Path(library)
    assert import_images.portrait_source_folder(library) == str(
        library_path / "PPInstaRiders"
    )
    (library_path / "PPRiders").mkdir()
    assert import_images.portrait_source_folder(library) == str(
        library_path / "PPRiders"
    )
    (library_path / "PPInstaRiders").mkdir()
    assert import_images.portrait_source_folder(library) == str(
        library_path / "PPInstaRiders"
    )


cases = {
    "@abel_moga21.jpg": "abelmoga21",
    "MOGA_Abel__@abel_moga21.jpg": "abelmoga21",
    "DAVIS-MEEHAN_Michaela__@michaeladavismeehan.webp": "michaeladavismeehan",
    "JONES_Mia__@mia__jones_.png": "miajones",
    "legacy.handle.jpeg": "legacyhandle",
}

for filename, expected in cases.items():
    actual = import_images.rider_handle_from_filename(filename)
    assert actual == expected, (filename, actual, expected)

assert set(import_images.rider_name_keys_from_filename(
    "KOLESCH_Jack__@jack_kolesch.jpg"
)) == {"kolesch jack", "jack kolesch"}
assert import_images.rider_name_keys_from_filename("@jack_kolesch.jpg") == ()
assert import_images.one_edit_apart("atashabradleyy", "natashabradleyy")
assert not import_images.one_edit_apart("riderone", "ridertwo")

with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
    for filename in (
        "MOGA_Abel__@abel_moga21.jpg",
        "KOLESCH_Jack__@jack_kolesch.jpg",
        "@atasha_bradleyy.jpg",
    ):
        (Path(source) / filename).touch()
    riders = [
        {"slug": "moga-abel", "display_name": "Abel Moga", "instagram": "@abel_moga21"},
        {"slug": "kolesch-jack", "display_name": "Jack Kolesch", "instagram": None},
        {"slug": "bradley-natasha", "display_name": "Natasha Bradley", "instagram": "@natasha_bradleyy"},
    ]
    imported, missing = import_images.import_riders(
        riders, source, output, "avatars", True, True, True
    )
    assert sorted(imported) == sorted(rider["slug"] for rider in riders)
    assert missing == []

print("Portrait filename matching: legacy and descriptive Drive names passed.")
