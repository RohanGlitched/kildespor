"""Small shared helpers: time, hashing, text normalisation."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

LEGAL_FORMS = {
    "as", "asa", "ans", "da", "sa", "ba", "bbl", "brl", "enk", "nuf", "sti", "ks", "iks", "kf", "sf",
    "fli", "esek", "spa", "pre", "sam", "gfs", "anna", "kirk", "vpfo", "pk", "sæ", "sær", "se",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def stable_id(*parts: Any, prefix: str = "") -> str:
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def fold(text: str) -> str:
    """Lowercase, Norwegian letters to ASCII, strip accents."""
    text = (text or "").lower()
    text = text.replace("æ", "ae").replace("ø", "o").replace("å", "a")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def name_tokens(name: str, drop_forms: bool = True) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", fold(name).replace("&", " og "))
    if drop_forms:
        while tokens and tokens[-1] in LEGAL_FORMS:
            tokens.pop()
    return tokens


def digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def norm_phone(text: str) -> str:
    """Norwegian phone to 8 digits when possible."""
    d = digits(text)
    if d.startswith("0047"):
        d = d[4:]
    elif d.startswith("47") and len(d) == 10:
        d = d[2:]
    return d if len(d) == 8 else ""


def clip(text: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
