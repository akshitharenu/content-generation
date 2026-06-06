"""Streamlit web app — Green Steel News Generator."""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import textwrap
from datetime import datetime
from typing import List

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="Green Steel News Generator",
    page_icon="🏭",
    layout="wide",
)

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import CATEGORIES, QUALITY_THRESHOLD  # noqa: E402
from main import run_pipeline  # noqa: E402
from models.article import Article  # noqa: E402

_SAMPLE_TOPICS_PATH = os.path.join(_PROJECT_ROOT, "sample_topics.json")


# ---------------------------------------------------------------------------
# PDF builder — uses fpdf2 (no external binary required)
# ---------------------------------------------------------------------------
def _build_pdf(article: Article) -> bytes:
    """Build a PDF using reportlab — handles all Unicode including EUR, em-dashes etc."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    )
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=22*mm, bottomMargin=22*mm,
    )

    styles = getSampleStyleSheet()
    green = colors.HexColor("#1e6430")
    dark  = colors.HexColor("#111111")
    grey  = colors.HexColor("#555555")
    light = colors.HexColor("#f5f5f5")

    cat_style = ParagraphStyle("cat", fontName="Helvetica-Bold", fontSize=8,
                                textColor=colors.white, backColor=green,
                                spaceAfter=6, spaceBefore=0, leading=14,
                                leftIndent=4, rightIndent=4)
    headline_style = ParagraphStyle("headline", fontName="Helvetica-Bold", fontSize=20,
                                     textColor=dark, spaceAfter=6, leading=24)
    dateline_style = ParagraphStyle("dateline", fontName="Helvetica-Oblique", fontSize=10,
                                     textColor=grey, spaceAfter=4)
    body_style = ParagraphStyle("body", fontName="Helvetica", fontSize=11,
                                 textColor=dark, spaceAfter=8, leading=16)
    label_style = ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=9,
                                  textColor=dark, spaceAfter=2)
    meta_style = ParagraphStyle("meta", fontName="Helvetica", fontSize=9,
                                 textColor=grey, spaceAfter=3)
    source_style = ParagraphStyle("source", fontName="Helvetica", fontSize=8,
                                   textColor=colors.HexColor("#3050b4"), spaceAfter=3)
    footer_style = ParagraphStyle("footer", fontName="Helvetica", fontSize=8,
                                   textColor=grey, alignment=TA_CENTER)

    story = []
    qs = article.quality_score

    # Category banner
    story.append(Paragraph(f"&nbsp;&nbsp;{article.category.upper()}&nbsp;&nbsp;", cat_style))
    story.append(Spacer(1, 4*mm))

    # Headline
    story.append(Paragraph(article.headline, headline_style))

    # Dateline
    story.append(Paragraph(article.dateline, dateline_style))

    # Green rule
    story.append(HRFlowable(width="100%", thickness=1.5, color=green, spaceAfter=6))

    # Body paragraphs
    for para in article.body.split("\n\n"):
        para = para.strip()
        if para:
            # Escape XML special chars for reportlab
            para = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(para, body_style))

    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=4))

    # Metadata table
    story.append(Paragraph("ARTICLE METADATA", label_style))
    score_str = f"{qs.overall:.2f}/10  —  {'PASS' if qs.passed else 'FAIL'}" if qs else "N/A"
    meta_data = [
        ["Category:", article.category],
        ["Confidence:", f"{article.category_confidence*100:.0f}%"],
        ["Word Count:", str(article.word_count)],
        ["Quality Score:", score_str],
        ["Created:", article.created_at[:10]],
    ]
    t = Table(meta_data, colWidths=[40*mm, 120*mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), dark),
        ("TEXTCOLOR", (1,0), (1,-1), grey),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BACKGROUND", (0,0), (-1,-1), light),
    ]))
    story.append(t)

    # Sources
    if article.sources:
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("SOURCES", label_style))
        for src in article.sources[:6]:
            src_escaped = src[:120].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(src_escaped, source_style))

    # Key players
    if article.key_players:
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("KEY PLAYERS", label_style))
        players = "  |  ".join(article.key_players)
        story.append(Paragraph(players, meta_style))

    doc.build(story)
    return buf.getvalue()

# ---------------------------------------------------------------------------
# Markdown / JSON builders
# ---------------------------------------------------------------------------
def _build_md(article: Article) -> str:
    qs = article.quality_score
    sources_yaml = "\n".join(f'  - "{s}"' for s in article.sources)
    players_yaml = "\n".join(f'  - "{p}"' for p in article.key_players)
    fm = (
        "---\n"
        f'title: "{article.headline}"\n'
        f'category: "{article.category}"\n'
        f'dateline: "{article.dateline}"\n'
        f"word_count: {article.word_count}\n"
        f"quality_score: {qs.overall if qs else 'N/A'}\n"
        f"quality_passed: {qs.passed if qs else 'N/A'}\n"
        f'created_at: "{article.created_at}"\n'
        f"sources:\n{sources_yaml}\n"
        f"key_players:\n{players_yaml}\n"
        "---\n\n"
    )
    return fm + f"# {article.headline}\n\n**{article.dateline}**\n\n---\n\n{article.body}\n"


def _build_json(article: Article) -> str:
    return json.dumps(article.model_dump(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_sample_topics() -> list[dict]:
    if not os.path.exists(_SAMPLE_TOPICS_PATH):
        return []
    with open(_SAMPLE_TOPICS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    result = []
    for t in data.get("topics", []):
        if isinstance(t, str):
            result.append({"category": "", "topic": t})
        else:
            result.append({"category": t.get("category", ""), "topic": t.get("topic", "")})
    return result


def _article_card(article: Article, index: int):
    """Render one article result card with all download buttons."""
    qs = article.quality_score
    passed = qs.passed if qs else False
    score = f"{qs.overall:.1f}/10" if qs else "N/A"
    badge = "🟢 PASS" if passed else "🔴 FAIL"

    with st.container(border=True):
        col_info, col_score = st.columns([6, 1])
        with col_info:
            st.markdown(f"### {article.headline}")
            st.caption(f"**{article.dateline}**  ·  {article.category}  ·  {article.word_count} words")
        with col_score:
            st.metric("Quality", score, delta=badge, delta_color="off")

        if not passed and qs and qs.feedback:
            st.warning(f"Quality note: {qs.feedback}")

        with st.expander("Read full article"):
            st.markdown(f"**{article.dateline}**\n\n{article.body}")

        # Quality breakdown inside expander
        if qs:
            with st.expander("Quality breakdown"):
                cols = st.columns(5)
                dims = [
                    ("Newsworthiness", qs.newsworthiness),
                    ("Specificity", qs.specificity),
                    ("Readability", qs.readability),
                    ("Structure", qs.structure),
                    ("Category Fit", qs.category_fit),
                ]
                for col, (label, val) in zip(cols, dims):
                    col.metric(label, f"{val:.1f}")

        # Download row
        slug = article.slug or f"article_{index}"
        c1, c2, c3, _ = st.columns([1, 1, 1, 4])

        with c1:
            st.download_button(
                "📄 PDF",
                data=_build_pdf(article),
                file_name=f"{slug}.pdf",
                mime="application/pdf",
                key=f"pdf_{index}",
            )
        with c2:
            st.download_button(
                "📝 Markdown",
                data=_build_md(article),
                file_name=f"{slug}.md",
                mime="text/markdown",
                key=f"md_{index}",
            )
        with c3:
            st.download_button(
                "{ } JSON",
                data=_build_json(article),
                file_name=f"{slug}.json",
                mime="application/json",
                key=f"json_{index}",
            )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Green Steel News Generator")
    st.caption("AI-Powered Industry Content Workflow")
    st.divider()

    st.divider()

    generation_mode = st.radio(
        "Generation mode",
        options=["Single article", "Batch — multiple topics", "Batch — full category sweep"],
        index=0,
        help=(
            "Single: one topic → one article.\n"
            "Batch topics: enter several topics, one per line.\n"
            "Category sweep: auto-generate one article per selected category."
        ),
    )

    st.divider()

    with st.expander("Pipeline — how it works"):
        st.markdown(
            """
1. **ResearchAgent** — fetches live RSS news, extracts facts & sources
2. **CategoryAgent** — classifies into 1 of 15 green steel categories
3. **WriterAgent** — drafts 500–700 word inverted-pyramid article
4. **HumanizerAgent** — removes AI patterns, adds journalist texture
5. **QualityAgent** — scores 5 dimensions, pass/fail gate at 7.0/10
6. **PublisherAgent** — saves `.json` + `.md` to output/
"""
        )


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.header("Green Steel News Generator")

sample_topics = _load_sample_topics()

# ── SINGLE ARTICLE ──────────────────────────────────────────────────────────
if generation_mode == "Single article":
    sample_labels = ["— load a sample topic —"] + [t["topic"] for t in sample_topics]
    col_topic, col_cat = st.columns([3, 1])
    with col_topic:
        selected_sample = st.selectbox("Sample topics", sample_labels)
        prefill = selected_sample if selected_sample != "— load a sample topic —" else ""
        topic_input = st.text_area(
            "Topic / story angle",
            value=prefill,
            height=90,
            placeholder="e.g. SSAB secures €500M green bond for HYBRIT scale-up in Sweden",
        )
    with col_cat:
        cat_options = ["Auto-detect"] + CATEGORIES
        selected_cat = st.selectbox("Category", cat_options)

    if st.button("Generate Article", type="primary"):
        if not topic_input.strip():
            st.warning("Please enter a topic.")
        else:
            cat_override = None if selected_cat == "Auto-detect" else selected_cat
            with st.spinner("Running 6-agent pipeline…"):
                try:
                    article = asyncio.run(run_pipeline(topic_input.strip(), category_override=cat_override))
                    st.session_state.setdefault("articles", [])
                    st.session_state["articles"] = [article] + st.session_state["articles"]
                    st.success("Article generated.")
                except Exception as exc:
                    st.error(f"Pipeline error: {exc}")

# ── BATCH — MULTIPLE TOPICS ─────────────────────────────────────────────────
elif generation_mode == "Batch — multiple topics":
    st.markdown("Enter one topic per line. Each will generate a separate article.")
    default_batch = "\n".join(t["topic"] for t in sample_topics[:5])
    topics_raw = st.text_area("Topics (one per line)", value=default_batch, height=200)
    col_cat2, _ = st.columns([2, 4])
    with col_cat2:
        cat_options2 = ["Auto-detect"] + CATEGORIES
        selected_cat2 = st.selectbox("Category override (applies to all)", cat_options2)

    if st.button("Generate Batch", type="primary"):
        topics_list = [t.strip() for t in topics_raw.splitlines() if t.strip()]
        if not topics_list:
            st.warning("Please enter at least one topic.")
        else:
            cat_override = None if selected_cat2 == "Auto-detect" else selected_cat2
            st.session_state.setdefault("articles", [])
            progress = st.progress(0, text="Starting batch…")
            for i, topic in enumerate(topics_list):
                progress.progress((i) / len(topics_list), text=f"Generating {i+1}/{len(topics_list)}: {topic[:60]}…")
                try:
                    article = asyncio.run(run_pipeline(topic, category_override=cat_override))
                    st.session_state["articles"].insert(0, article)
                except Exception as exc:
                    st.warning(f"Skipped '{topic[:50]}…': {exc}")
            progress.progress(1.0, text="Batch complete.")
            st.success(f"Generated {len(topics_list)} articles.")

# ── BATCH — CATEGORY SWEEP ──────────────────────────────────────────────────
else:
    st.markdown("Generates one article per selected category using the built-in sample topics.")
    selected_cats = st.multiselect(
        "Select categories to cover",
        options=CATEGORIES,
        default=CATEGORIES[:5],
    )
    # Build a topic map from sample_topics.json
    topic_map = {t["category"]: t["topic"] for t in sample_topics if t.get("category")}

    if st.button("Run Category Sweep", type="primary"):
        if not selected_cats:
            st.warning("Select at least one category.")
        else:
            st.session_state.setdefault("articles", [])
            progress = st.progress(0, text="Starting sweep…")
            for i, cat in enumerate(selected_cats):
                topic = topic_map.get(cat, f"Latest developments in {cat} for green steel industry")
                progress.progress(i / len(selected_cats), text=f"{i+1}/{len(selected_cats)} — {cat}")
                try:
                    article = asyncio.run(run_pipeline(topic, category_override=cat))
                    st.session_state["articles"].insert(0, article)
                except Exception as exc:
                    st.warning(f"Skipped '{cat}': {exc}")
            progress.progress(1.0, text="Sweep complete.")
            st.success(f"Generated {len(selected_cats)} articles.")

# ---------------------------------------------------------------------------
# Results — all generated articles
# ---------------------------------------------------------------------------
if st.session_state.get("articles"):
    articles: List[Article] = st.session_state["articles"]
    st.divider()

    col_h, col_clear = st.columns([6, 1])
    with col_h:
        st.subheader(f"Generated Articles ({len(articles)})")
    with col_clear:
        if st.button("Clear all"):
            st.session_state["articles"] = []
            st.rerun()

    # Bulk download all as ZIP
    if len(articles) > 1:
        import zipfile
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for art in articles:
                slug = art.slug or "article"
                zf.writestr(f"{slug}.md", _build_md(art))
                zf.writestr(f"{slug}.json", _build_json(art))
                try:
                    zf.writestr(f"{slug}.pdf", _build_pdf(art))
                except Exception:
                    pass
        st.download_button(
            f"Download all {len(articles)} articles (.zip — PDF + MD + JSON)",
            data=zip_buf.getvalue(),
            file_name=f"green_steel_articles_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip",
        )

    for idx, art in enumerate(articles):
        _article_card(art, idx)
