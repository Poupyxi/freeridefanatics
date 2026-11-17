#!/usr/bin/env python3
"""Winter equipment links without a season must remain rider-specific."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sync_notion import CATEGORY_MAP, equipment_link_scopes


primary = "summer-season"
winter = {"winter-season"}


def scopes(seasons, category, disciplines, participated=False):
    return equipment_link_scopes(
        seasons, category, disciplines, primary, winter, participated
    )


assert scopes(set(), "Skis", ["Ski Freeride"]) == (False, True)
assert scopes(set(), "Snowboard", ["Snowboard Freeride"]) == (False, True)
assert scopes(set(), "Bindings", ["Ski Freeride"]) == (False, True)
assert scopes(set(), "Skis", ["Bike Downhill"], True) == (False, False)
assert scopes(set(), "Frame", ["Bike Downhill"], True) == (True, False)
assert scopes({primary}, "Frame", ["Bike Downhill"], True) == (True, False)
assert scopes({"winter-season"}, "Skis", ["Ski Freeride"]) == (False, True)
assert scopes({"other-season"}, "Skis", ["Ski Freeride"]) == (False, False)
assert CATEGORY_MAP["SacAirbag"] == "Avalanche Safety"
print("Winter equipment assignment preserves Ski/Snowboard and Summer isolation.")
