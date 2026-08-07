#!/usr/bin/env python3
"""
RidersFanatics — data checks run against the sheet before every build.

Why this exists: for months the standings were inverted because the placing
column was summed as if it were points. Nothing caught it. The numbers were
wrong on every page, and the site kept building happily. Every check below
comes from a defect that actually shipped.

sync.py refuses to write riders.json when a check of severity ERROR fails.
`--force` bypasses that, `--check` reports and writes nothing.
"""
import collections
import re
import unicodedata

# Position -> points. The women's field is shorter and diverges from the men's
# below 6th place, so the two ladders have to be kept apart — deriving a
# position from a women's result with the men's scale is how the placings
# silently drifted apart from the points.
POINTS_LADDERS = {
    "Men Elite": [200, 160, 140, 125, 110, 95, 90, 85, 80, 75, 70, 65, 60, 55,
                  50, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30],
    "Women Elite": [200, 160, 140, 125, 110, 95, 80, 70, 60, 55, 50, 45, 40, 35, 30],
}

DNX = {"DNS", "DNF", "DSQ", "DQ", "DNQ", "OTL"}


def fold(s):
    """Comparison form for names that should be the same thing."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, check, detail):
        self.errors.append((check, detail))

    def warn(self, check, detail):
        self.warnings.append((check, detail))

    @property
    def ok(self):
        return not self.errors

    def render(self):
        out = []
        for label, rows in (("ERROR", self.errors), ("WARN", self.warnings)):
            grouped = collections.OrderedDict()
            for check, detail in rows:
                grouped.setdefault(check, []).append(detail)
            for check, details in grouped.items():
                out.append(f"  {label}  {check} ({len(details)})")
                for d in details[:8]:
                    out.append(f"           {d}")
                if len(details) > 8:
                    out.append(f"           … and {len(details) - 8} more")
        return "\n".join(out)


def run(riders, result_keys, competition):
    """riders: assembled rider dicts. result_keys: (first_slug, last_slug) for
    every row of the results tab, so riders scoring points without a profile
    are caught rather than silently dropped."""
    rep = Report()

    # --- a rider scoring points but absent from the Profils tab never reaches
    # the site at all: no page, no standings row, and the placings of everyone
    # behind them shift by one.
    profiled = {(fold(r["first_name"]), fold(r["last_name"])) for r in riders}
    for first, last in sorted(result_keys):
        if (fold(first), fold(last)) not in profiled:
            rep.error("results with no profile", f"{first} {last}")

    # --- the equipment tabs are keyed on the Instagram handle, so a rider
    # without one gets a page with an empty setup.
    seen_handles = {}
    for r in riders:
        handle = (r.get("instagram") or "").strip()
        if not handle:
            rep.error("no Instagram handle", r["name"])
            continue
        if fold(handle) in seen_handles:
            rep.error("duplicate Instagram handle",
                      f"{handle} — {seen_handles[fold(handle)]} and {r['name']}")
        seen_handles[fold(handle)] = r["name"]

    # --- teams are free text, so one spelling difference splits a team's total
    # across two rows of the standings.
    spellings = collections.defaultdict(set)
    for r in riders:
        team = r.get("team")
        if team:
            spellings[fold(team)].add(team)
    for variants in spellings.values():
        if len(variants) > 1:
            rep.error("team spelled several ways", " | ".join(sorted(variants)))

    # --- points and placings
    per_round = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in riders:
        ladder = POINTS_LADDERS.get(r["gender_category"])
        for h in r.get("competition_history") or []:
            if h.get("category") != competition:
                continue
            where = f"{r['name']} · {h['event']}"
            place, points, status = h.get("place"), h.get("points"), h.get("result")
            if status in DNX:
                continue
            if place is not None and points is None:
                rep.error("placed but no points", f"{where} — {place}")
            elif points is not None and place is None:
                rep.error("points but no placing", f"{where} — {points} pts")
            if points is not None and ladder and points not in ladder:
                rep.error("points off the ladder", f"{where} — {points} pts")
            if place and points and ladder and place <= len(ladder) and ladder[place - 1] != points:
                rep.error("placing contradicts points",
                          f"{where} — {place} would be {ladder[place - 1]}, sheet says {points}")
            if place:
                per_round[(r["gender_category"], h["event"])][place].append(r["name"])

    for (group, event), places in sorted(per_round.items()):
        for place, names in sorted(places.items()):
            if len(names) > 1:
                rep.error("same placing twice",
                          f"{group} · {event} — {place}: {', '.join(sorted(names))}")

    # --- round labels reach the standings headers, every rider's results table
    # and the JSON-LD, so untranslated ones are visible on an English site.
    french = re.compile(r"autriche|italie|suisse|allemagne|espagne|juin|juillet|"
                        r"ao[uû]t|mai\b|septembre", re.I)
    for event in sorted({h["event"] for r in riders
                         for h in r.get("competition_history") or []}):
        if french.search(event):
            rep.warn("round label still in French", event)
        if "  " in event:
            rep.warn("double space in round label", repr(event))

    # --- a brand with no model competes against its own models in the
    # equipment leaderboards, so the category leader shown can be wrong.
    models = collections.defaultdict(set)
    for r in riders:
        for i in r.get("equipment") or []:
            models[(i["category"], i["brand"])].add(i["model_detail"].split(";")[0])
    for (category, brand), variants in sorted(models.items()):
        if "" in variants and len(variants) > 1:
            named = sorted(v for v in variants if v)
            rep.warn("brand used with and without a model",
                     f"{category} · {brand} — bare, plus {', '.join(named[:3])}"
                     + (f" +{len(named) - 3}" if len(named) > 3 else ""))

    return rep
