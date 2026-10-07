from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "BEGINNER_GUIDE.md"
OUTPUT = ROOT / "output" / "pdf" / "libreleaf-implementation-guide.pdf"

NAVY = colors.HexColor("#17352D")
BLUE = colors.HexColor("#287A55")
CYAN = colors.HexColor("#4A9B72")
GOLD = colors.HexColor("#D69A2D")
INK = colors.HexColor("#233B34")
MUTED = colors.HexColor("#63766F")
PALE = colors.HexColor("#EAF4EE")
CODE_BG = colors.HexColor("#19332C")
LIGHT_LINE = colors.HexColor("#D5E3DA")


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=14.2,
            textColor=INK,
            spaceAfter=7,
            alignment=TA_LEFT,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=25,
            textColor=NAVY,
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=17,
            textColor=BLUE,
            spaceBefore=9,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.8,
            leading=10.5,
            textColor=MUTED,
        ),
        "toc": ParagraphStyle(
            "TOC",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=14,
            textColor=INK,
        ),
        "code": ParagraphStyle(
            "Code",
            fontName="Courier",
            fontSize=7.2,
            leading=9.5,
            textColor=colors.HexColor("#F4F7FA"),
            leftIndent=0,
            rightIndent=0,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=30,
            leading=34,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            fontName="Helvetica",
            fontSize=13,
            leading=19,
            textColor=colors.HexColor("#DCEAF4"),
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=13.5,
            textColor=NAVY,
        ),
    }


def inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(
        r"\[([^]]+)\]\((https?://[^)]+)\)", r'<a href="\2" color="#2474B5">\1</a>', escaped
    )
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier" color="#0E6570">\1</font>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    return escaped


def code_block(code: str, style: ParagraphStyle) -> Table:
    pre = Preformatted(code.rstrip(), style)
    table = Table([[pre]], colWidths=[A4[0] - 38 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#30435C")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def parse_markdown(text: str, s: dict[str, ParagraphStyle]) -> list[object]:
    lines = text.splitlines()
    story: list[object] = []
    paragraph: list[str] = []
    bullets: list[str] = []
    numbers: list[str] = []
    code: list[str] = []
    in_code = False
    seen_first_section = False

    def flush_paragraph() -> None:
        if paragraph:
            story.append(Paragraph(inline_markup(" ".join(paragraph)), s["body"]))
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            items = [
                ListItem(Paragraph(inline_markup(item), s["body"]), leftIndent=10)
                for item in bullets
            ]
            story.append(ListFlowable(items, bulletType="bullet", bulletColor=CYAN, leftIndent=18))
            story.append(Spacer(1, 4))
            bullets.clear()

    def flush_numbers() -> None:
        if numbers:
            items = [
                ListItem(Paragraph(inline_markup(item), s["body"]), leftIndent=10)
                for item in numbers
            ]
            story.append(ListFlowable(items, bulletType="1", bulletColor=BLUE, leftIndent=22))
            story.append(Spacer(1, 4))
            numbers.clear()

    for line in lines:
        if line.startswith("```"):
            flush_paragraph()
            flush_bullets()
            flush_numbers()
            if in_code:
                story.append(code_block("\n".join(code), s["code"]))
                story.append(Spacer(1, 8))
                code.clear()
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_bullets()
            flush_numbers()
            if seen_first_section:
                story.append(PageBreak())
            seen_first_section = True
            story.append(Paragraph(inline_markup(line[3:]), s["h1"]))
            story.append(
                Table(
                    [["", ""]],
                    colWidths=[24 * mm, 136 * mm],
                    rowHeights=[2.2 * mm],
                    style=TableStyle(
                        [("BACKGROUND", (0, 0), (0, 0), GOLD), ("BACKGROUND", (1, 0), (1, 0), PALE)]
                    ),
                )
            )
            story.append(Spacer(1, 9))
            continue
        if line.startswith("### "):
            flush_paragraph()
            flush_bullets()
            flush_numbers()
            story.append(Paragraph(inline_markup(line[4:]), s["h2"]))
            continue
        if line.startswith("> "):
            flush_paragraph()
            flush_bullets()
            flush_numbers()
            quote = Paragraph(inline_markup(line[2:]), s["quote"])
            box = Table([[quote]], colWidths=[A4[0] - 38 * mm])
            box.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), PALE),
                        ("LINEBEFORE", (0, 0), (0, -1), 3, CYAN),
                        ("PADDING", (0, 0), (-1, -1), 9),
                    ]
                )
            )
            story.append(box)
            story.append(Spacer(1, 7))
            continue
        if line.startswith("- "):
            flush_paragraph()
            flush_numbers()
            bullets.append(line[2:])
            continue
        numbered = re.match(r"^\d+\.\s+(.*)", line)
        if numbered:
            flush_paragraph()
            flush_bullets()
            numbers.append(numbered.group(1))
            continue
        if not line.strip():
            flush_paragraph()
            flush_bullets()
            flush_numbers()
            continue
        paragraph.append(line.strip())

    flush_paragraph()
    flush_bullets()
    flush_numbers()
    return story


def draw_header_footer(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    page = canvas.getPageNumber()
    if page > 1:
        canvas.setStrokeColor(LIGHT_LINE)
        canvas.line(19 * mm, A4[1] - 15 * mm, A4[0] - 19 * mm, A4[1] - 15 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(19 * mm, A4[1] - 11.5 * mm, "LIBRELEAF - IMPLEMENTATION GUIDE")
        canvas.drawRightString(A4[0] - 19 * mm, 11 * mm, f"{page}")
        canvas.setFillColor(CYAN)
        canvas.rect(19 * mm, 9.5 * mm, 12 * mm, 1.2 * mm, fill=1, stroke=0)
    canvas.restoreState()


def cover(s: dict[str, ParagraphStyle]) -> list[object]:
    hero = Table(
        [
            [Paragraph("BUILDING<br/>LIBRELEAF", s["cover_title"])],
            [
                Paragraph(
                    "A beginner-friendly guide to ethical book discovery, OPDS feed harvesting, "
                    "exact-edition price comparison, a FastAPI frontend, persistence, and testing.",
                    s["cover_subtitle"],
                )
            ],
        ],
        colWidths=[A4[0] - 38 * mm],
        rowHeights=[78 * mm, 35 * mm],
    )
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("LEFTPADDING", (0, 0), (-1, -1), 17),
                ("RIGHTPADDING", (0, 0), (-1, -1), 17),
                ("TOPPADDING", (0, 0), (-1, 0), 18),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    chips = Table([["52 TESTS", "90%+ COVERAGE", "BR + US"]], colWidths=[52 * mm] * 3)
    chips.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("TEXTCOLOR", (0, 0), (-1, -1), BLUE),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LIGHT_LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return [
        Spacer(1, 16 * mm),
        hero,
        Spacer(1, 8 * mm),
        chips,
        Spacer(1, 18 * mm),
        Paragraph(
            "DISCOVER. COMPARE. READ.",
            ParagraphStyle(
                "Kicker",
                fontName="Helvetica-Bold",
                fontSize=9,
                textColor=GOLD,
                leading=12,
                alignment=TA_CENTER,
            ),
        ),
        Spacer(1, 5 * mm),
        Paragraph(
            "Python 3.11+  |  uv  |  FastAPI  |  HTTPX  |  SQLite  |  pytest",
            ParagraphStyle(
                "Stack", fontName="Helvetica", fontSize=9.5, textColor=MUTED, alignment=TA_CENTER
            ),
        ),
        PageBreak(),
    ]


def contents(s: dict[str, ParagraphStyle]) -> list[object]:
    chapters = [
        "1-5  Problem, ethics, APIs, structure, and pipeline",
        "6-9  ISBN identity, models, money, and secrets",
        "10-11  Open Library discovery and provider protocol",
        "12-15  Amazon, Mercado Livre, Google, and eBay",
        "16-19  Failures, SQLite, reports, and the CLI",
        "20-23  Tests, CI, credentials, and safe operation",
        "24-27  Extensions, troubleshooting, limits, and next steps",
        "28-30  Glossary, file map, and official references",
        "31-35  OPDS, frontend, testing, and exact-match scraping",
    ]
    rows = [
        [Paragraph(f"<b>{i + 1:02d}</b>", s["toc"]), Paragraph(item, s["toc"])]
        for i, item in enumerate(chapters)
    ]
    table = Table(rows, colWidths=[16 * mm, 140 * mm], rowHeights=[12 * mm] * len(rows))
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, LIGHT_LINE),
                ("TEXTCOLOR", (0, 0), (0, -1), BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return [
        Paragraph("How to use this guide", s["h1"]),
        Paragraph(
            "Read chapters 1-5 for the big picture, then follow the pipeline in order. Each later "
            "chapter maps to a source module. Return to the reference map when reviewing code or "
            "extending a provider.",
            s["body"],
        ),
        Spacer(1, 5 * mm),
        table,
        Spacer(1, 10 * mm),
        Table(
            [
                [
                    Paragraph(
                        "LEARNING GOAL",
                        ParagraphStyle(
                            "CalloutHead", fontName="Helvetica-Bold", fontSize=9, textColor=BLUE
                        ),
                    ),
                    Paragraph(
                        "Understand not only what the code does, but why each boundary and safety "
                        "control exists.",
                        s["body"],
                    ),
                ]
            ],
            colWidths=[35 * mm, 121 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PALE),
                    ("BOX", (0, 0), (-1, -1), 0.8, CYAN),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 10),
                ]
            ),
        ),
        PageBreak(),
    ]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    s = styles()
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=19 * mm,
        leftMargin=19 * mm,
        topMargin=21 * mm,
        bottomMargin=18 * mm,
        title="Building LibreLeaf",
        author="LibreLeaf",
        subject="Beginner guide to ethical book discovery and price comparison",
    )
    story = cover(s) + contents(s) + parse_markdown(SOURCE.read_text(encoding="utf-8"), s)
    document.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
