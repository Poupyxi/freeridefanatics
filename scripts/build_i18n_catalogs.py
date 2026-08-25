#!/usr/bin/env python3
"""Build cached browser translation catalogs from the generated English site.

The translation engine is only used while generating the catalogs. Visitors load
small local JSON files; no page content is sent to a third-party service.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, Comment


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("fr", "de", "es", "it", "pt", "nl", "pl", "ja", "zh-cn")
TRANSLATABLE_ATTRIBUTES = ("alt", "aria-label", "placeholder", "title")
SKIPPED_PARENTS = {"script", "style", "noscript", "svg", "code", "pre"}
PLACEHOLDER = "[{:04d}]"
DYNAMIC_STRINGS = {
    "View profile",
    "Random Women",
    "Random Men",
    "Common equipment",
    "Random equipment",
    "Used by both selected riders.",
    "Used by one of the selected riders.",
    "Explore category",
    "Brake Disc",
}


def source_pages() -> list[Path]:
    pages = []
    for path in ROOT.rglob("*.html"):
        relative = path.relative_to(ROOT)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if relative.parts[:1] == ("guides",) and relative.parts[1:2] != ("en",):
            continue
        pages.append(path)
    return sorted(pages)


def collect_strings() -> list[str]:
    strings: set[str] = set(DYNAMIC_STRINGS)
    for path in source_pages():
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
        for node in soup.find_all(string=True):
            if isinstance(node, Comment) or node.parent.name in SKIPPED_PARENTS:
                continue
            value = str(node).strip()
            if value:
                strings.add(value)
        for element in soup.find_all(True):
            for attribute in TRANSLATABLE_ATTRIBUTES:
                value = str(element.get(attribute, "")).strip()
                if value:
                    strings.add(value)
        if soup.title and soup.title.string:
            strings.add(soup.title.string.strip())
        for meta in soup.select('meta[name="description"], meta[property="og:title"], meta[property="og:description"], meta[name="twitter:title"], meta[name="twitter:description"]'):
            value = str(meta.get("content", "")).strip()
            if value:
                strings.add(value)
    return sorted(strings, key=lambda value: (len(value), value))


def protected_terms() -> list[str]:
    terms = {"RidersFanatics", "UCI", "DH", "World Cup"}
    riders = json.loads((ROOT / "data" / "riders.json").read_text(encoding="utf-8"))
    for rider in riders:
        for key in ("name", "first_name", "last_name", "team", "instagram"):
            if rider.get(key):
                terms.add(str(rider[key]).strip())
        bike = rider.get("bike") or {}
        for key in ("brand", "model"):
            if bike.get(key):
                terms.update(part.strip() for part in str(bike[key]).split(";") if part.strip())
        for equipment in rider.get("equipment") or []:
            for key in ("brand", "model_detail"):
                if equipment.get(key):
                    terms.update(part.strip() for part in str(equipment[key]).split(";") if part.strip())
    competitions = json.loads((ROOT / "data" / "competitions.json").read_text(encoding="utf-8"))

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"name", "short_name", "organization"} and isinstance(item, str):
                    terms.add(item.strip())
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(competitions)
    return sorted((term for term in terms if len(term) >= 2), key=len, reverse=True)


def glossary_pattern(terms: list[str]) -> re.Pattern[str]:
    return re.compile(
        r"(?<![\w])(?:" + "|".join(re.escape(term) for term in terms) + r")(?![\w])",
        re.IGNORECASE,
    )


def protect(text: str, pattern: re.Pattern[str]) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}
    index = 0
    def replace(match):
        nonlocal index
        token = PLACEHOLDER.format(index)
        replacements[token] = match.group(0)
        index += 1
        return token

    protected = pattern.sub(replace, text)
    return protected, replacements


def restore(text: str, replacements: dict[str, str]) -> str:
    restored = text
    for token, original in replacements.items():
        restored = restored.replace(token, original)
    return restored


def should_translate(text: str, glossary: set[str]) -> bool:
    if text.casefold() in glossary or len(text) < 2:
        return False
    return bool(re.search(r"[A-Za-z]", text))


def sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)


def translate_around_terms(text: str, pattern: re.Pattern[str], translator) -> str:
    """Safe fallback when a model mutates or drops placeholder tokens."""
    output = []
    position = 0
    for match in pattern.finditer(text):
        fragment = text[position:match.start()]
        output.append(translator(fragment) if re.search(r"[A-Za-z]", fragment) else fragment)
        output.append(match.group(0))
        position = match.end()
    fragment = text[position:]
    output.append(translator(fragment) if re.search(r"[A-Za-z]", fragment) else fragment)
    return "".join(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="+", choices=TARGETS, default=list(TARGETS))
    parser.add_argument("--model-dir", type=Path, help="Directory containing installed Argos models")
    args = parser.parse_args()
    if args.model_dir:
        import os
        os.environ["ARGOS_PACKAGES_DIR"] = str(args.model_dir.resolve())

    from argostranslate import translate

    strings = collect_strings()
    terms = protected_terms()
    pattern = glossary_pattern(terms)
    glossary = {term.casefold() for term in terms}
    output_dir = ROOT / "assets" / "i18n"
    output_dir.mkdir(parents=True, exist_ok=True)

    for language in args.languages:
        target = "zh" if language == "zh-cn" else language
        destination = output_dir / f"{language}.json"
        existing = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else {}
        catalog = {}
        translated_templates: dict[str, str] = {}
        for number, source in enumerate(strings, 1):
            if source in existing:
                catalog[source] = existing[source]
                source_sentences = sentences(source)
                translated_sentences = sentences(existing[source])
                if len(source_sentences) == len(translated_sentences):
                    for source_sentence, translated_sentence in zip(source_sentences, translated_sentences):
                        protected_source, _ = protect(source_sentence, pattern)
                        protected_translation, _ = protect(translated_sentence, pattern)
                        source_tokens = re.findall(r"\[\d{4}\]", protected_source)
                        translated_tokens = re.findall(r"\[\d{4}\]", protected_translation)
                        if len(source_tokens) == len(translated_tokens):
                            translated_templates.setdefault(protected_source, protected_translation)
                continue
            if not should_translate(source, glossary):
                continue
            translated_parts = []
            for sentence in sentences(source):
                protected, replacements = protect(sentence, pattern)
                translated = translated_templates.get(protected)
                if translated is None:
                    translated = translate.translate(protected, "en", target)
                    translated_templates[protected] = translated
                if all(translated.count(token) == 1 for token in replacements):
                    translated = restore(translated, replacements)
                else:
                    translated = translate_around_terms(
                        sentence,
                        pattern,
                        lambda fragment: translate.translate(fragment, "en", target),
                    )
                translated_parts.append(translated)
            catalog[source] = " ".join(translated_parts)
            if number % 100 == 0:
                destination.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                print(f"{language}: {number}/{len(strings)}", flush=True)
        destination.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{language}: wrote {len(catalog)} translations to {destination.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
