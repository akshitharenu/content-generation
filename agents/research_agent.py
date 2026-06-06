from __future__ import annotations

import json
import logging
import os
import textwrap
from datetime import datetime, timezone
from typing import List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup

import anthropic

from config import MAX_TOKENS, MODEL
from models import ResearchInput
from utils import RESEARCH_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RSS feeds mapped per category — all free, no API key required
# ---------------------------------------------------------------------------
CATEGORY_FEEDS: dict[str, list[str]] = {
    "Renewable Energy": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.renewableenergyworld.com/feed/",
        "https://cleantechnica.com/feed/",
        "https://rss.app/feeds/tXqKMFk8EAqnqKRz.xml",  # PV-Tech
    ],
    "Hydrogen Production & Technology": [
        "https://www.hydrogeninsight.com/rss",
        "https://www.fuelcellsworks.com/feed/",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://cleantechnica.com/feed/",
    ],
    "Green Iron & Low-Carbon Feedstocks": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.mining.com/feed/",
        "https://www.metalbulletin.com/rss/all-news.rss",
        "https://www.kallanish.com/rss.xml",
    ],
    "Circular Economy (Scrap)": [
        "https://www.recyclingtoday.com/rss/all-news.rss",
        "https://www.scrap.org/rss",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.metalbulletin.com/rss/all-news.rss",
    ],
    "CCS & CCUS": [
        "https://www.globalccsinstitute.com/feed/",
        "https://feeds.reuters.com/reuters/environmentNews",
        "https://cleantechnica.com/feed/",
        "https://carbonbrief.org/feed",
    ],
    "Steel Demand, Procurement & End Markets": [
        "https://www.worldsteel.org/rss.xml",
        "https://www.metalbulletin.com/rss/all-news.rss",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.kallanish.com/rss.xml",
    ],
    "Steel Prices & Green Premiums": [
        "https://www.metalbulletin.com/rss/all-news.rss",
        "https://www.kallanish.com/rss.xml",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.worldsteel.org/rss.xml",
    ],
    "Raw Material Prices": [
        "https://www.mining.com/feed/",
        "https://www.metalbulletin.com/rss/all-news.rss",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.argusmedia.com/rss/latest-news",
    ],
    "Clean Energy Logistics & Storage": [
        "https://www.energystoragenews.com/rss",
        "https://cleantechnica.com/feed/",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.renewableenergyworld.com/feed/",
    ],
    "Project Finance & Investment": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.bloomberg.com/feeds/bbiz/sitemap_index.xml",
        "https://www.globalccsinstitute.com/feed/",
        "https://www.hydrogeninsight.com/rss",
    ],
    "Trade, Tariffs & Regulations": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.reuters.com/Reuters/worldNews",
        "https://www.metalbulletin.com/rss/all-news.rss",
        "https://carbonbrief.org/feed",
    ],
    "Climate Policy & Environment": [
        "https://carbonbrief.org/feed",
        "https://feeds.reuters.com/reuters/environmentNews",
        "https://cleantechnica.com/feed/",
        "https://steelwatch.org/feed/",
    ],
    "Corporate Offtake": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.worldsteel.org/rss.xml",
        "https://www.metalbulletin.com/rss/all-news.rss",
        "https://cleantechnica.com/feed/",
    ],
    "Partnerships & M&A": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.metalbulletin.com/rss/all-news.rss",
        "https://www.hydrogeninsight.com/rss",
        "https://www.mining.com/feed/",
    ],
    "Green Steel Projects & Plant Development": [
        "https://www.worldsteel.org/rss.xml",
        "https://www.hydrogeninsight.com/rss",
        "https://www.metalbulletin.com/rss/all-news.rss",
        "https://steelwatch.org/feed/",
    ],
}

# Fallback feeds used when category is unknown or feeds all fail
FALLBACK_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://cleantechnica.com/feed/",
    "https://www.mining.com/feed/",
]

# Keywords to prioritise entries related to steel / green energy / hydrogen
RELEVANCE_KEYWORDS = [
    "steel", "hydrogen", "green", "iron", "decarboni", "carbon",
    "renewable", "scrap", "electric arc", "DRI", "blast furnace",
    "CCUS", "CCS", "offtake", "net zero", "emission", "energy",
    "investment", "plant", "project", "fund", "tariff", "trade",
]


def _fetch_feed_entries(url: str, max_items: int = 8) -> list[dict]:
    """Pull entries from a single RSS/Atom feed. Returns plain dicts."""
    try:
        # feedparser handles redirects and various feed formats
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        entries = []
        for entry in feed.entries[:max_items]:
            entries.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", entry.get("description", "")),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            })
        return entries
    except Exception as exc:
        logger.debug("Feed fetch failed for %s: %s", url, exc)
        return []


def _score_entry(entry: dict) -> int:
    """Higher = more relevant to green steel."""
    text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    return sum(1 for kw in RELEVANCE_KEYWORDS if kw in text)


def _clean_html(raw: str) -> str:
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ").strip()


def gather_live_news(category: str, topic: str, max_articles: int = 12) -> list[dict]:
    """
    Fetch real RSS entries for the given category and topic.
    Returns up to max_articles entries sorted by relevance score.
    """
    feeds = CATEGORY_FEEDS.get(category, FALLBACK_FEEDS)
    all_entries: list[dict] = []

    for feed_url in feeds:
        entries = _fetch_feed_entries(feed_url, max_items=10)
        all_entries.extend(entries)

    # Also try fallbacks if we got very little
    if len(all_entries) < 5:
        for feed_url in FALLBACK_FEEDS:
            all_entries.extend(_fetch_feed_entries(feed_url, max_items=5))

    # Clean HTML from summaries
    for e in all_entries:
        e["summary"] = _clean_html(e["summary"])[:500]

    # Deduplicate by title
    seen: set[str] = set()
    unique: list[dict] = []
    for e in all_entries:
        if e["title"] and e["title"] not in seen:
            seen.add(e["title"])
            unique.append(e)

    # Sort by relevance to green steel keywords
    unique.sort(key=_score_entry, reverse=True)

    # Also boost entries that mention words from the topic itself
    topic_words = {w.lower() for w in topic.split() if len(w) > 3}
    def combined_score(e: dict) -> int:
        base = _score_entry(e)
        text = (e["title"] + " " + e["summary"]).lower()
        bonus = sum(1 for w in topic_words if w in text)
        return base + bonus * 2

    unique.sort(key=combined_score, reverse=True)
    return unique[:max_articles]


def _format_news_context(entries: list[dict]) -> str:
    lines = []
    for i, e in enumerate(entries, 1):
        lines.append(
            f"{i}. HEADLINE: {e['title']}\n"
            f"   SUMMARY: {e['summary']}\n"
            f"   SOURCE: {e['link']}\n"
            f"   DATE: {e['published']}"
        )
    return "\n\n".join(lines)


class ResearchAgent:
    """
    Agent 1 — Research & intelligence gathering.

    Fetches live RSS news for the category, then uses Claude to synthesise
    a structured research brief grounded in the real fetched content.
    """

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file or set it as an environment variable."
            )
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def run(self, topic: str, category: Optional[str] = None) -> ResearchInput:
        logger.info("[ResearchAgent] Gathering live news for: %s", topic)

        # Fetch real articles from the web
        cat = category or "Green Steel Projects & Plant Development"
        live_entries = gather_live_news(cat, topic)
        news_context = _format_news_context(live_entries)

        if live_entries:
            logger.info("[ResearchAgent] Fetched %d live articles from RSS feeds.", len(live_entries))
        else:
            logger.warning("[ResearchAgent] No live articles fetched — Claude will reason from topic only.")
            news_context = "No live feed data available. Use your knowledge of the green steel industry."

        today = datetime.now(timezone.utc).strftime("%B %d, %Y")

        user_message = textwrap.dedent(f"""
            Today's date: {today}
            Topic to cover: {topic}
            Category: {cat}

            LIVE NEWS CONTEXT (fetched from industry RSS feeds right now):
            {news_context}

            Using the live news above as your factual foundation, generate a research brief
            for a news article about the topic. Extract and synthesise real facts, figures,
            company names, and quotes from the context above. If specific data is missing,
            supplement with your knowledge of the green steel industry — but clearly ground
            the brief in the real news provided.

            Return ONLY a valid JSON object as specified.
        """).strip()

        message = await self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=RESEARCH_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = message.content[0].text.strip()

        # Strip markdown code fences
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            raw_text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        data = json.loads(raw_text)
        data["topic"] = topic

        # Attach live source URLs as additional sources
        live_urls = [e["link"] for e in live_entries if e.get("link")][:5]
        existing = data.get("sources", [])
        data["sources"] = list(dict.fromkeys(existing + live_urls))[:8]

        research = ResearchInput(**data)
        logger.info(
            "[ResearchAgent] Brief ready — %d facts, %d sources, %d key players.",
            len(research.facts),
            len(research.sources),
            len(research.key_players),
        )
        return research
