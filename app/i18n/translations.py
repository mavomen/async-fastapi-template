"""Translation catalog loading and lookup."""

import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger("app.i18n")

LOCALES_DIR = Path(__file__).resolve().parent / "locales"


def _load_catalog(locale: str) -> dict[str, str]:
    """Load a single JSON translation catalog from disk."""
    path = LOCALES_DIR / f"{locale}.json"
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return {str(key): str(value) for key, value in data.items()}


def _load_catalogs() -> dict[str, dict[str, str]]:
    """Load all catalogs for supported locales, skipping missing files."""
    catalogs: dict[str, dict[str, str]] = {}
    for locale in settings.SUPPORTED_LOCALES:
        try:
            catalogs[locale] = _load_catalog(locale)
        except FileNotFoundError:
            logger.warning("Missing translation catalog for locale %s", locale)
    return catalogs


_catalogs: dict[str, dict[str, str]] = _load_catalogs()


def get_translations(locale: str) -> dict[str, str]:
    """Return the full catalog for a locale, falling back to the default locale."""
    if locale in _catalogs:
        return _catalogs[locale]
    return _catalogs.get(settings.DEFAULT_LOCALE, {})


def translate(key: str, locale: str = "en", **kwargs: str) -> str:
    """Translate a key into the requested locale with optional interpolation.

    Falls back to the default locale when the requested one lacks the key,
    and to the key itself when no translation exists.
    """
    text = get_translations(locale).get(key)
    if text is None:
        text = _catalogs.get(settings.DEFAULT_LOCALE, {}).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text
