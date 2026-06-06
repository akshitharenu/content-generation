from __future__ import annotations

import json
import logging

import anthropic

from config import API_KEY, MAX_TOKENS, MODEL, QUALITY_THRESHOLD
from models import QualityScore
from utils import QUALITY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class QualityAgent:
    """Agent 5 — Quality gate & scoring.

    Evaluates the article on five dimensions (0–10 each) and returns a
    QualityScore model. If the overall score is below QUALITY_THRESHOLD the
    score is marked as failed and includes actionable feedback.
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=API_KEY)

    async def run(self, article_text: str, category: str) -> QualityScore:
        """Score *article_text* and return a QualityScore."""
        logger.info(
            "[QualityAgent] Scoring article (%d chars) in category '%s'.",
            len(article_text),
            category,
        )

        user_message = (
            f"Score the following news article. Its assigned category is: {category}\n\n"
            "--- ARTICLE START ---\n"
            + article_text
            + "\n--- ARTICLE END ---\n\n"
            "Return only the JSON score object."
        )

        message = await self._client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=QUALITY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = message.content[0].text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            raw_text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        data = json.loads(raw_text)

        score = QualityScore.compute(
            newsworthiness=float(data.get("newsworthiness", 5.0)),
            specificity=float(data.get("specificity", 5.0)),
            readability=float(data.get("readability", 5.0)),
            structure=float(data.get("structure", 5.0)),
            category_fit=float(data.get("category_fit", 5.0)),
            threshold=QUALITY_THRESHOLD,
            feedback=data.get("feedback") or None,
        )

        logger.info(
            "[QualityAgent] Scores — newsworthiness=%.1f specificity=%.1f "
            "readability=%.1f structure=%.1f category_fit=%.1f → overall=%.2f (%s)",
            score.newsworthiness,
            score.specificity,
            score.readability,
            score.structure,
            score.category_fit,
            score.overall,
            "PASS" if score.passed else "FAIL",
        )
        return score
