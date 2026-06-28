"""
Claude at ingestion.

Two jobs, both done in a single API call when a key is configured:
  1. Detect the source language and translate to English if needed.
  2. Summarize the problem and the resolution into plain English that any
     stakeholder in any department can read.

The ORIGINAL source text is always kept separately by the caller (store.py),
so the resolving department keeps its own-language record and the KB output is
the shared plain-English layer on top.

Graceful fallback: with no API key (or on any error), we do NOT fabricate a
summary. We pass the raw text through, clearly labelled, and report ai_used =
False. Honest by default — the demo still works offline.

Uses plain HTTPS via `requests` so there's no extra SDK to package.
"""

import json
import requests

API_URL = "https://api.anthropic.com/v1/messages"

PROMPT = """You are normalizing a resolved customer support ticket into a \
shared knowledge base. The text may be in any language.

Return ONLY a JSON object, no preamble, with these keys:
  "source_language": the detected language of the input (e.g. "English", "French"),
  "problem": one or two plain-English sentences describing the customer's problem,
  "resolution": one or two plain-English sentences describing how it was resolved.

Write the problem and resolution in clear English a non-specialist in another \
department could understand. Do not invent details that are not present.

TICKET DESCRIPTION:
{description}

RESOLUTION NOTES:
{resolution}
"""


def summarize(description: str, resolution: str, cfg: dict) -> dict:
    """
    Returns dict: {source_language, problem, resolution, ai_used}.
    Never raises — failure degrades to a labelled passthrough.
    """
    fallback = {
        "source_language": "unknown",
        "problem": description.strip(),
        "resolution": resolution.strip(),
        "ai_used": False,
    }

    api_key = cfg.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return fallback

    body = {
        "model": cfg.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "max_tokens": 400,
        "messages": [{
            "role": "user",
            "content": PROMPT.format(description=description, resolution=resolution),
        }],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        r = requests.post(API_URL, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        text = "".join(
            block.get("text", "")
            for block in r.json().get("content", [])
            if block.get("type") == "text"
        ).strip()
        # Strip accidental code fences before parsing.
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("{"):]
        parsed = json.loads(text[text.find("{"): text.rfind("}") + 1])
        return {
            "source_language": parsed.get("source_language", "unknown"),
            "problem": parsed.get("problem", "").strip() or description.strip(),
            "resolution": parsed.get("resolution", "").strip() or resolution.strip(),
            "ai_used": True,
        }
    except Exception as e:  # noqa: BLE001 — degrade, never block ingestion
        print(f"[ai] summarize failed, using passthrough: {e}")
        return fallback


def classify_department(text: str, cfg: dict):
    """Layer-2 classifier helper: one-word department guess, or None."""
    api_key = cfg.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    body = {
        "model": cfg.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "max_tokens": 20,
        "messages": [{
            "role": "user",
            "content": "Reply with ONE of: IT, Technical Support, Billing, "
                       "Warranty, Legal, Sales. Which department best owns this "
                       f"resolved ticket?\n\n{text}",
        }],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        r = requests.post(API_URL, headers=headers, json=body, timeout=15)
        r.raise_for_status()
        return "".join(
            b.get("text", "") for b in r.json().get("content", [])
            if b.get("type") == "text"
        ).strip()
    except Exception:  # noqa: BLE001
        return None
