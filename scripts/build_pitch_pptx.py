#!/usr/bin/env python3
"""Generate PITCH.pptx — AgnesTheSecond pitch deck (3 slides).

Strict 3-slide structure per the latest pitch brief. Each slide is
visually dense with one central moment; speaker notes mirror the
PITCH.md script verbatim.

  1. Problem + why it matters
  2. Our solution (inputs → reasoning → outputs)
  3. Why our approach is trustworthy (framework + 124/125 + 3 proof points)
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

# ── Palette (mirror taim/insights/agnes.html) ──────────────────────────────
BG       = RGBColor(0x0A, 0x0F, 0x1A)
BG_ALT   = RGBColor(0x07, 0x0B, 0x14)
SURFACE  = RGBColor(0x11, 0x18, 0x27)
SURFACE2 = RGBColor(0x1A, 0x22, 0x36)
SURFACE3 = RGBColor(0x22, 0x2D, 0x42)
BORDER   = RGBColor(0x26, 0x33, 0x50)
TEXT     = RGBColor(0xE9, 0xF4, 0xFF)
TEXT2    = RGBColor(0x8B, 0xA3, 0xC7)
TEXT3    = RGBColor(0x5A, 0x74, 0x9A)
ACCENT   = RGBColor(0x6C, 0x63, 0xFF)
ACCENT2  = RGBColor(0x00, 0xD4, 0xAA)
WARN     = RGBColor(0xF5, 0x9E, 0x0B)
DANGER   = RGBColor(0xEF, 0x44, 0x44)
SUCCESS  = RGBColor(0x22, 0xC5, 0x5E)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

FONT_HEAD = "Helvetica Neue"
FONT_BODY = "Helvetica Neue"
FONT_MONO = "Menlo"


# ── Helpers ────────────────────────────────────────────────────────────────


def set_bg(slide, prs, color=BG):
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height
    )
    bg.line.fill.background()
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.shadow.inherit = False
    slide.shapes._spTree.remove(bg._element)
    slide.shapes._spTree.insert(2, bg._element)
    return bg


def add_text(
    slide,
    left, top, width, height,
    text,
    *,
    size=18,
    bold=False,
    color=TEXT,
    align=PP_ALIGN.LEFT,
    font=FONT_BODY,
    line_spacing=None,
):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    if line_spacing:
        p.line_spacing = line_spacing
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    return tb


def rule(slide, left, top, width, color=ACCENT2, height=Inches(0.06)):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    bar.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    return bar


def kicker(slide, text, *, color=ACCENT2):
    add_text(
        slide, Inches(0.6), Inches(0.45), Inches(12), Inches(0.35),
        text.upper(), size=11, bold=True, color=color, font=FONT_BODY,
    )


def title_big(slide, text, *, size=32):
    add_text(
        slide, Inches(0.6), Inches(0.85), Inches(12), Inches(1.2),
        text, size=size, bold=True, color=TEXT, font=FONT_HEAD,
        line_spacing=1.15,
    )


def rounded(slide, l, t, w, h, *, fill=SURFACE, border=BORDER, border_w=1.0, radius=0.04):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    s.adjustments[0] = radius
    s.line.color.rgb = border
    s.line.width = Pt(border_w)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    return s


def chip(slide, l, t, text, *, fill=SURFACE2, border=BORDER, color=TEXT, bold=True, size=11, pad=0.15):
    w = Inches(pad * 2 + 0.11 * len(text) + 0.2)
    h = Inches(0.36)
    s = rounded(slide, l, t, w, h, fill=fill, border=border, radius=0.35)
    tf = s.text_frame
    tf.margin_left = Inches(pad)
    tf.margin_right = Inches(pad)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.name = FONT_BODY
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    return s, w


def page_footer(slide, idx, total):
    add_text(
        slide, Inches(0.6), Inches(7.05), Inches(10), Inches(0.3),
        "AgnesTheSecond  ·  TUM.ai × Spherecast Makeathon 2026  ·  Trustworthy sourcing, not just cheaper sourcing.",
        size=9, color=TEXT3,
    )
    add_text(
        slide, Inches(11.0), Inches(7.05), Inches(2), Inches(0.3),
        f"{idx} / {total}",
        size=9, color=TEXT3, align=PP_ALIGN.RIGHT,
    )


def add_notes(slide, script):
    slide.notes_slide.notes_text_frame.text = script


# ── Slide 1: Problem ───────────────────────────────────────────────────────


def slide_problem(prs, idx, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    kicker(slide, "Problem", color=WARN)
    title_big(
        slide,
        "CPG companies leave money on the table because\ndemand is fragmented and substitution is hard to prove.",
        size=26,
    )
    rule(slide, Inches(0.6), Inches(2.35), Inches(0.5))

    pains = [
        ("Fragmented demand",
         "The same ingredient is bought by many companies and products with no shared visibility. No volume leverage.",
         ACCENT2),
        ("Hidden single-source risk",
         "Consolidation can look attractive, but if only 1–2 suppliers remain, a single disruption takes out the line.",
         WARN),
        ("Compliance is the blocker",
         "Cheaper alternatives only count if they are functionally valid AND meet quality / regulatory requirements.",
         DANGER),
    ]
    col_w = Inches(4.05)
    gap = Inches(0.15)
    start_x = Inches(0.6)
    top = Inches(2.85)
    card_h = Inches(3.05)
    for i, (head, body, color) in enumerate(pains):
        x = start_x + i * (col_w + gap)
        rounded(slide, x, top, col_w, card_h, fill=SURFACE, border=BORDER, radius=0.06)
        # Accent left-bar
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, x, top, Inches(0.09), card_h,
        )
        bar.line.fill.background()
        bar.fill.solid()
        bar.fill.fore_color.rgb = color
        # Number
        add_text(
            slide, x + Inches(0.35), top + Inches(0.3), col_w - Inches(0.5), Inches(0.4),
            f"0{i + 1}", size=14, bold=True, color=color, font=FONT_MONO,
        )
        # Head
        add_text(
            slide, x + Inches(0.35), top + Inches(0.75), col_w - Inches(0.5), Inches(0.7),
            head, size=22, bold=True, color=TEXT, font=FONT_HEAD, line_spacing=1.1,
        )
        # Body
        add_text(
            slide, x + Inches(0.35), top + Inches(1.55), col_w - Inches(0.55), Inches(1.4),
            body, size=13, color=TEXT2, line_spacing=1.4,
        )

    # Footer conclusion line
    add_text(
        slide, Inches(0.6), Inches(6.3), Inches(12.2), Inches(0.5),
        "Most tools stop at cost. Procurement teams need a recommendation they can defend to a CFO.",
        size=15, bold=True, color=WARN,
    )

    page_footer(slide, idx, total)
    add_notes(
        slide,
        "CPG companies leave money on the table because demand is "
        "fragmented and substitution is hard to prove. The same ingredient "
        "is often bought by multiple companies and products with no shared "
        "visibility — that blocks volume leverage and creates hidden "
        "single-source risk. And consolidation is only useful if the "
        "substitute still meets quality and compliance requirements. "
        "Otherwise you've just traded a cost problem for a compliance "
        "incident. Most tools stop at cost. Procurement teams need a "
        "recommendation they can actually defend.",
    )


# ── Slide 2: Solution ──────────────────────────────────────────────────────


def slide_solution(prs, idx, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    kicker(slide, "Our solution")
    title_big(
        slide,
        "Agnes turns fragmented procurement data\ninto evidence-backed sourcing decisions.",
        size=26,
    )
    rule(slide, Inches(0.6), Inches(2.35), Inches(0.5))

    # Three-column flow: Inputs → Reasoning → Outputs
    cols = [
        ("INPUTS", ACCENT2, [
            "BOMs + supplier–product links",
            "2 years of procurement history",
            "Supplier ratings + certifications",
            "Market-benchmark pricing",
        ]),
        ("REASONING", ACCENT, [
            "Substitution detection (variant / functional)",
            "Compliance-fit checks",
            "Risk detection (5 risk types)",
            "Prioritization on 5 weighted dimensions",
        ]),
        ("OUTPUTS", SUCCESS, [
            "Consolidation proposals w/ evidence",
            "Substitution standardization",
            "Risk mitigation actions",
            "Cost-optimization opportunities",
        ]),
    ]
    col_w = Inches(4.05)
    gap = Inches(0.15)
    start_x = Inches(0.6)
    top = Inches(2.85)
    card_h = Inches(3.1)
    for i, (head, color, items) in enumerate(cols):
        x = start_x + i * (col_w + gap)
        rounded(slide, x, top, col_w, card_h, fill=SURFACE, border=BORDER, radius=0.04)
        add_text(
            slide, x + Inches(0.25), top + Inches(0.22), col_w - Inches(0.5), Inches(0.4),
            head, size=11, bold=True, color=color,
        )
        for j, item in enumerate(items):
            y = top + Inches(0.65 + j * 0.58)
            dot = slide.shapes.add_shape(
                MSO_SHAPE.OVAL, x + Inches(0.25), y + Inches(0.1),
                Inches(0.14), Inches(0.14),
            )
            dot.line.fill.background()
            dot.fill.solid()
            dot.fill.fore_color.rgb = color
            add_text(
                slide, x + Inches(0.52), y, col_w - Inches(0.75), Inches(0.5),
                item, size=13, color=TEXT,
            )
        if i < len(cols) - 1:
            arrow_x = x + col_w + Inches(0.02)
            add_text(
                slide, arrow_x, top + Inches(1.35),
                Inches(0.15), Inches(0.5),
                "▸", size=22, bold=True, color=TEXT3, align=PP_ALIGN.CENTER,
            )

    # Surfaces strip
    add_text(
        slide, Inches(0.6), Inches(6.2), Inches(12.2), Inches(0.3),
        "ONE ENGINE, FOUR SURFACES",
        size=10, bold=True, color=TEXT3,
    )
    surfaces = ["Chat", "Explorer", "Insights", "Cube"]
    x = Inches(0.6)
    for s in surfaces:
        _, w = chip(slide, x, Inches(6.55), s, fill=SURFACE2, border=ACCENT2, color=ACCENT2, size=12)
        x = x + w + Inches(0.15)

    # Dataset numbers strip (right side)
    add_text(
        slide, Inches(7.3), Inches(6.2), Inches(5.5), Inches(0.3),
        "RUN AGAINST",
        size=10, bold=True, color=TEXT3, align=PP_ALIGN.RIGHT,
    )
    add_text(
        slide, Inches(7.3), Inches(6.5), Inches(5.5), Inches(0.45),
        "61 companies  ·  357 ingredients  ·  8,127 orders  ·  $1.52B spend",
        size=12, bold=True, color=TEXT2, align=PP_ALIGN.RIGHT,
    )

    page_footer(slide, idx, total)
    add_notes(
        slide,
        "Agnes profiles every ingredient across the network. It finds "
        "variant and functional substitutes. It scores consolidation "
        "opportunities across five weighted dimensions — leverage, evidence "
        "confidence, compliance fit, diversification, switching feasibility "
        "— and produces recommendations with evidence trails and caveats. "
        "Four surfaces: Chat, Explorer, Insights, Cube. Same brain. Run "
        "against the real dataset: 61 companies, 357 ingredients, 40 "
        "suppliers, 8,127 procurement orders, $1.52 billion in spend. "
        "On that dataset Agnes identified 125 consolidation opportunities, "
        "117 substitution groups, and 89 risk items.",
    )


# ── Slide 3: Trustworthy ───────────────────────────────────────────────────


def slide_trustworthy(prs, idx, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, prs)
    kicker(slide, "Why our approach is trustworthy")
    title_big(
        slide,
        "Agnes is designed to be defensible, not just impressive.",
        size=26,
    )
    rule(slide, Inches(0.6), Inches(1.95), Inches(0.5))

    # LEFT: 5-dimension framework + hard rule
    fw_x = Inches(0.6)
    fw_y = Inches(2.4)
    fw_w = Inches(6.55)
    rounded(slide, fw_x, fw_y, fw_w, Inches(3.6), fill=SURFACE, border=BORDER, radius=0.04)
    add_text(
        slide, fw_x + Inches(0.25), fw_y + Inches(0.2), fw_w - Inches(0.5), Inches(0.4),
        "PRIORITIZATION FRAMEWORK",
        size=11, bold=True, color=ACCENT2,
    )
    add_text(
        slide, fw_x + Inches(0.25), fw_y + Inches(0.55), fw_w - Inches(0.5), Inches(0.5),
        "5 dimensions.  One weighted score.",
        size=15, bold=True, color=TEXT, font=FONT_HEAD,
    )

    dims = [
        ("Consolidation leverage",    0.35, ACCENT2, False),
        ("Evidence confidence",       0.25, ACCENT2, False),
        ("Compliance fit",            0.20, ACCENT2, False),
        ("Supplier diversification",  0.10, DANGER,  True),
        ("Switching feasibility",     0.10, ACCENT2, False),
    ]
    max_bar_in = 3.1
    bar_row_h = 0.38
    y0 = 3.55
    for i, (label, weight, color, is_key) in enumerate(dims):
        y = Inches(y0 + i * bar_row_h)
        add_text(
            slide, fw_x + Inches(0.25), y, Inches(2.4), Inches(0.35),
            label, size=11, bold=is_key, color=DANGER if is_key else TEXT,
        )
        if is_key:
            add_text(
                slide, fw_x + Inches(2.5), y, Inches(0.2), Inches(0.35),
                "⚙", size=12, bold=True, color=DANGER,
            )
        track = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, fw_x + Inches(2.7), y + Inches(0.09),
            Inches(max_bar_in), Inches(0.16),
        )
        track.line.fill.background()
        track.fill.solid()
        track.fill.fore_color.rgb = SURFACE2
        fw_fill = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, fw_x + Inches(2.7), y + Inches(0.09),
            Inches(max_bar_in * (weight / 0.35)), Inches(0.16),
        )
        fw_fill.line.fill.background()
        fw_fill.fill.solid()
        fw_fill.fill.fore_color.rgb = color
        add_text(
            slide, fw_x + Inches(5.85), y, Inches(0.6), Inches(0.35),
            f"{weight:.2f}", size=11, bold=True, color=color, font=FONT_MONO,
            align=PP_ALIGN.RIGHT,
        )

    # RIGHT: 124/125 + hard rule
    rt_x = Inches(7.4)
    rt_y = Inches(2.4)
    rt_w = Inches(5.4)
    rounded(slide, rt_x, rt_y, rt_w, Inches(3.6), fill=SURFACE, border=ACCENT2, border_w=1.25, radius=0.04)
    add_text(
        slide, rt_x + Inches(0.25), rt_y + Inches(0.2), rt_w - Inches(0.5), Inches(0.4),
        "THE HARD RULE",
        size=11, bold=True, color=ACCENT2,
    )
    add_text(
        slide, rt_x, rt_y + Inches(0.55), rt_w, Inches(1.4),
        "124 / 125",
        size=96, bold=True, color=TEXT, align=PP_ALIGN.CENTER,
        font=FONT_HEAD, line_spacing=0.9,
    )
    add_text(
        slide, rt_x + Inches(0.25), rt_y + Inches(2.05), rt_w - Inches(0.5), Inches(0.5),
        "consolidation opportunities trigger\nthe anti-monopoly veto.",
        size=13, bold=True, color=ACCENT2, align=PP_ALIGN.CENTER, line_spacing=1.2,
    )
    add_text(
        slide, rt_x + Inches(0.25), rt_y + Inches(2.95), rt_w - Inches(0.5), Inches(0.55),
        "If consolidation would leave ≤ 2 suppliers network-wide, the grade is automatically downgraded.",
        size=10, color=TEXT2, align=PP_ALIGN.CENTER, line_spacing=1.3,
    )

    # BOTTOM: three proof points as compact cards
    cases = [
        {
            "ingredient": "Beta Carotene",
            "grade": "safe_to_consolidate",
            "grade_color": SUCCESS,
            "stats": "5 companies · 4 suppliers · score 0.85",
            "action": "Consolidate to Prinova USA — keep 3 backups.",
        },
        {
            "ingredient": "Microcrystalline Cellulose",
            "grade": "review_required",
            "grade_color": WARN,
            "stats": "13 companies · 2 suppliers · downgrade fired",
            "action": "Partial consolidation + qualified backup.",
        },
        {
            "ingredient": "Maltodextrin",
            "grade": "risk_mitigation",
            "grade_color": DANGER,
            "stats": "1 supplier (Ingredion) · 8 companies · 8 products",
            "action": "Qualify a second supplier.",
        },
    ]
    col_w = Inches(4.05)
    gap_x = Inches(0.15)
    start_x = Inches(0.6)
    top = Inches(6.15)
    card_h = Inches(0.8)
    for i, c in enumerate(cases):
        x = start_x + i * (col_w + gap_x)
        rounded(slide, x, top, col_w, card_h, fill=SURFACE, border=BORDER, radius=0.06)
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, x, top, Inches(0.08), card_h,
        )
        bar.line.fill.background()
        bar.fill.solid()
        bar.fill.fore_color.rgb = c["grade_color"]
        add_text(
            slide, x + Inches(0.25), top + Inches(0.05), col_w - Inches(0.5), Inches(0.3),
            c["ingredient"], size=12, bold=True, color=TEXT,
        )
        add_text(
            slide, x + Inches(0.25), top + Inches(0.33), col_w - Inches(0.5), Inches(0.25),
            c["stats"], size=9, color=c["grade_color"], font=FONT_MONO,
        )
        add_text(
            slide, x + Inches(0.25), top + Inches(0.55), col_w - Inches(0.5), Inches(0.25),
            c["action"], size=9.5, color=TEXT2,
        )

    page_footer(slide, idx, total)
    add_notes(
        slide,
        "Every recommendation is tied to actual supplier, spend, and "
        "benchmark data. The UI exposes evidence, confidence, and caveats. "
        "The system includes an anti-monopoly guard: when full "
        "consolidation would leave the network with ≤ 2 suppliers for an "
        "ingredient, the grade is automatically downgraded. On our "
        "dataset that fires on 124 of 125 opportunities. Three proof "
        "points. Beta Carotene — safe to consolidate, four suppliers, "
        "plenty of backup. Microcrystalline Cellulose — downgraded; "
        "Agnes recommends partial consolidation plus a qualified backup. "
        "Maltodextrin — single-source from Ingredion; Agnes recommends "
        "qualifying a second supplier. This is exactly what procurement "
        "teams need: not just answers, but justification.",
    )


# ── Main ───────────────────────────────────────────────────────────────────


def main(out_path: Path) -> None:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    builders = [slide_problem, slide_solution, slide_trustworthy]
    total = len(builders)
    for i, build in enumerate(builders, start=1):
        build(prs, i, total)

    prs.save(out_path)
    print(f"wrote {out_path} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    main(root / "PITCH.pptx")
