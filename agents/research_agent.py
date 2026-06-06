from __future__ import annotations

import json
import logging

import anthropic

from config import API_KEY, MAX_TOKENS, MODEL
from models import ResearchInput
from utils import RESEARCH_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ResearchAgent:
    """Agent 1 — Research & intelligence gathering.

    Given a topic string, uses Claude to produce a structured research brief
    containing facts, sources, a suggested editorial angle, and key players.
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=API_KEY)

    async def run(self, topic: str) -> ResearchInput:
        logger.info("[ResearchAgent] Starting research for topic: %s", topic)

        user_message = (
            f"Generate a detailed research brief for the following green steel news topic:\n\n"
            f'"{topic}"\n\n'
            "Return only the JSON object as specified."
        )

        message = await self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=RESEARCH_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = message.content[0].text.strip()

        # Strip markdown code fences if Claude wraps in them
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            raw_text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        data = json.loads(raw_text)
        # Ensure the topic field matches the original even if Claude rephrased it
        data["topic"] = topic

        research = ResearchInput(**data)
        logger.info(
            "[ResearchAgent] Produced %d facts, %d sources, %d key players.",
            len(research.facts),
            len(research.sources),
            len(research.key_players),
        )
        return research
