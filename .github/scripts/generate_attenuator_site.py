#!/usr/bin/env python3
"""Generate the localized Attenuator landing, support, and privacy pages."""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTENT_PATH = REPOSITORY_ROOT / ".github" / "data" / "attenuator-content.json"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "attenuator"
EXPECTED_LOCALES = ("en", "es", "fr", "ja", "ko", "zh-Hans", "zh-Hant")
EXPECTED_FEATURES = ("pulse", "power", "pressure", "field")


class GenerationError(RuntimeError):
    pass


def load_content() -> dict:
    content = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
    locales = content.get("locales", {})
    if tuple(locales) != EXPECTED_LOCALES:
        raise GenerationError(f"Expected locales {EXPECTED_LOCALES}, found {tuple(locales)}")

    required_site_keys = {
        "canonical_origin",
        "app_store_url",
        "support_email",
        "issues_url",
        "effective_date",
    }
    if not required_site_keys.issubset(content.get("site", {})):
        raise GenerationError("Site configuration is incomplete")

    for locale, localized in locales.items():
        features = localized.get("home", {}).get("features", [])
        feature_ids = tuple(feature.get("id") for feature in features)
        if feature_ids != EXPECTED_FEATURES:
            raise GenerationError(f"{locale}: expected feature IDs {EXPECTED_FEATURES}, found {feature_ids}")
        if len(localized.get("support", {}).get("cards", [])) != 3:
            raise GenerationError(f"{locale}: support must contain exactly three troubleshooting cards")
        if len(localized.get("privacy", {}).get("sections", [])) != 7:
            raise GenerationError(f"{locale}: privacy must contain exactly seven sections")
        screenshot_locale = localized.get("screenshot_locale")
        for feature_id in EXPECTED_FEATURES:
            screenshot = REPOSITORY_ROOT / "attenuator" / "assets" / "screenshots" / screenshot_locale / f"{feature_id}.png"
            if not screenshot.is_file():
                raise GenerationError(f"{locale}: missing screenshot {screenshot}")

    icon = REPOSITORY_ROOT / "attenuator" / "assets" / "app-icon.png"
    stylesheet = REPOSITORY_ROOT / "attenuator" / "assets" / "site.css"
    if not icon.is_file() or not stylesheet.is_file():
        raise GenerationError("Attenuator icon or stylesheet is missing")
    return content


def route(locale: str, section: str) -> str:
    suffix = "" if section == "home" else f"{section}/"
    return f"/attenuator/{locale}/{suffix}"


def language_links(content: dict, section: str, current: str | None) -> str:
    links = []
    for locale, localized in content["locales"].items():
        current_attr = ' aria-current="true"' if locale == current else ""
        links.append(
            f'<a lang="{escape(locale)}" hreflang="{escape(locale)}" href="{escape(route(locale, section))}"{current_attr}>'
            f'{escape(localized["language_name"])}</a>'
        )
    return "".join(links)


def alternate_links(content: dict, section: str) -> str:
    lines = [
        f'  <link rel="alternate" hreflang="{escape(locale)}" href="{escape(content["site"]["canonical_origin"] + route(locale, section))}">'
        for locale in content["locales"]
    ]
    default_path = "/attenuator/" if section == "home" else route("en", section)
    lines.append(
        f'  <link rel="alternate" hreflang="x-default" href="{escape(content["site"]["canonical_origin"] + default_path)}">'
    )
    return "\n".join(lines)


def page_shell(
    content: dict,
    locale: str,
    section: str,
    title: str,
    description: str,
    main: str,
    *,
    canonical_path: str | None = None,
) -> str:
    localized = content["locales"][locale]
    nav = localized["nav"]
    origin = content["site"]["canonical_origin"]
    canonical_path = canonical_path or route(locale, section)
    nav_links = "".join(
        f'<a href="{escape(route(locale, item))}"' + (' aria-current="page"' if item == section else "") + f'>{escape(nav[item])}</a>'
        for item in ("home", "support", "privacy")
    )
    image_url = f"{origin}/attenuator/assets/screenshots/{localized['screenshot_locale']}/power.png"
    return f"""<!doctype html>
<html lang="{escape(locale)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(description)}">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self'; style-src 'self'; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'self'; form-action 'none'">
  <title>{escape(title)} · Attenuator</title>
  <link rel="canonical" href="{escape(origin + canonical_path)}">
{alternate_links(content, section)}
  <meta property="og:type" content="website">
  <meta property="og:title" content="{escape(title)} · Attenuator">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:url" content="{escape(origin + canonical_path)}">
  <meta property="og:image" content="{escape(image_url)}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="/attenuator/assets/app-icon.png">
  <link rel="stylesheet" href="/attenuator/assets/site.css?v=20260822-2">
</head>
<body>
  <a class="skip-link" href="#main">{escape(nav['skip'])}</a>
  <header class="site-header">
    <div class="app-switcher">
      <a class="brand" href="{escape(route(locale, 'home'))}">
        <img src="/attenuator/assets/app-icon.png" width="44" height="44" alt="">
        <span>Attenuator</span>
      </a>
      <a class="brand" href="/nmrtutor/">
        <img src="/nmrtutor/assets/app-icon.png" width="44" height="44" alt="">
        <span>NMR Tutor</span>
      </a>
    </div>
    <nav class="primary-nav" aria-label="Attenuator">{nav_links}</nav>
  </header>
  <main id="main">{main}</main>
  <footer class="site-footer">
    <p>{escape(localized['footer'])} · <a href="mailto:{escape(content['site']['support_email'])}">{escape(content['site']['support_email'])}</a></p>
    <details class="language-menu">
      <summary>{escape(nav['languages'])}</summary>
      <div class="language-links">{language_links(content, section, locale)}</div>
    </details>
  </footer>
</body>
</html>
"""


def render_landing(content: dict, locale: str, *, global_entry: bool = False) -> str:
    localized = content["locales"][locale]
    home = localized["home"]
    app_store_url = content["site"]["app_store_url"]
    features = "".join(
        f'<article class="feature-card"><h2>{escape(item["title"])}</h2><p>{escape(item["body"])}</p></article>'
        for item in home["features"]
    )
    screenshots = "".join(
        f'<figure class="phone-shot"><img src="/attenuator/assets/screenshots/{escape(localized["screenshot_locale"])}/{escape(item["id"])}.png" '
        f'alt="Attenuator · {escape(item["title"])}" loading="lazy"><figcaption>{escape(item["title"])}</figcaption></figure>'
        for item in home["features"]
    )
    language_panel = ""
    if global_entry:
        language_panel = f"""
    <section class="language-panel" aria-labelledby="language-heading">
      <h2 id="language-heading">{escape(localized['nav']['languages'])}</h2>
      <div class="language-links">{language_links(content, 'home', None)}</div>
    </section>"""
    main = f"""
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">{escape(home['eyebrow'])}</p>
        <h1>{escape(home['heading'])}</h1>
        <p class="lede">{escape(home['summary'])}</p>
        <div class="actions">
          <a class="button primary" href="{escape(app_store_url)}">{escape(home['download_cta'])}</a>
          <a class="button secondary" href="{escape(route(locale, 'support'))}">{escape(home['support_cta'])}</a>
        </div>
        <p class="platforms"><a href="{escape(app_store_url)}">{escape(home['platforms'])}</a></p>
      </div>
      <img class="hero-icon" src="/attenuator/assets/app-icon.png" width="240" height="240" alt="Attenuator">
    </section>
    <section class="features" aria-label="Attenuator">{features}</section>
    <section class="screenshots" aria-label="Attenuator">{screenshots}</section>
{language_panel}
    """
    canonical = "/attenuator/" if global_entry else None
    return page_shell(content, locale, "home", "Attenuator", home["summary"], main, canonical_path=canonical)


def render_support(content: dict, locale: str) -> str:
    localized = content["locales"][locale]
    support = localized["support"]
    cards = "".join(
        f'<article class="support-card"><h2>{escape(card["title"])}</h2><p>{escape(card["body"])}</p></article>'
        for card in support["cards"]
    )
    main = f"""
    <section class="page-intro">
      <p class="eyebrow">Attenuator</p>
      <h1>{escape(support['title'])}</h1>
      <p class="lede">{escape(support['intro'])}</p>
    </section>
    <section class="support-grid">{cards}
      <article class="support-card">
        <h2>{escape(support['email_title'])}</h2>
        <p>{escape(support['email_body'])}</p>
        <p><a class="text-link" href="mailto:{escape(content['site']['support_email'])}">{escape(support['email_cta'])}</a></p>
      </article>
      <article class="support-card">
        <h2>{escape(support['issues_title'])}</h2>
        <p>{escape(support['issues_body'])}</p>
        <p class="warning">{escape(support['issues_warning'])}</p>
        <p><a class="text-link" href="{escape(content['site']['issues_url'])}">{escape(support['issues_cta'])}</a></p>
      </article>
    </section>
    """
    return page_shell(content, locale, "support", support["title"], support["intro"], main)


def render_privacy(content: dict, locale: str, *, compatibility_path: bool = False) -> str:
    localized = content["locales"][locale]
    privacy = localized["privacy"]
    sections = "".join(
        f'<section><h2>{escape(item["title"])}</h2><p>{escape(item["body"])}</p></section>'
        for item in privacy["sections"]
    )
    main = f"""
    <article class="policy">
      <p class="eyebrow">Attenuator</p>
      <h1>{escape(privacy['title'])}</h1>
      <p><strong>{escape(privacy['effective_label'])}:</strong> {escape(content['site']['effective_date'])}</p>
      <p class="lede">{escape(privacy['intro'])}</p>
      {sections}
      <p class="translation-notice">{escape(privacy['translation_notice'])}</p>
    </article>
    """
    canonical = route("en", "privacy") if compatibility_path else None
    return page_shell(content, locale, "privacy", privacy["title"], privacy["intro"], main, canonical_path=canonical)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def generate(output: Path, content: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_text(output / "index.html", render_landing(content, "en", global_entry=True))
    write_text(output / "privacy.html", render_privacy(content, "en", compatibility_path=True))
    sitemap_paths = ["/attenuator/", "/attenuator/privacy.html"]
    for locale in EXPECTED_LOCALES:
        pages = {
            "index.html": render_landing(content, locale),
            "support/index.html": render_support(content, locale),
            "privacy/index.html": render_privacy(content, locale),
        }
        for relative, source in pages.items():
            write_text(output / locale / relative, source)
        sitemap_paths.extend(route(locale, section) for section in ("home", "support", "privacy"))

    origin = content["site"]["canonical_origin"]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "\n".join(f"  <url><loc>{escape(origin + path)}</loc></url>" for path in sitemap_paths)
    sitemap += "\n</urlset>"
    write_text(output / "sitemap.xml", sitemap)
    manifest = {
        "generator": ".github/scripts/generate_attenuator_site.py",
        "locales": list(EXPECTED_LOCALES),
        "features": list(EXPECTED_FEATURES),
        "effective_date": content["site"]["effective_date"],
    }
    write_text(output / "generated-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        content = load_content()
        if args.check:
            print(f"Validated {len(EXPECTED_LOCALES)} locales and {len(EXPECTED_FEATURES)} Attenuator features.")
            return 0
        generate(args.output.resolve(), content)
        print(f"Generated Attenuator site at {args.output.resolve()}")
        return 0
    except (GenerationError, json.JSONDecodeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
