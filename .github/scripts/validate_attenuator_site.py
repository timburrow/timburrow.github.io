#!/usr/bin/env python3
"""Validate generated Attenuator pages, links, metadata, and image alternatives."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPOSITORY_ROOT / "attenuator"
LOCALES = ("en", "es", "fr", "ja", "ko", "zh-Hans", "zh-Hant")
ALLOWED_EXTERNAL_HOSTS = {"apps.apple.com", "github.com", "timburrow.github.io"}
APP_STORE_URL = "https://apps.apple.com/ca/app/attenuator/id367216554"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang: str | None = None
        self.h1_count = 0
        self.script_count = 0
        self.links: list[str] = []
        self.images: list[tuple[str, str | None]] = []
        self.alternates: list[str] = []
        self.has_canonical = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.html_lang = values.get("lang")
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "script":
            self.script_count += 1
        elif tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        elif tag == "img":
            self.images.append((values.get("src") or "", values.get("alt")))
        elif tag == "link":
            rel = values.get("rel")
            href = values.get("href")
            if rel == "canonical" and href:
                self.has_canonical = True
                self.links.append(href)
            elif rel == "alternate" and href:
                self.alternates.append(values.get("hreflang") or "")
                self.links.append(href)


def local_target(url: str) -> Path | None:
    if url.startswith("mailto:") or url.startswith("#"):
        return None
    parsed = urlparse(url)
    if parsed.scheme:
        if parsed.scheme not in {"http", "https"}:
            raise AssertionError(f"Unexpected URL scheme: {url}")
        if parsed.netloc not in ALLOWED_EXTERNAL_HOSTS:
            raise AssertionError(f"Unexpected external host: {url}")
        if parsed.netloc != "timburrow.github.io":
            return None
        path = parsed.path
    else:
        path = parsed.path
    if not path.startswith("/attenuator/"):
        return None
    relative = path.removeprefix("/")
    target = REPOSITORY_ROOT / relative
    return target / "index.html" if path.endswith("/") else target


def validate() -> None:
    required = {SITE_ROOT / "index.html", SITE_ROOT / "privacy.html"}
    for locale in LOCALES:
        required.update(
            {
                SITE_ROOT / locale / "index.html",
                SITE_ROOT / locale / "support" / "index.html",
                SITE_ROOT / locale / "privacy" / "index.html",
            }
        )
    missing = sorted(str(path) for path in required if not path.is_file())
    if missing:
        raise AssertionError(f"Missing required pages: {missing}")

    for path in sorted(required):
        source = path.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(source)
        if not parser.html_lang:
            raise AssertionError(f"{path}: missing html lang")
        if parser.h1_count != 1:
            raise AssertionError(f"{path}: expected one h1, found {parser.h1_count}")
        if parser.script_count:
            raise AssertionError(f"{path}: scripts are not expected")
        if not parser.has_canonical:
            raise AssertionError(f"{path}: missing canonical metadata")
        if sorted(parser.alternates) != sorted((*LOCALES, "x-default")):
            raise AssertionError(f"{path}: incomplete hreflang metadata")
        if source.count('href="/nmrtutor/"') != 1:
            raise AssertionError(f"{path}: expected one NMR Tutor header link")
        if source.count('src="/nmrtutor/assets/app-icon.png"') != 1:
            raise AssertionError(f"{path}: expected one NMR Tutor header icon")
        for src, alt in parser.images:
            if alt is None:
                raise AssertionError(f"{path}: image is missing alt text: {src}")
            target = local_target(src)
            if target is not None and not target.is_file():
                raise AssertionError(f"{path}: missing image: {src}")
        for url in parser.links:
            target = local_target(url)
            if target is not None and not target.is_file():
                raise AssertionError(f"{path}: broken link: {url}")

    landing_pages = [SITE_ROOT / "index.html", *(SITE_ROOT / locale / "index.html" for locale in LOCALES)]
    for path in landing_pages:
        source = path.read_text(encoding="utf-8")
        if source.count(f'href="{APP_STORE_URL}"') != 2:
            raise AssertionError(f"{path}: expected two App Store links")


def main() -> int:
    try:
        validate()
        print(f"Validated {len(LOCALES)} localized Attenuator page sets.")
        return 0
    except (AssertionError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
