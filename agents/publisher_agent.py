from __future__ import annotations

import logging
import os

from models import Article
from utils import generate_slug, write_json, write_markdown

logger = logging.getLogger(__name__)

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


class PublisherAgent:
    """Agent 6 — Final formatting & output.

    Writes the completed Article to:
      - output/<slug>.json  (full Article model serialized)
      - output/<slug>.md    (YAML frontmatter + article body)
    """

    def __init__(self, output_dir: str = _OUTPUT_DIR) -> None:
        self._output_dir = output_dir
        os.makedirs(self._output_dir, exist_ok=True)

    async def run(self, article: Article) -> tuple[str, str]:
        """Persist the article and return (json_path, md_path)."""
        slug = generate_slug(article.headline) if not article.slug else article.slug
        article.slug = slug

        json_path = os.path.join(self._output_dir, f"{slug}.json")
        md_path = os.path.join(self._output_dir, f"{slug}.md")

        # Serialize full Article model to JSON
        article_dict = article.model_dump()
        if article_dict.get("quality_score"):
            # Convert QualityScore nested model
            qs = article_dict["quality_score"]
            article_dict["quality_score"] = qs

        write_json(article_dict, json_path)
        logger.info("[PublisherAgent] Written JSON to %s", json_path)

        # Build Markdown with YAML frontmatter
        md_content = self._build_markdown(article)
        write_markdown(md_content, md_path)
        logger.info("[PublisherAgent] Written Markdown to %s", md_path)

        return json_path, md_path

    def _build_markdown(self, article: Article) -> str:
        qs = article.quality_score
        overall = f"{qs.overall:.2f}" if qs else "N/A"
        passed = str(qs.passed) if qs else "N/A"

        sources_yaml = "\n".join(f'  - "{s}"' for s in article.sources)
        players_yaml = "\n".join(f'  - "{p}"' for p in article.key_players)

        frontmatter = (
            "---\n"
            f'title: "{article.headline}"\n'
            f'slug: "{article.slug}"\n'
            f'category: "{article.category}"\n'
            f"category_confidence: {article.category_confidence:.2f}\n"
            f'dateline: "{article.dateline}"\n'
            f"word_count: {article.word_count}\n"
            f"quality_overall: {overall}\n"
            f"quality_passed: {passed}\n"
            f"created_at: \"{article.created_at}\"\n"
            f"sources:\n{sources_yaml}\n"
            f"key_players:\n{players_yaml}\n"
            "---\n\n"
        )

        body_section = (
            f"# {article.headline}\n\n"
            f"**{article.dateline}**\n\n"
            f"{article.body}\n"
        )

        if qs and qs.feedback:
            body_section += (
                "\n\n---\n\n"
                f"*Editorial note: {qs.feedback}*\n"
            )

        return frontmatter + body_section
