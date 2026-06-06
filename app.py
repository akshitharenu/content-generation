"""Streamlit web app for the Green Steel News Generator pipeline."""
from __future__ import annotations

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()  # loads ANTHROPIC_API_KEY from .env if present

import streamlit as st

# ---------------------------------------------------------------------------
# Page config — must be the first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Green Steel News Generator",
    page_icon="🏭",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Ensure project root is importable when launched from a different cwd
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import CATEGORIES, QUALITY_THRESHOLD  # noqa: E402
from main import run_pipeline  # noqa: E402

_SAMPLE_TOPICS_PATH = os.path.join(_PROJECT_ROOT, "sample_topics.json")


# ---------------------------------------------------------------------------
# Helper: load sample topics from JSON
# ---------------------------------------------------------------------------
def _load_sample_topics() -> list[dict]:
    if not os.path.exists(_SAMPLE_TOPICS_PATH):
        return []
    with open(_SAMPLE_TOPICS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    topics = data.get("topics", [])
    result = []
    for t in topics:
        if isinstance(t, str):
            result.append({"category": "", "topic": t})
        else:
            result.append({"category": t.get("category", ""), "topic": t.get("topic", str(t))})
    return result


# ---------------------------------------------------------------------------
# Helper: build markdown string for download
# ---------------------------------------------------------------------------
def _build_article_markdown(article) -> str:
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
        f'created_at: "{article.created_at}"\n'
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
        body_section += f"\n\n---\n\n*Editorial note: {qs.feedback}*\n"

    return frontmatter + body_section


# ---------------------------------------------------------------------------
# Helper: build JSON bytes for download
# ---------------------------------------------------------------------------
def _build_article_json(article) -> str:
    return json.dumps(article.model_dump(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Green Steel News Generator")
    st.caption("AI-Powered Industry Content Workflow")
    st.divider()

    # API key input
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if "api_key" not in st.session_state:
        st.session_state["api_key"] = env_key

    sidebar_key = st.text_input(
        "ANTHROPIC_API_KEY",
        value=st.session_state["api_key"],
        type="password",
        placeholder="sk-ant-...",
        help="Paste your Anthropic API key here if it is not set as an environment variable.",
    )
    if sidebar_key:
        st.session_state["api_key"] = sidebar_key

    st.divider()

    # Category filter
    category_options = ["Auto-detect"] + CATEGORIES
    selected_category = st.selectbox(
        "Category filter",
        options=category_options,
        index=0,
        help="Force the pipeline to assign a specific category, or let the AI decide.",
    )

    # Sample topics
    sample_topics = _load_sample_topics()
    sample_labels = ["— select a sample topic —"] + [t["topic"] for t in sample_topics]
    selected_sample = st.selectbox(
        "Load a sample topic",
        options=sample_labels,
        index=0,
    )

    st.divider()

    # How it works expander
    with st.expander("How it works"):
        st.markdown(
            """
1. **ResearchAgent** — gathers facts, sources and key players for the topic
2. **CategoryAgent** — classifies the article into one of 15 industry categories
3. **WriterAgent** — drafts a structured news article (headline, dateline, body)
4. **HumanizerAgent** — rewrites the draft for a natural, journalist tone
5. **QualityAgent** — scores the article on 5 dimensions and applies a quality gate
6. **PublisherAgent** — serialises the final article to `.json` and `.md` files
"""
        )

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.header("Generate a Green Steel News Article")

# Pre-fill topic area from sample selection
prefill_topic = ""
if selected_sample != "— select a sample topic —":
    prefill_topic = selected_sample

topic_input = st.text_area(
    "Enter news topic or story angle",
    value=prefill_topic,
    height=100,
    placeholder="e.g. ArcelorMittal signs hydrogen offtake deal with Ørsted for its Dunkirk plant",
)

generate_clicked = st.button("Generate Article", type="primary", use_container_width=False)

# ---------------------------------------------------------------------------
# Generation logic
# ---------------------------------------------------------------------------
if generate_clicked:
    api_key = st.session_state.get("api_key", "").strip()

    if not api_key:
        st.warning("Please enter your Anthropic API key in the sidebar.")
    elif not topic_input.strip():
        st.warning("Please enter a topic before generating.")
    else:
        # Inject API key into environment so agents pick it up
        os.environ["ANTHROPIC_API_KEY"] = api_key

        category_override = None if selected_category == "Auto-detect" else selected_category

        try:
            with st.status("Running pipeline…", expanded=True) as status:
                st.write("🔍 Researching topic...")

                # We need to run the async pipeline synchronously from Streamlit.
                # Streamlit runs in its own thread; asyncio.run() creates a fresh
                # event loop for each call, avoiding conflicts.
                async def _pipeline_with_updates(topic: str, cat_override):
                    """Thin wrapper — status updates must happen in the sync thread,
                    so we just call run_pipeline directly."""
                    return await run_pipeline(topic, category_override=cat_override)

                # Step placeholders — update as pipeline progresses by hooking into
                # a patched run_pipeline that yields progress.  Since the existing
                # agents don't emit callbacks, we show progress messages sequentially
                # via intermediate st.write calls that are emitted before asyncio.run.
                st.write("🏷️ Classifying category...")
                st.write("✍️ Drafting article...")
                st.write("✨ Humanizing content...")
                st.write("✅ Quality check...")
                st.write("📄 Finalising output...")

                article = asyncio.run(
                    _pipeline_with_updates(topic_input.strip(), category_override)
                )

                status.update(label="Pipeline complete!", state="complete", expanded=False)

            st.session_state["last_article"] = article

        except Exception as exc:
            st.error(f"Pipeline error: {exc}")

# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------
if "last_article" in st.session_state:
    article = st.session_state["last_article"]
    qs = article.quality_score

    # Quality gate warning (show even if article is displayed)
    if qs and not qs.passed:
        feedback_msg = qs.feedback or "No detailed feedback provided."
        st.warning(
            f"Quality gate did not pass (score {qs.overall:.2f} / {QUALITY_THRESHOLD:.1f}). "
            f"Feedback: {feedback_msg}"
        )

    tab_article, tab_meta = st.tabs(["Article", "Metadata"])

    # --- Article tab ---
    with tab_article:
        article_md = f"# {article.headline}\n\n**{article.dateline}**\n\n---\n\n{article.body}"
        st.markdown(article_md)

        st.divider()

        # Download buttons side by side
        col_dl_md, col_dl_json, _ = st.columns([1, 1, 4])
        with col_dl_md:
            st.download_button(
                label="Download .md",
                data=_build_article_markdown(article),
                file_name=f"{article.slug}.md",
                mime="text/markdown",
            )
        with col_dl_json:
            st.download_button(
                label="Download .json",
                data=_build_article_json(article),
                file_name=f"{article.slug}.json",
                mime="application/json",
            )

    # --- Metadata tab ---
    with tab_meta:
        # Metrics row
        pass_label = "PASS" if (qs and qs.passed) else "FAIL"
        pass_delta_color = "normal" if (qs and qs.passed) else "inverse"

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Category", article.category)
        m2.metric("Word Count", article.word_count)
        m3.metric("Quality Score", f"{qs.overall:.2f}" if qs else "N/A")
        m4.metric("Status", pass_label)

        st.divider()

        # Quality breakdown
        if qs:
            with st.expander("Quality Breakdown", expanded=True):
                breakdown = {
                    "Dimension": [
                        "Newsworthiness",
                        "Specificity",
                        "Readability",
                        "Structure",
                        "Category Fit",
                        "**Overall**",
                    ],
                    "Score": [
                        qs.newsworthiness,
                        qs.specificity,
                        qs.readability,
                        qs.structure,
                        qs.category_fit,
                        qs.overall,
                    ],
                }
                st.table(breakdown)

        # Sources & Key Players
        with st.expander("Sources & Key Players"):
            if article.sources:
                st.markdown("**Sources**")
                for src in article.sources:
                    st.markdown(f"- {src}")
            if article.key_players:
                st.markdown("**Key Players**")
                for player in article.key_players:
                    st.markdown(f"- {player}")

        # Research facts — stored on the Article if available
        # The Article model doesn't carry raw facts directly; show topic + category reasoning
        with st.expander("Research Facts"):
            st.markdown(f"**Topic:** {article.topic}")
            st.markdown(f"**Category reasoning:** {article.category_reasoning}")
            st.markdown(
                f"**Category confidence:** {article.category_confidence * 100:.0f}%"
            )
