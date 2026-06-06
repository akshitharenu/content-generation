#!/usr/bin/env python3
"""Orchestrator for the green steel multi-agent news generation workflow.

Usage examples:
  python main.py --topic "ArcelorMittal signs hydrogen offtake deal with Ørsted"
  python main.py --topic "Iron ore spot prices fall on weak Chinese demand" --category "Raw Material Prices"
  python main.py  # uses the first topic from sample_topics.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

from agents import (
    CategoryAgent,
    HumanizerAgent,
    PublisherAgent,
    QualityAgent,
    ResearchAgent,
    WriterAgent,
)
from models import Article
from utils import generate_slug, get_timestamp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_SAMPLE_TOPICS_PATH = os.path.join(os.path.dirname(__file__), "sample_topics.json")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Green steel multi-agent news generation pipeline."
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="News topic to research and write. If omitted, the first topic from "
             "sample_topics.json is used.",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Override category classification (must match one of the 15 category names).",
    )
    return parser.parse_args()


def _load_default_topic() -> str:
    if not os.path.exists(_SAMPLE_TOPICS_PATH):
        return "H2 Green Steel signs 10-year wind PPA for its Boden plant in northern Sweden"
    with open(_SAMPLE_TOPICS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    topics = data.get("topics", [])
    if not topics:
        return "H2 Green Steel signs 10-year wind PPA for its Boden plant in northern Sweden"
    first = topics[0]
    # Each entry is either a string or {"category": ..., "topic": ...}
    if isinstance(first, str):
        return first
    return first.get("topic", str(first))


async def run_pipeline(topic: str, category_override: str | None = None) -> Article:
    """Execute all 6 agents in sequence and return the final Article."""

    logger.info("=" * 60)
    logger.info("PIPELINE START")
    logger.info("Topic: %s", topic)
    logger.info("=" * 60)

    # --- Agent 1: Research ---
    research_agent = ResearchAgent()
    research = await research_agent.run(topic, category=category_override)

    # --- Agent 2: Category classification ---
    category_agent = CategoryAgent()
    category, confidence, reasoning = await category_agent.run(
        research, override_category=category_override
    )

    # --- Agent 3: Write draft article ---
    writer_agent = WriterAgent()
    headline, dateline, body, word_count = await writer_agent.run(research, category)

    # --- Agent 4: Humanize ---
    humanizer_agent = HumanizerAgent()
    full_draft = f"{headline}\n{dateline}\n\n{body}"
    humanized_text = await humanizer_agent.run(full_draft)

    # Re-parse headline/dateline/body from humanized output
    h_lines = humanized_text.splitlines()
    h_non_empty = [l for l in h_lines if l.strip()]

    h_headline = h_non_empty[0].strip() if h_non_empty else headline
    import re
    h_headline = re.sub(r"^headline\s*:\s*", "", h_headline, flags=re.IGNORECASE).strip()

    h_dateline = h_non_empty[1].strip() if len(h_non_empty) > 1 else dateline
    if not re.search(r"\d{4}", h_dateline):
        h_dateline = dateline  # fall back to writer's dateline

    # Body starts after headline + dateline lines in humanized output
    body_start_idx = 2
    h_body_lines = h_lines[body_start_idx:]
    h_body = "\n".join(h_body_lines).strip()
    h_word_count = len((h_headline + " " + h_dateline + " " + h_body).split())

    # --- Agent 5: Quality scoring ---
    quality_agent = QualityAgent()
    full_humanized = f"{h_headline}\n{h_dateline}\n\n{h_body}"
    quality_score = await quality_agent.run(full_humanized, category)

    if not quality_score.passed:
        logger.warning(
            "Quality gate FAILED (overall=%.2f). Feedback: %s",
            quality_score.overall,
            quality_score.feedback,
        )
    else:
        logger.info("Quality gate PASSED (overall=%.2f).", quality_score.overall)

    # --- Build Article model ---
    slug = generate_slug(h_headline)
    article = Article(
        topic=topic,
        category=category,
        category_confidence=confidence,
        category_reasoning=reasoning,
        headline=h_headline,
        dateline=h_dateline,
        body=h_body,
        word_count=h_word_count,
        sources=research.sources,
        key_players=research.key_players,
        quality_score=quality_score,
        slug=slug,
        created_at=get_timestamp(),
    )

    # --- Agent 6: Publish ---
    publisher_agent = PublisherAgent()
    json_path, md_path = await publisher_agent.run(article)

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("Category   : %s (confidence=%.2f)", article.category, article.category_confidence)
    logger.info("Headline   : %s", article.headline)
    logger.info("Word count : %d", article.word_count)
    logger.info("Quality    : %.2f (%s)", quality_score.overall, "PASS" if quality_score.passed else "FAIL")
    logger.info("JSON output: %s", json_path)
    logger.info("MD output  : %s", md_path)
    logger.info("=" * 60)

    return article


def main() -> None:
    args = _parse_args()
    topic = args.topic or _load_default_topic()
    asyncio.run(run_pipeline(topic, category_override=args.category))


if __name__ == "__main__":
    main()
