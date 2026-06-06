"""
Green Steel News Generator — AI Workflow & Pipeline Documentation
Generates the professional .docx file.
"""

from docx import Document
from docx.shared import Pt, Cm, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy
from datetime import date

# ── colour constants ────────────────────────────────────────────────────────
GREEN_DARK  = RGBColor(0x1e, 0x64, 0x30)   # #1e6430
GREEN_LIGHT = RGBColor(0xe8, 0xf5, 0xe9)   # light green for alt rows
WHITE       = RGBColor(0xFF, 0xFF, 0xFF)
BLUE_LINK   = RGBColor(0x00, 0x56, 0xB3)
BLACK       = RGBColor(0x00, 0x00, 0x00)
GREY_LIGHT  = RGBColor(0xF2, 0xF2, 0xF2)

OUTPUT_PATH = "/home/user/content-generation/docs/Green_Steel_AI_Workflow.docx"


# ── helpers ─────────────────────────────────────────────────────────────────

def set_cell_bg(cell, rgb: RGBColor):
    """Fill a table cell background colour."""
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    hex_color = f"{rgb.red:02X}{rgb.green:02X}{rgb.blue:02X}"
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)


def set_cell_borders(cell, border_color="BBBBBB", border_sz=4):
    """Add thin borders to a cell."""
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"),   "single")
        el.set(qn("w:sz"),    str(border_sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), border_color)
        tcBorders.append(el)
    tcPr.append(tcBorders)


def add_hyperlink(paragraph, url: str, text: str):
    """Insert a clickable hyperlink into a paragraph."""
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    # blue + underline style
    color_el = OxmlElement("w:color")
    color_el.set(qn("w:val"), "0056B3")
    rPr.append(color_el)
    u_el = OxmlElement("w:u")
    u_el.set(qn("w:val"), "single")
    rPr.append(u_el)
    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def add_page_number_footer(doc):
    """Add centred page numbers to every section footer."""
    for section in doc.sections:
        footer = section.footer
        footer.is_linked_to_previous = False
        p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.clear()
        run = p.add_run()
        fldChar1 = OxmlElement("w:fldChar")
        fldChar1.set(qn("w:fldCharType"), "begin")
        instrText = OxmlElement("w:instrText")
        instrText.text = "PAGE"
        fldChar2 = OxmlElement("w:fldChar")
        fldChar2.set(qn("w:fldCharType"), "end")
        run._r.append(fldChar1)
        run._r.append(instrText)
        run._r.append(fldChar2)
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def style_heading1(run_or_para, doc):
    pass  # handled via style


def apply_body_font(run, size=11):
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.font.color.rgb = BLACK


def heading1(doc, text):
    p = doc.add_heading(text, level=1)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in p.runs:
        run.font.color.rgb = GREEN_DARK
        run.font.name = "Calibri"
        run.font.bold = True
        run.font.size = Pt(16)
    return p


def heading2(doc, text):
    p = doc.add_heading(text, level=2)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in p.runs:
        run.font.color.rgb = GREEN_DARK
        run.font.name = "Calibri"
        run.font.bold = True
        run.font.size = Pt(13)
    return p


def body_para(doc, text, bold=False, italic=False, space_before=0, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    run = p.add_run(text)
    apply_body_font(run)
    run.bold   = bold
    run.italic = italic
    return p


def bullet_para(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    apply_body_font(run)
    return p


def add_table(doc, headers, rows, col_widths=None):
    """Create a styled table with dark-green header and alternating rows."""
    table = doc.add_table(rows=1+len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    # header row
    hdr_cells = table.rows[0].cells
    for i, hdr in enumerate(headers):
        cell = hdr_cells[i]
        set_cell_bg(cell, GREEN_DARK)
        set_cell_borders(cell, "1E6430", 6)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(hdr)
        run.font.bold  = True
        run.font.color.rgb = WHITE
        run.font.name  = "Calibri"
        run.font.size  = Pt(10)

    # data rows
    for r_idx, row_data in enumerate(rows):
        row_cells = table.rows[r_idx + 1].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        for c_idx, cell_text in enumerate(row_data):
            cell = row_cells[c_idx]
            set_cell_bg(cell, bg)
            set_cell_borders(cell, "CCCCCC", 4)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            # check if cell text contains a URL to hyperlink
            if cell_text.startswith("http"):
                add_hyperlink(p, cell_text, cell_text)
            else:
                run = p.add_run(cell_text)
                run.font.name  = "Calibri"
                run.font.size  = Pt(9.5)
                run.font.color.rgb = BLACK

    # column widths
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Cm(w)

    return table


def add_code_block(doc, text):
    """Add a monospace code/diagram block with light grey background."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after  = Pt(6)
    # shade the paragraph
    pPr  = p._p.get_or_add_pPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  "F2F2F2")
    pPr.append(shd)
    # left indent
    p.paragraph_format.left_indent = Cm(0.5)
    run = p.add_run(text)
    run.font.name = "Courier New"
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x1e, 0x1e, 0x1e)
    return p


def page_break(doc):
    doc.add_page_break()


# ── document setup ───────────────────────────────────────────────────────────

def build_document():
    doc = Document()

    # page margins 2.54 cm all sides
    for section in doc.sections:
        section.top_margin    = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin   = Cm(2.54)
        section.right_margin  = Cm(2.54)

    # ensure built-in styles have Calibri 11
    for style_name in ("Normal", "Body Text"):
        try:
            s = doc.styles[style_name]
            s.font.name = "Calibri"
            s.font.size = Pt(11)
        except Exception:
            pass

    add_page_number_footer(doc)

    # ── TITLE PAGE ──────────────────────────────────────────────────────────
    # project name
    proj = doc.add_paragraph()
    proj.alignment = WD_ALIGN_PARAGRAPH.CENTER
    proj.paragraph_format.space_before = Pt(72)
    proj.paragraph_format.space_after  = Pt(6)
    r = proj.add_run("Green Steel News Generator")
    r.font.name  = "Calibri"
    r.font.size  = Pt(14)
    r.font.color.rgb = GREEN_DARK
    r.font.bold  = True

    # main title
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(12)
    title_p.paragraph_format.space_after  = Pt(12)
    r = title_p.add_run("Green Steel News Generator")
    r.font.name  = "Calibri"
    r.font.size  = Pt(28)
    r.font.color.rgb = GREEN_DARK
    r.font.bold  = True

    title_p2 = doc.add_paragraph()
    title_p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p2.paragraph_format.space_after = Pt(8)
    r2 = title_p2.add_run("AI Workflow & Pipeline Documentation")
    r2.font.name  = "Calibri"
    r2.font.size  = Pt(22)
    r2.font.color.rgb = GREEN_DARK
    r2.font.bold  = False

    # subtitle
    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(48)
    r_sub = sub_p.add_run("Technical Reference Manual")
    r_sub.font.name  = "Calibri"
    r_sub.font.size  = Pt(16)
    r_sub.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    r_sub.font.italic = True

    # horizontal rule
    hr = doc.add_paragraph()
    hr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_hr = hr.add_run("─" * 60)
    r_hr.font.color.rgb = GREEN_DARK
    r_hr.font.size = Pt(12)

    # metadata block
    for label, value in [
        ("Document Type:", "Technical Reference Manual"),
        ("Project:",       "Green Steel News Generator"),
        ("Date:",          "June 2025"),
        ("Status:",        "Final — Client / Assessor Release"),
    ]:
        meta = doc.add_paragraph()
        meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
        meta.paragraph_format.space_after = Pt(4)
        rb = meta.add_run(f"{label}  ")
        rb.font.name  = "Calibri"
        rb.font.size  = Pt(11)
        rb.font.bold  = True
        rv = meta.add_run(value)
        rv.font.name  = "Calibri"
        rv.font.size  = Pt(11)

    page_break(doc)

    # ── TABLE OF CONTENTS ────────────────────────────────────────────────────
    heading1(doc, "Table of Contents")

    toc_entries = [
        ("1", "System Overview",                               "3"),
        ("2", "The 6-Agent Pipeline",                         "4"),
        ("3", "Data Pipeline Flow",                           "8"),
        ("4", "News Sources and Data Links",                  "9"),
        ("5", "AI Model and Technology Stack",               "10"),
        ("6", "The 15 Industry Categories",                  "11"),
        ("7", "Quality Scoring Framework",                   "13"),
        ("8", "Output Formats",                              "14"),
        ("9", "Environment Setup",                           "15"),
        ("10","Deployment",                                  "16"),
    ]

    for num, title, pg in toc_entries:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        tab_stops = p.paragraph_format.tab_stops
        # right-aligned tab at 15 cm for page number
        from docx.shared import Cm as _Cm
        from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER
        tab_stops.add_tab_stop(_Cm(15), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        run_num = p.add_run(f"Section {num} — {title}")
        run_num.font.name = "Calibri"
        run_num.font.size = Pt(11)
        run_pg = p.add_run(f"\t{pg}")
        run_pg.font.name = "Calibri"
        run_pg.font.size = Pt(11)

    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 1 — SYSTEM OVERVIEW
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 1 — System Overview")

    body_para(doc,
        "This system is an AI-powered news generation pipeline that automatically researches, writes, "
        "edits, quality-checks, and publishes news articles about the green steel industry. It operates "
        "as a chain of six specialised AI agents, each with a single defined responsibility. The system "
        "fetches live news from the internet, passes it to Claude AI as factual context, and produces "
        "publication-ready articles in under 60 seconds per article.")

    body_para(doc, "The workflow supports three generation modes:", bold=True, space_after=3)
    bullet_para(doc, "Single Article — one topic produces one article.")
    bullet_para(doc, "Batch Topics — multiple topics entered line by line; each generates an article.")
    bullet_para(doc, "Category Sweep — one article auto-generated per selected industry category.")

    body_para(doc, "Output formats:", bold=True, space_before=6, space_after=3)
    bullet_para(doc, "PDF — formatted document with metadata and sources.")
    bullet_para(doc, "Markdown (.md) — YAML frontmatter and article body.")
    bullet_para(doc, "JSON — complete structured data.")
    bullet_para(doc, "Bulk ZIP download — all formats for all articles in one file.")

    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 2 — THE 6-AGENT PIPELINE
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 2 — The 6-Agent Pipeline")

    body_para(doc,
        "The pipeline is composed of six discrete agents executed in strict sequence. Each agent receives "
        "the output of the previous agent as its input. No agent performs the responsibility of another.")

    # ── Agent 1 ──────────────────────────────────────────────────────────────
    heading2(doc, "Agent 1 — ResearchAgent")

    agent_table_data = [
        ["Role",
         "Gathers live news articles related to the topic from three tiered sources, scores them by "
         "relevance and recency, then passes the top results to Claude AI. Claude extracts structured "
         "facts, sources, key players, and an editorial angle from the gathered material."],
        ["Input",  "Topic string (e.g., 'SSAB hydrogen DRI plant Sweden')."],
        ["Output",
         "Research brief containing: 5–8 facts (each with company name, number, and date); "
         "3–6 source citations; a suggested editorial angle; and 3–6 key players."],
        ["Key Logic",
         "Every gathered article is labelled with its age: today / yesterday / X days ago / [OLDER SOURCE]. "
         "Claude is instructed to use only recent articles as primary facts. Older sources are used as "
         "background context only and are explicitly flagged as such in the research brief."],
    ]

    tbl = doc.add_table(rows=len(agent_table_data), cols=2)
    tbl.style = "Table Grid"
    col_widths_agent = [3.5, 12.5]
    for r_idx, (label, content) in enumerate(agent_table_data):
        cells = tbl.rows[r_idx].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        # label cell
        set_cell_bg(cells[0], GREEN_DARK)
        set_cell_borders(cells[0], "1E6430", 6)
        pl = cells[0].paragraphs[0]
        rl = pl.add_run(label)
        rl.font.name = "Calibri"; rl.font.size = Pt(10); rl.font.bold = True; rl.font.color.rgb = WHITE
        # content cell
        set_cell_bg(cells[1], bg)
        set_cell_borders(cells[1], "CCCCCC", 4)
        pc = cells[1].paragraphs[0]
        rc = pc.add_run(content)
        rc.font.name = "Calibri"; rc.font.size = Pt(10); rc.font.color.rgb = BLACK
    for row in tbl.rows:
        row.cells[0].width = Cm(3.5)
        row.cells[1].width = Cm(12.5)
    doc.add_paragraph()

    # ── Agent 2 ──────────────────────────────────────────────────────────────
    heading2(doc, "Agent 2 — CategoryAgent")
    agent2_data = [
        ["Role",
         "Reads the research brief produced by Agent 1 and assigns the article to exactly one of the "
         "15 green steel industry categories. The agent uses Claude to reason about the primary subject "
         "matter and returns a structured classification result."],
        ["Input",  "Research brief from Agent 1."],
        ["Output", "Category name; confidence score (0.0–1.0); one-sentence reasoning explaining the assignment."],
        ["Key Logic",
         "The confidence score reflects how strongly the research brief aligns with the assigned category. "
         "A score above 0.85 indicates a clear primary topic. A score below 0.60 triggers a warning in the "
         "UI that the article may span multiple categories."],
    ]
    tbl2 = doc.add_table(rows=len(agent2_data), cols=2)
    tbl2.style = "Table Grid"
    for r_idx, (label, content) in enumerate(agent2_data):
        cells = tbl2.rows[r_idx].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        set_cell_bg(cells[0], GREEN_DARK)
        set_cell_borders(cells[0], "1E6430", 6)
        pl = cells[0].paragraphs[0]
        rl = pl.add_run(label)
        rl.font.name = "Calibri"; rl.font.size = Pt(10); rl.font.bold = True; rl.font.color.rgb = WHITE
        set_cell_bg(cells[1], bg)
        set_cell_borders(cells[1], "CCCCCC", 4)
        pc = cells[1].paragraphs[0]
        rc = pc.add_run(content)
        rc.font.name = "Calibri"; rc.font.size = Pt(10); rc.font.color.rgb = BLACK
    for row in tbl2.rows:
        row.cells[0].width = Cm(3.5)
        row.cells[1].width = Cm(12.5)
    doc.add_paragraph()

    # ── Agent 3 ──────────────────────────────────────────────────────────────
    heading2(doc, "Agent 3 — WriterAgent")
    agent3_data = [
        ["Role",
         "Writes a 500–700 word news article using the research brief as the sole factual source. "
         "Follows inverted pyramid structure. Uses category-specific writing guidance for each of the "
         "15 categories to ensure the article leads with the most newsworthy data point."],
        ["Input",  "Research brief from Agent 1 plus the assigned category from Agent 2."],
        ["Output",
         "Full article: headline, dateline, body paragraphs, and a closing quote attributed to a named source."],
        ["Article Structure",
         "Line 1: Headline (title case, maximum 15 words).\n"
         "Line 2: Dateline (CITY, Month DD, YYYY).\n"
         "Paragraph 1: Lead — answers who, what, where, when in under 60 words.\n"
         "Paragraphs 2–4: Body — supporting facts, each attributed to a source or company.\n"
         "Final paragraph: Closing quote from a named individual or company spokesperson."],
        ["Key Logic",
         "Every number from the research brief must appear in the article. "
         "No paragraph may consist solely of background context without a concrete figure or named actor. "
         "The category assignment determines which data points are prioritised in the lead paragraph."],
    ]
    tbl3 = doc.add_table(rows=len(agent3_data), cols=2)
    tbl3.style = "Table Grid"
    for r_idx, (label, content) in enumerate(agent3_data):
        cells = tbl3.rows[r_idx].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        set_cell_bg(cells[0], GREEN_DARK)
        set_cell_borders(cells[0], "1E6430", 6)
        pl = cells[0].paragraphs[0]
        rl = pl.add_run(label)
        rl.font.name = "Calibri"; rl.font.size = Pt(10); rl.font.bold = True; rl.font.color.rgb = WHITE
        set_cell_bg(cells[1], bg)
        set_cell_borders(cells[1], "CCCCCC", 4)
        pc = cells[1].paragraphs[0]
        rc = pc.add_run(content)
        rc.font.name = "Calibri"; rc.font.size = Pt(10); rc.font.color.rgb = BLACK
    for row in tbl3.rows:
        row.cells[0].width = Cm(3.5)
        row.cells[1].width = Cm(12.5)
    doc.add_paragraph()

    # ── Agent 4 ──────────────────────────────────────────────────────────────
    heading2(doc, "Agent 4 — HumanizerAgent")
    agent4_data = [
        ["Role",
         "Rewrites the draft article to remove recognisable AI writing patterns and produce copy that "
         "reads as authentic wire-service journalism. A reference article is embedded in the prompt as "
         "a concrete writing target for tone and style."],
        ["Input",  "Draft article from Agent 3."],
        ["Output", "Rewritten article with all AI-pattern phrases removed and authentic journalistic voice applied."],
        ["Banned Phrases (30+)",
         "significant, notably, landscape, leverage, robust, game-changer, paradigm, paving the way, "
         "underscores, showcases, furthermore, moreover, it is worth noting, transformative, unprecedented, "
         "exciting, in today's world, going forward, at the forefront, leading the charge, holistic, synergy, "
         "milestone, landmark, it is important to, in conclusion, highlights the importance, comprehensive, "
         "utilise, harness."],
        ["Rules Enforced",
         "First sentence must state the news event directly.\n"
         "Sentence length must vary — no three consecutive sentences of similar length.\n"
         "No paragraph may begin with a gerund (e.g., 'Producing…', 'Building…').\n"
         "Every number from the research brief must appear in the rewritten version.\n"
         "Closing quote must express a judgement or assessment — not a press release statement."],
    ]
    tbl4 = doc.add_table(rows=len(agent4_data), cols=2)
    tbl4.style = "Table Grid"
    for r_idx, (label, content) in enumerate(agent4_data):
        cells = tbl4.rows[r_idx].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        set_cell_bg(cells[0], GREEN_DARK)
        set_cell_borders(cells[0], "1E6430", 6)
        pl = cells[0].paragraphs[0]
        rl = pl.add_run(label)
        rl.font.name = "Calibri"; rl.font.size = Pt(10); rl.font.bold = True; rl.font.color.rgb = WHITE
        set_cell_bg(cells[1], bg)
        set_cell_borders(cells[1], "CCCCCC", 4)
        pc = cells[1].paragraphs[0]
        rc = pc.add_run(content)
        rc.font.name = "Calibri"; rc.font.size = Pt(10); rc.font.color.rgb = BLACK
    for row in tbl4.rows:
        row.cells[0].width = Cm(3.5)
        row.cells[1].width = Cm(12.5)
    doc.add_paragraph()

    # ── Agent 5 ──────────────────────────────────────────────────────────────
    heading2(doc, "Agent 5 — QualityAgent")
    agent5_data = [
        ["Role",
         "Acts as a senior editor, scoring the humanised article across five dimensions. The pass "
         "threshold is 7.0 out of 10. Failed articles are returned to the operator with detailed "
         "feedback; they are displayed in the news feed with a warning badge."],
        ["Input",  "Humanised article from Agent 4 plus the assigned category from Agent 2."],
        ["Output",
         "Five individual dimension scores (0–10); overall score (arithmetic mean); "
         "pass/fail status; written feedback for each dimension that scored below 7.0."],
        ["Dimension 1 — Newsworthiness (0–10)",
         "Is there a real, recent, specific news event at the centre of the article? "
         "Score 0 if the article reads as background analysis or opinion without a concrete event."],
        ["Dimension 2 — Specificity (0–10)",
         "Are there concrete figures (tonnes, MW, USD, %, dates), named companies, and named individuals? "
         "Deduct points for any paragraph that contains no number. Score below 5 if any full paragraph "
         "has no number at all."],
        ["Dimension 3 — Readability (0–10)",
         "Does the article meet wire-service journalism standards? Vary sentence length. Clear, direct "
         "language. Deduct 2 points for each banned AI-filler phrase found in the final text."],
        ["Dimension 4 — Structure (0–10)",
         "Does the article open with the sharpest, most newsworthy fact? Is the closing quote a "
         "judgement rather than a promotional statement? Correct inverted pyramid structure throughout?"],
        ["Dimension 5 — Category Fit (0–10)",
         "Does the content genuinely match the assigned category? Does the lead paragraph focus on "
         "the data type specified for that category (e.g., MW for Renewable Energy, USD/t for Steel Prices)?"],
    ]
    tbl5 = doc.add_table(rows=len(agent5_data), cols=2)
    tbl5.style = "Table Grid"
    for r_idx, (label, content) in enumerate(agent5_data):
        cells = tbl5.rows[r_idx].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        set_cell_bg(cells[0], GREEN_DARK)
        set_cell_borders(cells[0], "1E6430", 6)
        pl = cells[0].paragraphs[0]
        rl = pl.add_run(label)
        rl.font.name = "Calibri"; rl.font.size = Pt(10); rl.font.bold = True; rl.font.color.rgb = WHITE
        set_cell_bg(cells[1], bg)
        set_cell_borders(cells[1], "CCCCCC", 4)
        pc = cells[1].paragraphs[0]
        rc = pc.add_run(content)
        rc.font.name = "Calibri"; rc.font.size = Pt(10); rc.font.color.rgb = BLACK
    for row in tbl5.rows:
        row.cells[0].width = Cm(3.5)
        row.cells[1].width = Cm(12.5)
    doc.add_paragraph()

    # ── Agent 6 ──────────────────────────────────────────────────────────────
    heading2(doc, "Agent 6 — PublisherAgent")
    agent6_data = [
        ["Role",
         "Writes the final article and all associated metadata to output files and serves download "
         "links to the operator's browser via the Streamlit interface. This agent has no AI reasoning "
         "component — it is a deterministic file-writing and serving module."],
        ["Input",
         "Final article text; quality score object; category; confidence score; word count; "
         "sources list; key players list; topic string; creation timestamp."],
        ["Output",
         "output/<slug>.json — full structured data record.\n"
         "output/<slug>.md — YAML frontmatter followed by article body.\n"
         "PDF download — generated on demand via the browser download button.\n"
         "Bulk ZIP download — available when two or more articles exist in the feed."],
        ["Key Logic",
         "The article slug is derived from the headline (lowercase, hyphens, max 60 chars). "
         "Files are written atomically — the .json file is written first, then .md. "
         "PDF is generated in memory by ReportLab and streamed directly to the browser; "
         "it is not written to disk."],
    ]
    tbl6 = doc.add_table(rows=len(agent6_data), cols=2)
    tbl6.style = "Table Grid"
    for r_idx, (label, content) in enumerate(agent6_data):
        cells = tbl6.rows[r_idx].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        set_cell_bg(cells[0], GREEN_DARK)
        set_cell_borders(cells[0], "1E6430", 6)
        pl = cells[0].paragraphs[0]
        rl = pl.add_run(label)
        rl.font.name = "Calibri"; rl.font.size = Pt(10); rl.font.bold = True; rl.font.color.rgb = WHITE
        set_cell_bg(cells[1], bg)
        set_cell_borders(cells[1], "CCCCCC", 4)
        pc = cells[1].paragraphs[0]
        rc = pc.add_run(content)
        rc.font.name = "Calibri"; rc.font.size = Pt(10); rc.font.color.rgb = BLACK
    for row in tbl6.rows:
        row.cells[0].width = Cm(3.5)
        row.cells[1].width = Cm(12.5)
    doc.add_paragraph()

    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 3 — DATA PIPELINE FLOW
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 3 — Data Pipeline Flow")

    body_para(doc,
        "The following diagram illustrates the complete sequential data flow from user input through "
        "all six agents to the published news feed output.")

    flow_diagram = """\
USER ENTERS TOPIC
        |
        v
AGENT 1 — ResearchAgent
  Tier 1: NewsAPI (real articles, last 29 days, exact publish dates)
  Tier 2: Google News RSS (live search, free, always runs as supplement)
  Tier 3: Category RSS Feeds (fallback if fewer than 8 articles gathered)
  All articles labelled with age
        |  Claude extracts structured research brief
        v
AGENT 2 — CategoryAgent
  Assigns 1 of 15 categories
        |  Returns: confidence score + one-sentence reasoning
        v
AGENT 3 — WriterAgent
  500-700 word article
        |  Uses category-specific writing guidance
        v
AGENT 4 — HumanizerAgent
  Removes AI patterns
        |  Wire-service style rewrite
        |  Reference article embedded in prompt as concrete writing target
        v
AGENT 5 — QualityAgent
  Scores 5 dimensions
        |  Pass/fail at 7.0 / 10
        v
AGENT 6 — PublisherAgent
  Writes .json and .md output files
        |  Serves PDF via browser download
        v
NEWS FEED
  Publication-style cards with:
    - Category badge (colour-coded)
    - Quality score displayed
    - Lead paragraph visible
    - Full article expandable on click
    - Per-article downloads: PDF / Markdown / JSON
    - Bulk ZIP download (2+ articles)"""

    add_code_block(doc, flow_diagram)
    doc.add_paragraph()

    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 4 — NEWS SOURCES AND DATA LINKS
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 4 — News Sources and Data Links")

    body_para(doc,
        "The system draws from three tiers of news sources. Tier 1 (NewsAPI) is the primary source "
        "of timestamped real articles. Tier 2 (Google News RSS) supplements every query at no cost. "
        "Tier 3 consists of specialist category RSS feeds that provide domain-specific coverage when "
        "the first two tiers return fewer than eight articles.")

    sources_headers = ["Source", "Type", "URL", "What It Provides", "Key Notes"]
    sources_rows = [
        ["NewsAPI",
         "Primary (real-time)",
         "https://newsapi.org",
         "Articles from 80,000+ sources, last 29 days",
         "Requires free API key. 100 requests/day on free plan. Set NEWS_API_KEY in .env"],
        ["Google News RSS",
         "Secondary (free)",
         "https://news.google.com/rss",
         "Live search results, no key required",
         "Two queries per article — precise and broad. Always runs alongside NewsAPI"],
        ["WorldSteel Association",
         "Category RSS",
         "https://worldsteel.org",
         "Steel industry statistics and news",
         "Used for Steel Demand and Steel Prices categories"],
        ["HydrogenInsight",
         "Category RSS",
         "https://www.hydrogeninsight.com",
         "Hydrogen industry news",
         "Used for Hydrogen and Project Finance categories"],
        ["SteelWatch",
         "Category RSS",
         "https://steelwatch.org",
         "Green steel decarbonisation tracking",
         "Used for Climate Policy and Green Steel Projects"],
        ["CleanTechnica",
         "Category RSS",
         "https://cleantechnica.com",
         "Clean energy and technology news",
         "Used for Renewable Energy and Logistics categories"],
        ["Mining.com",
         "Category RSS",
         "https://www.mining.com",
         "Mining and raw materials news",
         "Used for Raw Materials and Green Iron categories"],
        ["CarbonBrief",
         "Category RSS",
         "https://carbonbrief.org",
         "Climate science and policy",
         "Used for CCS/CCUS, Trade, and Climate Policy categories"],
        ["Global CCS Institute",
         "Category RSS",
         "https://globalccsinstitute.com",
         "Carbon capture news and reports",
         "Used for CCS and CCUS category"],
        ["HydrogenInsight (RSS)",
         "Category RSS",
         "https://www.hydrogeninsight.com/rss",
         "Hydrogen project and market news",
         "Used for Hydrogen Technology and Partnerships"],
        ["RecyclingToday",
         "Category RSS",
         "https://www.recyclingtoday.com",
         "Scrap and recycling industry",
         "Used for Circular Economy category"],
        ["FuelCellsWorks",
         "Category RSS",
         "https://www.fuelcellsworks.com",
         "Fuel cell and hydrogen technology",
         "Used for Hydrogen Production category"],
        ["RenewableEnergyWorld",
         "Category RSS",
         "https://www.renewableenergyworld.com",
         "Renewable energy industry news",
         "Used for Renewable Energy category"],
    ]

    # For this table we build manually to support hyperlinks in URL column
    s_tbl = doc.add_table(rows=1 + len(sources_rows), cols=5)
    s_tbl.style = "Table Grid"
    s_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    col_w = [3.5, 3.0, 4.5, 4.5, 4.5]
    # header
    h_cells = s_tbl.rows[0].cells
    for i, hdr in enumerate(sources_headers):
        set_cell_bg(h_cells[i], GREEN_DARK)
        set_cell_borders(h_cells[i], "1E6430", 6)
        p = h_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(hdr)
        r.font.bold = True; r.font.name = "Calibri"; r.font.size = Pt(9.5); r.font.color.rgb = WHITE
    # data
    for r_idx, row_data in enumerate(sources_rows):
        row_cells = s_tbl.rows[r_idx + 1].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        for c_idx, cell_text in enumerate(row_data):
            cell = row_cells[c_idx]
            set_cell_bg(cell, bg)
            set_cell_borders(cell, "CCCCCC", 4)
            p = cell.paragraphs[0]
            if c_idx == 2:  # URL column — hyperlink
                add_hyperlink(p, cell_text, cell_text)
            else:
                r = p.add_run(cell_text)
                r.font.name = "Calibri"; r.font.size = Pt(9); r.font.color.rgb = BLACK
    # widths
    for row in s_tbl.rows:
        for i, w in enumerate(col_w):
            row.cells[i].width = Cm(w)

    doc.add_paragraph()
    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 5 — AI MODEL AND TECHNOLOGY STACK
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 5 — AI Model and Technology Stack")

    body_para(doc,
        "The following table lists every software component used in the Green Steel News Generator, "
        "including version requirements and links to official documentation.")

    tech_headers = ["Component", "Tool / Library", "Version", "Purpose", "Link"]
    tech_rows = [
        ["AI Model",         "Claude (claude-sonnet-4-6)", "Sonnet 4.6",  "Powers all 5 reasoning agents",                "https://docs.anthropic.com"],
        ["Anthropic SDK",    "anthropic",                  ">=0.30.0",    "Python SDK for Claude API",                    "https://pypi.org/project/anthropic"],
        ["Web Interface",    "Streamlit",                  ">=1.35.0",    "Browser UI and download buttons",              "https://streamlit.io"],
        ["RSS Parser",       "feedparser",                 ">=6.0.0",     "Parses RSS and Atom news feeds",               "https://pypi.org/project/feedparser"],
        ["News API Client",  "requests",                   ">=2.31.0",    "HTTP calls to NewsAPI",                        "https://pypi.org/project/requests"],
        ["HTML Cleaner",     "beautifulsoup4",             ">=4.12.0",    "Strips HTML from article summaries",           "https://pypi.org/project/beautifulsoup4"],
        ["PDF Generator",    "reportlab",                  ">=4.0.0",     "Creates formatted PDF downloads",             "https://pypi.org/project/reportlab"],
        ["Data Models",      "pydantic",                   ">=2.0.0",     "Article and quality score schemas",            "https://pypi.org/project/pydantic"],
        ["Env Variables",    "python-dotenv",              ">=1.0.0",     "Loads .env file at startup",                   "https://pypi.org/project/python-dotenv"],
    ]

    t_tbl = doc.add_table(rows=1 + len(tech_rows), cols=5)
    t_tbl.style = "Table Grid"
    t_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    t_col_w = [3.5, 4.0, 2.5, 4.5, 5.5]
    h_cells = t_tbl.rows[0].cells
    for i, hdr in enumerate(tech_headers):
        set_cell_bg(h_cells[i], GREEN_DARK)
        set_cell_borders(h_cells[i], "1E6430", 6)
        p = h_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(hdr)
        r.font.bold = True; r.font.name = "Calibri"; r.font.size = Pt(9.5); r.font.color.rgb = WHITE
    for r_idx, row_data in enumerate(tech_rows):
        row_cells = t_tbl.rows[r_idx + 1].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        for c_idx, cell_text in enumerate(row_data):
            cell = row_cells[c_idx]
            set_cell_bg(cell, bg)
            set_cell_borders(cell, "CCCCCC", 4)
            p = cell.paragraphs[0]
            if c_idx == 4:  # Link column
                add_hyperlink(p, cell_text, cell_text)
            else:
                r = p.add_run(cell_text)
                r.font.name = "Calibri"; r.font.size = Pt(9); r.font.color.rgb = BLACK
    for row in t_tbl.rows:
        for i, w in enumerate(t_col_w):
            row.cells[i].width = Cm(w)

    doc.add_paragraph()
    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 6 — THE 15 INDUSTRY CATEGORIES
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 6 — The 15 Industry Categories")

    body_para(doc,
        "The CategoryAgent assigns every article to exactly one of the following 15 categories. "
        "The category determines which data points the WriterAgent prioritises in the lead paragraph "
        "and which RSS feeds are queried during the research phase.")

    cat_headers = ["No.", "Category Name", "Description", "Primary Writing Focus"]
    cat_rows = [
        ["1",  "Renewable Energy",
         "Wind, solar, and clean power supply for steel and hydrogen production",
         "PPA agreements, MW capacity, grid connection milestones"],
        ["2",  "Hydrogen Production & Technology",
         "Green hydrogen production methods, electrolyser technology",
         "Electrolyser capacity (MW), cost per kg, supplier names"],
        ["3",  "Green Iron & Low-Carbon Feedstocks",
         "DRI, HBI, and low-carbon iron ore supply",
         "DRI/HBI output (Mt), iron ore grade, emissions vs blast furnace"],
        ["4",  "Circular Economy (Scrap)",
         "Steel scrap collection, recycling, and EAF use",
         "Scrap volume (Mt/kt), EAF share %, facility name"],
        ["5",  "CCS & CCUS",
         "Carbon capture and storage at steel plants",
         "Capture rate (%), CO₂ volume (Mt/yr), injection site"],
        ["6",  "Steel Demand, Procurement & End Markets",
         "Buyer commitments and offtake volumes",
         "Offtake volume (kt/yr), buyer name, sector, contract duration"],
        ["7",  "Steel Prices & Green Premiums",
         "Benchmark prices and low-carbon premiums",
         "Price level (USD/t or EUR/t), premium range, market driver"],
        ["8",  "Raw Material Prices",
         "Iron ore, coking coal, scrap, and energy prices",
         "Spot price, direction, percentage change, named driver"],
        ["9",  "Clean Energy Logistics & Storage",
         "Hydrogen carriers, ports, pipelines, storage",
         "Carrier type, port name, capacity (GWh or kt H₂)"],
        ["10", "Project Finance & Investment",
         "Capital raises, funding structures, investors",
         "Capital amount, equity/debt/grant split, lead investors"],
        ["11", "Trade, Tariffs & Regulations",
         "Import/export measures, CBAM, quotas",
         "Tariff rate, CBAM price, affected trade flows (Mt/yr)"],
        ["12", "Climate Policy & Environment",
         "ETS prices, NDC targets, taxonomy rulings",
         "Carbon price (EUR/t CO₂), affected producer, cost impact"],
        ["13", "Corporate Offtake",
         "Long-term green steel supply agreements",
         "Volume (kt/yr), buyer, seller, duration, delivery date"],
        ["14", "Partnerships & M&A",
         "Joint ventures, acquisitions, strategic alliances",
         "Deal type, value/equity split, both party names, rationale"],
        ["15", "Green Steel Projects & Plant Development",
         "New plant construction, capacity expansions",
         "Capacity (Mt/yr), technology route, location, CAPEX, timeline"],
    ]

    c_tbl = doc.add_table(rows=1 + len(cat_rows), cols=4)
    c_tbl.style = "Table Grid"
    c_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    c_col_w = [1.0, 4.5, 5.5, 5.0]
    h_cells = c_tbl.rows[0].cells
    for i, hdr in enumerate(cat_headers):
        set_cell_bg(h_cells[i], GREEN_DARK)
        set_cell_borders(h_cells[i], "1E6430", 6)
        p = h_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(hdr)
        r.font.bold = True; r.font.name = "Calibri"; r.font.size = Pt(9.5); r.font.color.rgb = WHITE
    for r_idx, row_data in enumerate(cat_rows):
        row_cells = c_tbl.rows[r_idx + 1].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        for c_idx, cell_text in enumerate(row_data):
            cell = row_cells[c_idx]
            set_cell_bg(cell, bg)
            set_cell_borders(cell, "CCCCCC", 4)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if c_idx == 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(cell_text)
            r.font.name = "Calibri"; r.font.size = Pt(9); r.font.color.rgb = BLACK
            if c_idx == 0:
                r.font.bold = True
    for row in c_tbl.rows:
        for i, w in enumerate(c_col_w):
            row.cells[i].width = Cm(w)

    doc.add_paragraph()
    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 7 — QUALITY SCORING FRAMEWORK
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 7 — Quality Scoring Framework")

    body_para(doc,
        "Every article produced by the pipeline is evaluated by Agent 5 — QualityAgent — before "
        "it is published to the news feed. The quality framework mirrors the editorial standards of "
        "wire-service journalism, with scoring anchored to a concrete reference standard.")

    heading2(doc, "Score Bands")

    score_headers = ["Score Range", "Band", "Editorial Interpretation"]
    score_rows = [
        ["9–10", "Exceptional",          "Publish as-is. No edits required."],
        ["7–8",  "Publishable",          "Publish with minor copyediting only."],
        ["5–6",  "Needs Rewrite",        "Needs significant rewrite before publication."],
        ["0–4",  "Unacceptable",         "Would not be published. Major structural or factual issues."],
    ]
    add_table(doc, score_headers, score_rows, col_widths=[2.5, 3.5, 10.0])
    doc.add_paragraph()

    heading2(doc, "Pass Threshold")
    body_para(doc,
        "The pass threshold for the automated pipeline is 7.0 (arithmetic mean across all five dimensions). "
        "Articles scoring below 7.0 are displayed in the news feed with a warning badge and the full "
        "QualityAgent feedback. The article is not suppressed — the operator decides whether to use it.")

    heading2(doc, "Reference Standard")
    body_para(doc,
        "The reference standard used to calibrate all five scoring dimensions is the SteelWatch Corporate "
        "Scorecard article style. Key characteristics of this standard:")
    bullet_para(doc, "Specific and factual — every paragraph contains a named company and a concrete number.")
    bullet_para(doc, "No AI filler phrases — direct, active-voice sentences only.")
    bullet_para(doc, "Varied sentence length — short declarative sentences alternate with longer analytical ones.")
    bullet_para(doc, "Attribution — every claim is attributed to a named source, document, or company.")
    bullet_para(doc, "Newsworthiness — opens with the most significant development, not background context.")

    heading2(doc, "Dimension Descriptions")
    body_para(doc, "Newsworthiness (0–10):", bold=True, space_after=2)
    body_para(doc,
        "Is there a real, recent, specific news event at the centre of the article? A score of 0 is awarded "
        "if the article reads as background analysis or opinion without a concrete, datable event.")

    body_para(doc, "Specificity (0–10):", bold=True, space_after=2)
    body_para(doc,
        "Are there concrete figures — tonnes, MW, USD, percentage points, exact dates — alongside "
        "named companies and named individuals? Any paragraph with no number at all scores below 5.")

    body_para(doc, "Readability (0–10):", bold=True, space_after=2)
    body_para(doc,
        "Does the article meet wire-service journalism standards? 2 points are deducted for each "
        "banned AI-filler phrase found in the final text (see Agent 4 — HumanizerAgent for the full list).")

    body_para(doc, "Structure (0–10):", bold=True, space_after=2)
    body_para(doc,
        "Does the article open with the sharpest, most newsworthy fact? Is the closing quote a "
        "genuine judgement rather than a promotional statement? Is the inverted pyramid structure "
        "followed throughout?")

    body_para(doc, "Category Fit (0–10):", bold=True, space_after=2)
    body_para(doc,
        "Does the content genuinely match the assigned category? Does the lead paragraph focus on "
        "the data type specified for that category (e.g., MW capacity for Renewable Energy, USD/t for "
        "Steel Prices, capture rate percentage for CCS/CCUS)?")

    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 8 — OUTPUT FORMATS
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 8 — Output Formats")

    body_para(doc,
        "The PublisherAgent (Agent 6) produces output in three machine-readable formats and one "
        "print-quality format. All formats are available for download individually or as a bulk ZIP archive.")

    heading2(doc, "PDF")
    body_para(doc,
        "Generated in-memory by ReportLab and streamed directly to the browser — no file is written "
        "to disk. The PDF contains:")
    for item in [
        "Category banner with colour-coded background matching the category.",
        "Headline in large bold type.",
        "Dateline (city, date).",
        "Full article body with justified paragraph alignment.",
        "Metadata table: category, confidence score, word count, quality score, creation date.",
        "Sources list with URLs.",
        "Key players list.",
    ]:
        bullet_para(doc, item)

    heading2(doc, "Markdown (.md)")
    body_para(doc,
        "Written to output/<slug>.md. Suitable for CMS platforms (e.g., Ghost, Contentful), "
        "static site generators (e.g., Hugo, Jekyll), and documentation systems. Structure:")
    for item in [
        "YAML frontmatter block containing: title, category, dateline, word count, quality score, "
        "pass/fail status, creation timestamp, sources list, key players list.",
        "Full article body below the frontmatter separator (---).",
    ]:
        bullet_para(doc, item)

    heading2(doc, "JSON")
    body_para(doc,
        "Written to output/<slug>.json. Contains the complete structured data record for the article:")
    for item in [
        "headline, dateline, body (full text).",
        "category, confidence score.",
        "word count.",
        "All five quality dimension scores and overall score.",
        "pass/fail status.",
        "sources array (list of URL strings).",
        "key players array (list of name strings).",
        "topic (original input string).",
        "creation timestamp (ISO 8601).",
        "article slug.",
    ]:
        bullet_para(doc, item)

    heading2(doc, "Bulk ZIP Download")
    body_para(doc,
        "When two or more articles exist in the news feed, a 'Download All' button appears in the "
        "Streamlit sidebar. This packages all three formats (PDF, Markdown, JSON) for every article "
        "into a single ZIP file with a timestamped filename "
        "(e.g., green_steel_articles_20250615_143022.zip). "
        "ZIP files are generated in-memory and streamed to the browser.")

    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 9 — ENVIRONMENT SETUP
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 9 — Environment Setup")

    body_para(doc,
        "The system requires two API keys to operate. Both are stored in a .env file in the project "
        "root directory and are never committed to version control.")

    heading2(doc, "Required Keys")

    env_headers = ["Variable", "Required", "Description", "How to Obtain"]
    env_rows = [
        ["ANTHROPIC_API_KEY", "Yes",
         "Anthropic API key. Powers all five reasoning agents via Claude.",
         "https://console.anthropic.com/settings/keys"],
        ["NEWS_API_KEY", "Optional",
         "NewsAPI key for real-time news articles. Free plan: 100 requests/day. "
         "If not set, the system automatically falls back to Google News RSS only.",
         "https://newsapi.org"],
    ]

    ev_tbl = doc.add_table(rows=1 + len(env_rows), cols=4)
    ev_tbl.style = "Table Grid"
    ev_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    ev_col_w = [4.0, 2.0, 6.5, 5.5]
    h_cells = ev_tbl.rows[0].cells
    for i, hdr in enumerate(env_headers):
        set_cell_bg(h_cells[i], GREEN_DARK)
        set_cell_borders(h_cells[i], "1E6430", 6)
        p = h_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(hdr)
        r.font.bold = True; r.font.name = "Calibri"; r.font.size = Pt(9.5); r.font.color.rgb = WHITE
    for r_idx, row_data in enumerate(env_rows):
        row_cells = ev_tbl.rows[r_idx + 1].cells
        bg = GREY_LIGHT if r_idx % 2 == 0 else WHITE
        for c_idx, cell_text in enumerate(row_data):
            cell = row_cells[c_idx]
            set_cell_bg(cell, bg)
            set_cell_borders(cell, "CCCCCC", 4)
            p = cell.paragraphs[0]
            if c_idx == 3:
                add_hyperlink(p, cell_text, cell_text)
            else:
                r = p.add_run(cell_text)
                r.font.name = "Calibri"; r.font.size = Pt(9); r.font.color.rgb = BLACK
    for row in ev_tbl.rows:
        for i, w in enumerate(ev_col_w):
            row.cells[i].width = Cm(w)

    doc.add_paragraph()

    heading2(doc, ".env File Format")
    body_para(doc, "Create a file named .env in the project root with the following content:")
    add_code_block(doc,
        "ANTHROPIC_API_KEY=your_anthropic_key_here\n"
        "NEWS_API_KEY=your_newsapi_key_here   # optional")
    doc.add_paragraph()

    body_para(doc, "Important security notes:", bold=True, space_after=3)
    bullet_para(doc, "The .env file is listed in .gitignore and must never be committed to GitHub.")
    bullet_para(doc, "Never share the .env file or paste its contents into a public repository, issue, or pull request.")
    bullet_para(doc,
        "On Render.com, keys are added via the dashboard Environment Variables panel — "
        "no .env file is used in cloud deployment.")

    page_break(doc)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 10 — DEPLOYMENT
    # ════════════════════════════════════════════════════════════════════════
    heading1(doc, "Section 10 — Deployment")

    heading2(doc, "Local Development")

    body_para(doc, "Prerequisites:", bold=True, space_after=3)
    bullet_para(doc, "Python 3.10 or higher")
    bullet_para(doc, "pip package manager")
    bullet_para(doc, "A .env file with ANTHROPIC_API_KEY (and optionally NEWS_API_KEY)")

    body_para(doc, "Installation and launch:", bold=True, space_before=6, space_after=3)
    add_code_block(doc,
        "# 1. Clone the repository\n"
        "git clone https://github.com/your-org/green-steel-news-generator.git\n"
        "cd green-steel-news-generator\n\n"
        "# 2. Install dependencies\n"
        "pip install -r requirements.txt\n\n"
        "# 3. Create .env file with your API keys\n"
        "# (see Section 9 for format)\n\n"
        "# 4. Launch the application\n"
        "streamlit run app.py\n\n"
        "# Application opens at: http://localhost:8501")

    doc.add_paragraph()

    heading2(doc, "Cloud Deployment — Render.com")

    body_para(doc,
        "The repository includes a render.yaml configuration file that enables one-click deployment "
        "to Render.com. Auto-deploy is enabled — every push to the main branch triggers a new "
        "deployment automatically.")

    body_para(doc, "Deployment steps:", bold=True, space_after=3)

    steps = [
        "Push the project code to a GitHub repository.",
        "Go to https://render.com and sign in (or create a free account).",
        "Click 'New' → 'Web Service' and connect the GitHub repository.",
        "Render detects render.yaml automatically and configures the service.",
        "In the Render dashboard, go to Environment → Environment Variables.",
        "Add ANTHROPIC_API_KEY with your Anthropic API key value.",
        "Optionally add NEWS_API_KEY with your NewsAPI key value.",
        "Click 'Deploy'. Render builds the Docker image and launches the app.",
        "Your app is now live at a public Render URL (e.g., https://green-steel-news.onrender.com).",
    ]
    for i, step in enumerate(steps, 1):
        p = doc.add_paragraph(style="List Number")
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(f"{step}")
        r.font.name = "Calibri"; r.font.size = Pt(11); r.font.color.rgb = BLACK

    doc.add_paragraph()

    heading2(doc, "render.yaml Configuration Summary")
    add_code_block(doc,
        "services:\n"
        "  - type: web\n"
        "    name: green-steel-news-generator\n"
        "    runtime: python\n"
        "    buildCommand: pip install -r requirements.txt\n"
        "    startCommand: streamlit run app.py --server.port $PORT --server.address 0.0.0.0\n"
        "    envVars:\n"
        "      - key: ANTHROPIC_API_KEY\n"
        "        sync: false   # set manually in dashboard\n"
        "      - key: NEWS_API_KEY\n"
        "        sync: false   # optional")

    doc.add_paragraph()

    heading2(doc, "Local vs Cloud Feature Comparison")
    deploy_headers = ["Feature", "Local (localhost)", "Cloud (Render.com)"]
    deploy_rows = [
        ["Setup time",         "2–5 minutes",       "5–10 minutes (first deploy)"],
        ["Cost",               "Free",              "Free tier available (spins down after inactivity)"],
        ["Public URL",         "No (localhost only)", "Yes — shareable public URL"],
        ["Auto-deploy",        "Manual relaunch",   "Every push to main branch"],
        ["API key storage",    ".env file",         "Render dashboard env vars"],
        ["PDF download",       "Supported",         "Supported"],
        ["Bulk ZIP download",  "Supported",         "Supported"],
        ["Article persistence","Session only (resets on restart)", "Session only (resets on redeploy)"],
    ]
    add_table(doc, deploy_headers, deploy_rows, col_widths=[5.5, 5.0, 5.5])

    # ── save ──────────────────────────────────────────────────────────────────
    doc.save(OUTPUT_PATH)
    print(f"Document saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_document()
