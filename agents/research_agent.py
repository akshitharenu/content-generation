from __future__ import annotations

import json
import logging
import os
import textwrap
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup

import anthropic

from config import MAX_TOKENS, MODEL
from models import ResearchInput
from utils import RESEARCH_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google News RSS — searches any query, always returns recent articles
# ---------------------------------------------------------------------------
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# Category-specific search terms added to the topic query for better results
CATEGORY_SEARCH_TERMS: dict[str, str] = {
    "Renewable Energy":                      "green steel renewable energy wind solar",
    "Hydrogen Production & Technology":      "hydrogen steel H2 DRI electrolyser",
    "Green Iron & Low-Carbon Feedstocks":    "green iron DRI direct reduction low carbon",
    "Circular Economy (Scrap)":              "steel scrap recycling electric arc furnace",
    "CCS & CCUS":                            "steel carbon capture CCS CCUS",
    "Steel Demand, Procurement & End Markets": "steel demand procurement automotive construction",
    "Steel Prices & Green Premiums":         "steel price green premium low carbon",
    "Raw Material Prices":                   "iron ore coking coal steel raw material price",
    "Clean Energy Logistics & Storage":      "green hydrogen storage clean energy logistics",
    "Project Finance & Investment":          "green steel investment financing fund",
    "Trade, Tariffs & Regulations":          "steel trade tariff regulation carbon border",
    "Climate Policy & Environment":          "steel decarbonization climate policy net zero",
    "Corporate Offtake":                     "green steel offtake agreement corporate",
    "Partnerships & M&A":                    "steel merger acquisition partnership joint venture",
    "Green Steel Projects & Plant Development": "green steel plant project development construction",
}

FALLBACK_SEARCH_TERMS = "green steel hydrogen decarbonization"

# Category RSS feeds as secondary/backup source
CATEGORY_FEEDS: dict[str, list[str]] = {
    "Renewable Energy": [
        "https://cleantechnica.com/feed/",
        "https://www.renewableenergyworld.com/feed/",
    ],
    "Hydrogen Production & Technology": [
        "https://www.hydrogeninsight.com/rss",
        "https://www.fuelcellsworks.com/feed/",
    ],
    "Green Iron & Low-Carbon Feedstocks": [
        "https://www.mining.com/feed/",
    ],
    "Circular Economy (Scrap)": [
        "https://www.recyclingtoday.com/rss/all-news.rss",
    ],
    "CCS & CCUS": [
        "https://www.globalccsinstitute.com/feed/",
        "https://carbonbrief.org/feed",
    ],
    "Steel Demand, Procurement & End Markets": [
        "https://www.worldsteel.org/rss.xml",
    ],
    "Steel Prices & Green Premiums": [
        "https://www.worldsteel.org/rss.xml",
    ],
    "Raw Material Prices": [
        "https://www.mining.com/feed/",
    ],
    "Clean Energy Logistics & Storage": [
        "https://cleantechnica.com/feed/",
    ],
    "Project Finance & Investment": [
        "https://www.hydrogeninsight.com/rss",
    ],
    "Trade, Tariffs & Regulations": [
        "https://carbonbrief.org/feed",
    ],
    "Climate Policy & Environment": [
        "https://carbonbrief.org/feed",
        "https://steelwatch.org/feed/",
    ],
    "Corporate Offtake": [
        "https://www.worldsteel.org/rss.xml",
    ],
    "Partnerships & M&A": [
        "https://www.hydrogeninsight.com/rss",
        "https://www.mining.com/feed/",
    ],
    "Green Steel Projects & Plant Development": [
        "https://steelwatch.org/feed/",
        "https://www.hydrogeninsight.com/rss",
    ],
}

RELEVANCE_KEYWORDS = [
    "steel", "hydrogen", "green", "iron", "decarboni", "carbon",
    "renewable", "scrap", "electric arc", "DRI", "blast furnace",
    "CCUS", "CCS", "offtake", "net zero", "emission", "energy",
    "investment", "plant", "project", "fund", "tariff", "trade",
]

CUTOFF_DAYS = 90  # ignore articles older than this


def _parse_date(entry: dict) -> Optional[datetime]:
    """Try to parse the published date from a feed entry."""
    raw = entry.get("published", "") or entry.get("updated", "")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        # Try ISO format
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _is_recent(entry: dict, days: int = CUTOFF_DAYS) -> bool:
    """Return True if the entry was published within `days` days."""
    pub = _parse_date(entry)
    if pub is None:
        return True  # unknown date — keep it
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return pub >= cutoff


def _clean_html(raw: str) -> str:
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ").strip()


def _fetch_feed(url: str, max_items: int = 15) -> list[dict]:
    """Fetch a single RSS/Atom feed and return recent entries as dicts."""
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        entries = []
        for entry in feed.entries[:max_items]:
            pub = _parse_date(entry)
            item = {
                "title":     entry.get("title", "").strip(),
                "summary":   _clean_html(entry.get("summary", entry.get("description", "")))[:600],
                "link":      entry.get("link", ""),
                "published": pub.strftime("%B %d, %Y") if pub else entry.get("published", ""),
                "pub_dt":    pub,
            }
            if item["title"]:
                entries.append(item)
        return entries
    except Exception as exc:
        logger.debug("Feed fetch failed (%s): %s", url, exc)
        return []


def _fetch_google_news(query: str, max_items: int = 15) -> list[dict]:
    """Query Google News RSS for the given search string."""
    encoded = urllib.parse.quote(query)
    url = GOOGLE_NEWS_RSS.format(query=encoded)
    entries = _fetch_feed(url, max_items=max_items)
    logger.info("[ResearchAgent] Google News '%s' → %d entries", query[:60], len(entries))
    return entries


def _score_entry(entry: dict, topic_words: set[str]) -> int:
    text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    relevance = sum(1 for kw in RELEVANCE_KEYWORDS if kw in text)
    topic_bonus = sum(2 for w in topic_words if w in text)
    # Recency bonus: articles from last 7 days get +5
    pub = entry.get("pub_dt")
    recency = 5 if pub and pub >= datetime.now(timezone.utc) - timedelta(days=7) else 0
    return relevance + topic_bonus + recency


def gather_live_news(category: str, topic: str, max_articles: int = 15) -> list[dict]:
    """
    1. Search Google News RSS with topic + category keywords (always fresh)
    2. Supplement with category-specific RSS feeds
    3. Filter to last CUTOFF_DAYS days, rank by relevance + recency
    """
    topic_words = {w.lower() for w in topic.split() if len(w) > 3}
    cat_terms = CATEGORY_SEARCH_TERMS.get(category, FALLBACK_SEARCH_TERMS)

    # Build two Google News queries: one precise, one broader
    precise_query = f"{topic} green steel"
    broad_query   = f"{cat_terms} green steel 2025"

    all_entries: list[dict] = []

    # Primary: Google News (topic-specific, always current)
    all_entries.extend(_fetch_google_news(precise_query, max_items=15))
    all_entries.extend(_fetch_google_news(broad_query,   max_items=10))

    # Secondary: category RSS feeds
    for feed_url in CATEGORY_FEEDS.get(category, []):
        all_entries.extend(_fetch_feed(feed_url, max_items=8))

    # Filter to recent articles only
    all_entries = [e for e in all_entries if _is_recent(e, days=CUTOFF_DAYS)]

    # Deduplicate by title
    seen: set[str] = set()
    unique: list[dict] = []
    for e in all_entries:
        if e["title"] and e["title"] not in seen:
            seen.add(e["title"])
            unique.append(e)

    # Rank by relevance + recency
    unique.sort(key=lambda e: _score_entry(e, topic_words), reverse=True)

    result = unique[:max_articles]
    logger.info(
        "[ResearchAgent] %d unique recent articles collected for '%s'",
        len(result), category
    )
    return result


def _format_news_context(entries: list[dict]) -> str:
    lines = []
    for i, e in enumerate(entries, 1):
        lines.append(
            f"{i}. HEADLINE: {e['title']}\n"
            f"   DATE:     {e['published']}\n"
            f"   SUMMARY:  {e['summary']}\n"
            f"   SOURCE:   {e['link']}"
        )
    return "\n\n".join(lines)


class ResearchAgent:
    """
    Agent 1 — Research & intelligence gathering.

    Searches Google News RSS for the topic (always fresh, last 90 days),
    supplements with category RSS feeds, then passes real article context
    to Claude to build a structured research brief.
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
        logger.info("[ResearchAgent] Starting research: %s", topic)

        cat = category or "Green Steel Projects & Plant Development"
        live_entries = gather_live_news(cat, topic)
        news_context = _format_news_context(live_entries)

        if not live_entries:
            logger.warning("[ResearchAgent] No live articles found — Claude will use training knowledge.")
            news_context = "No live articles retrieved. Use your most recent knowledge of the green steel industry."

        today = datetime.now(timezone.utc).strftime("%B %d, %Y")

        user_message = textwrap.dedent(f"""
            Today's date: {today}
            Topic: {topic}
            Category: {cat}

            LIVE NEWS (fetched from Google News and industry RSS feeds — articles from last 90 days):
            {news_context}

            Instructions:
            - Use the live news above as your PRIMARY factual source.
            - Extract real company names, figures, dates, and quotes from the articles above.
            - Where the articles above don't provide enough detail, supplement with your knowledge
              of the green steel industry — but DO NOT invent facts not supported by the sources.
            - Prioritise the most recently dated articles when facts conflict.
            - Return ONLY a valid JSON object as specified.
        """).strip()

        message = await self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=RESEARCH_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = message.content[0].text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            raw_text = "\n".join(l for l in lines if not l.startswith("```")).strip()

        data = json.loads(raw_text)
        data["topic"] = topic

        # Attach live source URLs
        live_urls = [e["link"] for e in live_entries if e.get("link")][:6]
        existing  = data.get("sources", [])
        data["sources"] = list(dict.fromkeys(existing + live_urls))[:8]

        research = ResearchInput(**data)
        logger.info(
            "[ResearchAgent] Brief ready — %d facts, %d sources, %d key players.",
            len(research.facts), len(research.sources), len(research.key_players),
        )
        return research
