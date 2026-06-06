from __future__ import annotations

import json
import logging

import anthropic

from config import API_KEY, CATEGORIES, MAX_TOKENS, MODEL
from models import ResearchInput
from utils import CATEGORY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class CategoryAgent:
    """Agent 2 — Category classification.

    Takes a ResearchInput and returns the best-matching category name,
    a confidence score, and a one-sentence reasoning string.
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=API_KEY)

    async def run(
        self, research: ResearchInput, override_category: str | None = None
    ) -> tuple[str, float, str]:
        """Return (category, confidence, reasoning).

        If *override_category* is supplied and is a valid category name,
        skip the LLM call and return it with confidence 1.0.
        """
        if override_category:
            normalised = override_category.strip()
            if normalised in CATEGORIES:
                logger.info(
                    "[CategoryAgent] Using override category: %s", normalised
                )
                return normalised, 1.0, "Category provided by user override."
            logger.warning(
                "[CategoryAgent] Override category '%s' not in CATEGORIES list; "
                "falling back to classification.",
                normalised,
            )

        logger.info("[CategoryAgent] Classifying topic: %s", research.topic)

        brief_summary = (
            f"Topic: {research.topic}\n\n"
            f"Suggested angle: {research.suggested_angle}\n\n"
            f"Key players: {', '.join(research.key_players)}\n\n"
            "Research facts:\n"
            + "\n".join(f"- {f}" for f in research.facts)
        )

        message = await self._client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=CATEGORY_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Classify this research brief into one of the 15 categories:\n\n"
                        + brief_summary
                        + "\n\nReturn only the JSON object."
                    ),
                }
            ],
        )

        raw_text = message.content[0].text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            raw_text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        data = json.loads(raw_text)
        category: str = data["category"]
        confidence: float = float(data["confidence"])
        reasoning: str = data["reasoning"]

        if category not in CATEGORIES:
            # Find closest match by substring to handle minor wording differences
            for cat in CATEGORIES:
                if cat.lower() in category.lower() or category.lower() in cat.lower():
                    category = cat
                    break
            else:
                category = CATEGORIES[0]
                logger.warning(
                    "[CategoryAgent] Returned category not recognised; defaulting to '%s'.",
                    category,
                )

        logger.info(
            "[CategoryAgent] Category='%s' confidence=%.2f", category, confidence
        )
        return category, confidence, reasoning
