import os
from __future__ import annotations

import logging

import anthropic

from config import MAX_TOKENS, MODEL
from utils import HUMANIZER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class HumanizerAgent:
    """Agent 4 — Anti-AI-detection pass.

    Rewrites the drafted article to eliminate AI-writing patterns while
    preserving every factual detail, name, and number.
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))

    async def run(self, article_text: str) -> str:
        """Return the humanized article text.

        *article_text* should be the full article including headline and dateline.
        """
        logger.info("[HumanizerAgent] Humanizing article (%d chars).", len(article_text))

        user_message = (
            "Rewrite the following news article to eliminate AI-writing patterns. "
            "Follow all rules in your system prompt exactly.\n\n"
            "--- ARTICLE START ---\n"
            + article_text
            + "\n--- ARTICLE END ---\n\n"
            "Return only the rewritten article."
        )

        message = await self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=HUMANIZER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        rewritten = message.content[0].text.strip()
        logger.info(
            "[HumanizerAgent] Rewrite complete. Output length: %d chars.", len(rewritten)
        )
        return rewritten
