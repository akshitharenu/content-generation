from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any


def extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from Claude's response.
    Handles markdown fences, extra text before/after, and trailing commas.
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the outermost { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidate = match.group(0)
        # Remove trailing commas before } or ]
        candidate = re.sub(r",\s*([\}\]])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from Claude response:\n{text[:400]}")


def generate_slug(headline: str) -> str:
    """Convert a headline into a URL-safe slug."""
    slug = headline.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    # Truncate to 80 chars to keep filenames manageable
    return slug[:80]


def get_timestamp() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.utcnow().isoformat()


def write_json(data: Any, path: str) -> None:
    """Serialise *data* to JSON and write to *path*."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def write_markdown(content: str, path: str) -> None:
    """Write *content* string to *path* as UTF-8 markdown."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
