from __future__ import annotations

import logging
import re

import anthropic

from config import API_KEY, MAX_TOKENS, MODEL
from models import ResearchInput
from utils import get_writer_system_prompt

logger = logging.getLogger(__name__)

# Regex to extract the [Word count: NNN] line the model appends
_WORD_COUNT_RE = re.compile(r"\[Word count:\s*(\d+)\]", re.IGNORECASE)


class WriterAgent:
    """Agent 3 — Article drafting.

    Combines ResearchInput and category assignment to produce a full
    500–700 word news article in inverted-pyramid format.
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=API_KEY)

    async def run(self, research: ResearchInput, category: str) -> tuple[str, str, str, int]:
        """Return (headline, dateline, body_text, word_count).

        *body_text* excludes the headline and dateline lines so callers can
        store them separately in the Article model.
        """
        logger.info(
            "[WriterAgent] Drafting article for topic='%s' category='%s'",
            research.topic,
            category,
        )

        facts_block = "\n".join(f"- {f}" for f in research.facts)
        sources_block = "\n".join(f"- {s}" for s in research.sources)
        players_block = ", ".join(research.key_players)

        user_message = (
            f"Write a news article for the following research brief.\n\n"
            f"Category: {category}\n"
            f"Topic: {research.topic}\n"
            f"Editorial angle: {research.suggested_angle}\n\n"
            f"Key players: {players_block}\n\n"
            f"Research facts (must all be woven into the article):\n{facts_block}\n\n"
            f"Sources (cite at least 2 in the body):\n{sources_block}\n\n"
            "Write the full article now. Remember: headline on line 1, dateline on line 2, "
            "then body paragraphs, closing quote, and [Word count: NNN] on the final line."
        )

        message = await self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=get_writer_system_prompt(category),
            messages=[{"role": "user", "content": user_message}],
        )

        full_text = message.content[0].text.strip()

        # Split into lines and extract structured parts
        lines = full_text.splitlines()
        non_empty = [line for line in lines if line.strip()]

        headline = non_empty[0].strip() if non_empty else research.topic
        # Remove any "Headline:" prefix that might slip through
        headline = re.sub(r"^headline\s*:\s*", "", headline, flags=re.IGNORECASE).strip()

        dateline = non_empty[1].strip() if len(non_empty) > 1 else ""
        # If second line doesn't look like a dateline, generate a placeholder
        if not re.search(r"\d{4}", dateline):
            dateline = ""

        # Extract word count from model's self-reported line
        wc_match = _WORD_COUNT_RE.search(full_text)
        reported_word_count = int(wc_match.group(1)) if wc_match else 0

        # Build body: everything after headline + dateline, excluding the word-count line
        body_start = 2 if dateline else 1
        body_lines = []
        for line in lines[body_start:]:
            if _WORD_COUNT_RE.search(line):
                continue
            body_lines.append(line)

        body_text = "\n".join(body_lines).strip()

        # Compute actual word count from body + headline + dateline if model didn't report
        if reported_word_count == 0:
            combined = f"{headline}\n{dateline}\n{body_text}"
            reported_word_count = len(combined.split())

        logger.info(
            "[WriterAgent] Article drafted. Headline='%s' word_count=%d",
            headline,
            reported_word_count,
        )
        return headline, dateline, body_text, reported_word_count
