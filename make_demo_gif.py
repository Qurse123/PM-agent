#!/usr/bin/env python3
"""Generate animated demo GIF for PM Agent README — matches actual UI."""

from PIL import Image, ImageDraw, ImageFont
import math, os

W, H = 1100, 620
FPS  = 14

# ── palette (matches Tailwind slate/indigo) ───────────────────────────────────
BG        = (248, 250, 252)   # slate-50
WHITE     = (255, 255, 255)
SLATE900  = ( 15,  23,  42)   # text
SLATE700  = ( 51,  65,  85)
SLATE600  = ( 71,  85, 105)
SLATE500  = (100, 116, 139)
SLATE400  = (148, 163, 184)
SLATE300  = (203, 213, 225)
SLATE200  = (226, 232, 240)
SLATE100  = (241, 245, 249)
SLATE50   = (248, 250, 252)

INDIGO600 = ( 79,  70, 229)
INDIGO700 = ( 67,  56, 202)
INDIGO50  = (238, 242, 255)
INDIGO200 = (199, 210, 254)

EMERALD600= (  5, 150, 105)
EMERALD700= (  4, 120,  87)
EMERALD50 = (236, 253, 245)
EMERALD200= (167, 243, 208)

AMBER600  = (217, 119,   6)
AMBER50   = (255, 251, 235)
AMBER200  = (253, 230, 138)

BLUE600   = ( 37,  99, 235)
BLUE50    = (239, 246, 255)
BLUE200   = (191, 219, 254)

RED600    = (220,  38,  38)
RED50     = (254, 242, 242)
RED200    = (254, 202, 202)

FONT_REG  = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

def fnt(size, bold=False):
    try:
        path = FONT_BOLD if bold else FONT_REG
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def rr(draw, xy, r, fill=None, outline=None, ow=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=ow)

def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

def lerp(a, b, t): return a + (b - a) * t
def lerp_c(c1, c2, t): return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))
def sub_t(t, start, end): return ease(max(0.0, min(1.0, (t - start) / max(0.001, end - start))))

# ── helpers ───────────────────────────────────────────────────────────────────
def text_w(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def centered_text(draw, cx, y, text, font, fill):
    w = text_w(draw, text, font)
    draw.text((cx - w // 2, y), text, font=font, fill=fill)

# ── chrome: navbar ────────────────────────────────────────────────────────────
def draw_nav(draw, show_btn=True):
    # white nav bar
    draw.rectangle([0, 0, W, 62], fill=WHITE)
    draw.line([0, 62, W, 62], fill=SLATE200, width=1)

    # indigo logo square
    rr(draw, [24, 18, 50, 44], 8, INDIGO600)
    # star / sparkle icon — 4 lines from center
    cx, cy = 37, 31
    for dx, dy in [(0,-7),(0,7),(-7,0),(7,0)]:
        draw.line([cx, cy, cx+dx, cy+dy], fill=WHITE, width=2)
    for dx, dy in [(-4,-4),(4,-4),(-4,4),(4,4)]:
        draw.line([cx, cy, cx+dx, cy+dy], fill=WHITE, width=1)

    draw.text((58, 22), "PM Agent", font=fnt(15, bold=True), fill=SLATE900)
    # measure text width to place divider correctly
    tmp = ImageDraw.Draw(Image.new("RGB", (1,1)))
    pm_w = tmp.textbbox((0,0), "PM Agent", font=fnt(15, bold=True))[2]
    div_x = 58 + pm_w + 12
    draw.line([div_x, 26, div_x, 46], fill=SLATE200, width=1)
    draw.text((div_x + 10, 26), "AI ticket proposal review", font=fnt(12), fill=SLATE400)

    if show_btn:
        bw = 86
        bx = W - bw - 20
        rr(draw, [bx, 19, bx+bw, 45], 7, INDIGO600)
        draw.text((bx + 10, 25), "+ New run", font=fnt(12, bold=True), fill=WHITE)

# ── chrome: 3-column headers ──────────────────────────────────────────────────
COL_X = [24, 382, 740]
COL_W = 334

COL_Y  = 130   # top of column content area
COL_LY = 126   # column header line y

def draw_col_headers(draw, proc_n=0, review_n=0, done_n=0):
    cols = [
        ("Processing",  proc_n,   BLUE600,    (191, 219, 254)),
        ("To Review",   review_n, AMBER600,   (253, 230, 138)),
        ("Reviewed",    done_n,   EMERALD600, (167, 243, 208)),
    ]
    for (title, count, col, border_col), x in zip(cols, COL_X):
        draw.text((x, 102), title, font=fnt(14, bold=True), fill=SLATE700)
        bx = x + text_w(draw, title, fnt(14, bold=True)) + 8
        rr(draw, [bx, 103, bx+28, 119], 10, SLATE100)
        draw.text((bx+6, 105), str(count), font=fnt(11), fill=SLATE500)
        draw.line([x, COL_LY, x + COL_W, COL_LY], fill=border_col, width=2)

def base_board(proc_n=0, review_n=0, done_n=0):
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    draw_nav(d)
    d.text((24, 72), "Analysis runs", font=fnt(20, bold=True), fill=SLATE900)
    draw_col_headers(d, proc_n, review_n, done_n)
    return img, d

def empty_col(draw, x, text):
    ey0, ey1 = COL_Y + 4, COL_Y + 64
    rr(draw, [x, ey0, x+COL_W, ey1], 10, None, outline=SLATE200, ow=1)
    for i in range(x, x+COL_W, 8):
        draw.line([i, ey0, min(i+4, x+COL_W), ey0], fill=SLATE200, width=1)
        draw.line([i, ey1, min(i+4, x+COL_W), ey1], fill=SLATE200, width=1)
    for i in range(ey0, ey1, 8):
        draw.line([x, i, x, min(i+4, ey1)], fill=SLATE200, width=1)
        draw.line([x+COL_W, i, x+COL_W, min(i+4, ey1)], fill=SLATE200, width=1)
    centered_text(draw, x + COL_W//2, ey0 + 20, text, fnt(11), SLATE400)

# ── run card (white, shadow effect) ──────────────────────────────────────────
def draw_run_card(draw, x, y, title, status_text, status_fill, status_text_col,
                  proposals="", pending="", show_review_btn=True):
    # shadow
    rr(draw, [x+2, y+2, x+COL_W-2, y+120], 10, SLATE200)
    # card
    rr(draw, [x, y, x+COL_W-4, y+118], 10, WHITE, outline=SLATE200, ow=1)

    # status pill
    rr(draw, [x+12, y+12, x+12+70, y+28], 10, status_fill)
    dot_col = status_text_col
    draw.ellipse([x+17, y+18, x+21, y+22], fill=dot_col)
    draw.text((x+25, y+14), status_text, font=fnt(10), fill=status_text_col)

    # title
    draw.text((x+12, y+36), title, font=fnt(13, bold=True), fill=SLATE900)

    # meta
    if proposals:
        draw.text((x+12, y+60), proposals, font=fnt(11), fill=SLATE400)

    if pending:
        rr(draw, [x+12, y+76, x+12+len(pending)*7+10, y+92], 10, AMBER50, outline=AMBER200, ow=1)
        draw.text((x+18, y+78), pending, font=fnt(10), fill=AMBER600)

    if show_review_btn:
        rr(draw, [x+12, y+96, x+COL_W-16, y+114], 7, INDIGO600)
        lbl = "Review"
        lw = text_w(draw, lbl, fnt(12, bold=True))
        draw.text(((x+12 + x+COL_W-16)//2 - lw//2, y+100), lbl, font=fnt(12, bold=True), fill=WHITE)

def draw_processing_card(draw, x, y, title, progress_t=0.5):
    # shimmer bar
    rr(draw, [x, y, x+COL_W-4, y+118], 10, WHITE, outline=BLUE200, ow=1)
    # blue top bar
    bar_end = x + int((COL_W-4) * ((math.sin(progress_t * 4) + 1) / 2))
    draw.line([x, y, bar_end, y], fill=INDIGO600, width=2)

    # spinner (arc approximation)
    arc_cx, arc_cy = x+23, y+22
    draw.ellipse([arc_cx-7, arc_cy-7, arc_cx+7, arc_cy+7], outline=BLUE200, width=2)
    angle = (progress_t * 360 * 3) % 360
    # draw a small arc segment
    for a in range(int(angle), int(angle)+90, 10):
        rad = math.radians(a)
        px = arc_cx + 7 * math.cos(rad)
        py = arc_cy + 7 * math.sin(rad)
        draw.ellipse([px-1, py-1, px+1, py+1], fill=BLUE600)

    draw.text((x+35, y+14), "Generating proposals...", font=fnt(10), fill=BLUE600)
    draw.text((x+12, y+38), title, font=fnt(13, bold=True), fill=SLATE700)

    # shimmer lines
    for i, width_frac in enumerate([1.0, 0.8, 0.6]):
        lw = int((COL_W - 24) * width_frac)
        pulse = (math.sin(progress_t * 4 + i * 0.5) + 1) / 2
        col = lerp_c(SLATE100, SLATE200, pulse)
        rr(draw, [x+12, y+62+i*14, x+12+lw, y+72+i*14], 4, col)

# ── SCENE 1: Main board, click New Run ────────────────────────────────────────
def scene_board(t):
    img, d = base_board(0, 0, 0)

    empty_col(d, COL_X[0], "Uploaded runs appear here")
    empty_col(d, COL_X[1], "No runs awaiting review")
    empty_col(d, COL_X[2], "Reviewed runs will appear here")

    # cursor moves to "New run" button
    btn_cx = W - 86 - 20 + 43
    btn_cy = 32
    cursor_t = sub_t(t, 0.4, 0.85)
    mx = int(lerp(W * 0.5, btn_cx - 10, cursor_t))
    my = int(lerp(H * 0.6, btn_cy + 5,  cursor_t))

    # button hover glow
    if cursor_t > 0.7:
        bw = 86
        bx = W - bw - 20
        rr(d, [bx, 19, bx+bw, 45], 7, INDIGO700)
        d.text((bx + 10, 25), "+ New run", font=fnt(12, bold=True), fill=WHITE)

    # cursor
    if t > 0.3:
        d.polygon([(mx,my),(mx+10,my+14),(mx+4,my+12),(mx+7,my+20),
                   (mx+3,my+21),(mx,my+13),(mx-5,my+17)], fill=SLATE900, outline=WHITE)

    return img

# ── SCENE 2: Panel open + fill form ──────────────────────────────────────────
def scene_panel(t):
    img, d = base_board(0, 0, 0)

    # panel slides down
    panel_h = 340
    panel_t = sub_t(t, 0.0, 0.3)
    panel_y = int(lerp(-panel_h, 74, panel_t))

    if panel_t > 0:
        rr(d, [24, panel_y, W-24, panel_y + panel_h], 12, WHITE, outline=INDIGO200, ow=1)

        # header
        d.text((36, panel_y+14), "New analysis run", font=fnt(13, bold=True), fill=SLATE900)
        # X button
        rr(d, [W-52, panel_y+10, W-34, panel_y+28], 4, SLATE100)
        d.text((W-49, panel_y+12), "x", font=fnt(11), fill=SLATE500)

        d.line([24, panel_y+42, W-24, panel_y+42], fill=SLATE100, width=1)

        # Meeting title label + input
        label_y = panel_y + 52
        d.text((36, label_y), "Meeting title", font=fnt(11, bold=True), fill=SLATE700)
        rr(d, [36, label_y+18, W//2 - 10, label_y+40], 7, WHITE, outline=SLATE300, ow=1)

        # type the title text
        title_text = "Sprint Planning May"
        chars_shown = int(len(title_text) * sub_t(t, 0.35, 0.65))
        typed = title_text[:chars_shown]
        d.text((44, label_y+22), typed, font=fnt(12), fill=SLATE900)
        # blinking cursor
        if int(t * 3) % 2 == 0 and chars_shown < len(title_text):
            cur_x = 44 + text_w(d, typed, fnt(12)) + 1
            d.line([cur_x, label_y+23, cur_x, label_y+36], fill=SLATE600, width=1)

        # Team board
        team_y = label_y + 52
        d.text((36, team_y), "Team board", font=fnt(11, bold=True), fill=SLATE700)
        d.text((W//2 - 10 + 20, team_y), "Sync", font=fnt(11), fill=INDIGO600)
        # select box with auto-matched team
        rr(d, [36, team_y+18, W-36, team_y+40], 7, WHITE, outline=SLATE300, ow=1)
        team_show_t = sub_t(t, 0.50, 0.70)
        if team_show_t > 0:
            d.text((44, team_y+22), "Engineering (ENG)", font=fnt(12),
                   fill=lerp_c(SLATE100, SLATE900, team_show_t))
        else:
            d.text((44, team_y+22), "All teams (no filter)", font=fnt(12), fill=SLATE400)

        # Upload area
        up_y = team_y + 52
        d.text((36, up_y), "Transcript", font=fnt(11, bold=True), fill=SLATE700)
        # two dashed boxes
        mid = (36 + W - 36) // 2 - 8
        for bx, blabel, bsub in [(36, "Upload files", ".txt  .vtt  .srt"),
                                  (mid + 8, "Upload folder", "Scans for transcripts")]:
            bx2 = bx + (mid - 36)
            rr(d, [bx, up_y+18, bx2, up_y+90], 8, WHITE, outline=SLATE300, ow=2)
            # folder/file icon box
            centered_text(d, (bx+bx2)//2, up_y+30, "[ ]", fnt(16), SLATE300)
            centered_text(d, (bx+bx2)//2, up_y+56, blabel, fnt(12, bold=True), SLATE600)
            centered_text(d, (bx+bx2)//2, up_y+72, bsub, fnt(10), SLATE400)

        # file selected animation
        file_t = sub_t(t, 0.70, 0.88)
        if file_t > 0:
            bx2 = mid - 36 + 36
            col = lerp_c(WHITE, INDIGO50, file_t)
            rr(d, [36, up_y+18, bx2, up_y+90], 8, col, outline=INDIGO200, ow=2)
            centered_text(d, (36+bx2)//2, up_y+30, "[ TXT ]", fnt(13), INDIGO600)
            centered_text(d, (36+bx2)//2, up_y+56, "sprint_planning_may.txt", fnt(11, bold=True), SLATE700)
            centered_text(d, (36+bx2)//2, up_y+72, "12.3 KB", fnt(10), SLATE400)

        # footer buttons
        foot_y = panel_y + panel_h - 48
        d.line([24, foot_y, W-24, foot_y], fill=SLATE100, width=1)
        rr(d, [W-176, foot_y+10, W-104, foot_y+36], 7, WHITE, outline=SLATE200, ow=1)
        d.text((W-165, foot_y+16), "Cancel", font=fnt(12), fill=SLATE600)

        create_col = lerp_c(SLATE200, INDIGO600, sub_t(t, 0.70, 0.90))
        rr(d, [W-100, foot_y+10, W-32, foot_y+36], 7, create_col)
        d.text((W-92, foot_y+16), "Create run", font=fnt(12, bold=True), fill=WHITE)

    # push existing columns down to be partially visible
    push = min(panel_h + 74, int(panel_h * panel_t) + 74)
    col_vis_y = push + 20
    if col_vis_y < H:
        for x in COL_X:
            d.text((x, col_vis_y), "...", font=fnt(12), fill=SLATE300)

    return img

# ── SCENE 3: Processing column has a card ────────────────────────────────────
def scene_processing(t):
    img, d = base_board(1, 0, 0)

    draw_processing_card(d, COL_X[0], COL_Y + 4, "Sprint Planning May", t)
    empty_col(d, COL_X[1], "No runs awaiting review")
    empty_col(d, COL_X[2], "Reviewed runs will appear here")
    return img

# ── SCENE 4: Card moves to To Review ─────────────────────────────────────────
def scene_to_review(t):
    img, d = base_board(0, 1, 0)

    empty_col(d, COL_X[0], "Uploaded runs appear here")

    # card slides into To Review
    card_t = sub_t(t, 0.0, 0.45)
    card_x = int(lerp(COL_X[0], COL_X[1], card_t))
    card_y = COL_Y + 4

    draw_run_card(d, card_x, card_y,
                  "Sprint Planning May",
                  "ready", EMERALD50, EMERALD600,
                  proposals="3 proposals",
                  pending="1 pending",
                  show_review_btn=True)

    empty_col(d, COL_X[2], "Reviewed runs will appear here")

    # cursor drifts to Review button
    btn_cx = COL_X[1] + COL_W // 2
    btn_cy = card_y + 105
    cur_t = sub_t(t, 0.55, 0.90)
    mx = int(lerp(COL_X[1] + 20, btn_cx, cur_t))
    my = int(lerp(H * 0.5, btn_cy, cur_t))
    if t > 0.5:
        d.polygon([(mx,my),(mx+10,my+14),(mx+4,my+12),(mx+7,my+20),
                   (mx+3,my+21),(mx,my+13),(mx-5,my+17)], fill=SLATE900, outline=WHITE)
    return img

# ── SCENE 5: Proposal diff view ───────────────────────────────────────────────
def scene_proposals(t):
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)

    # nav without new-run btn (detail page)
    draw_nav(d, show_btn=False)
    # breadcrumb
    d.text((24, 72), "< Runs", font=fnt(12), fill=INDIGO600)
    d.text((80, 72), "/  Sprint Planning May", font=fnt(12), fill=SLATE500)

    # heading
    d.text((24, 95), "Sprint Planning May", font=fnt(18, bold=True), fill=SLATE900)

    # approve-all button
    rr(d, [W-160, 95, W-24, 121], 7, EMERALD50, outline=EMERALD200, ow=1)
    d.text((W-148, 102), "Approve all (3)", font=fnt(12), fill=EMERALD700)

    # ── proposal card 1 ───────────────────────────────────────────────────────
    card_t = sub_t(t, 0.0, 0.30)
    c1_y   = int(lerp(H, 130, card_t))

    rr(d, [24, c1_y, W-24, c1_y+240], 12, WHITE, outline=SLATE200, ow=1)

    # badges
    rr(d, [36, c1_y+14, 90, c1_y+30], 6, BLUE50, outline=BLUE200, ow=1)
    d.text((41, c1_y+16), "UPDATE", font=fnt(10, bold=True), fill=BLUE600)
    rr(d, [96, c1_y+14, 144, c1_y+30], 6, EMERALD50, outline=EMERALD200, ow=1)
    d.text((101, c1_y+16), "Linear", font=fnt(10), fill=EMERALD600)
    rr(d, [W-118, c1_y+14, W-44, c1_y+30], 6, AMBER50, outline=AMBER200, ow=1)
    d.text((W-112, c1_y+16), "pending", font=fnt(10), fill=AMBER600)

    # title
    d.text((36, c1_y+38), "Add rate limiting to public API", font=fnt(14, bold=True), fill=SLATE900)
    d.text((36, c1_y+60), "TES-11  ·  James Liu", font=fnt(11), fill=SLATE400)

    # diff table header
    th_y = c1_y + 82
    d.line([36, th_y, W-36, th_y], fill=SLATE100, width=1)
    for lbl, x in [("FIELD", 48), ("BEFORE", 220), ("AFTER", 560)]:
        d.text((x, th_y+6), lbl, font=fnt(9, bold=True), fill=SLATE400)
    d.line([36, th_y+22, W-36, th_y+22], fill=SLATE100, width=1)

    rows = [
        ("State",    "Backlog",     "In Progress",
         (254,242,242), RED600,   (236,253,245), EMERALD600),
        ("Assignee", "—",           "James Liu",
         WHITE,        SLATE400,  (236,253,245), EMERALD600),
        ("Description", "No rate limiting...", "Implement rate limiting...",
         (254,242,242), RED600,   (236,253,245), EMERALD600),
    ]
    for ri, (field, bef, aft, bb, bc, ab, ac) in enumerate(rows):
        ry = th_y + 28 + ri * 36
        d.text((48, ry), field, font=fnt(12), fill=SLATE700)
        rr(d, [200, ry-2, 430, ry+18], 4, bb)
        d.text((208, ry), bef[:24], font=fnt(11), fill=bc)
        rr(d, [530, ry-2, W-44, ry+18], 4, ab)
        d.text((538, ry), aft[:30], font=fnt(11), fill=ac)

    # approve / deny buttons
    btn_y  = c1_y + 198
    # cursor moves to Approve
    cur_t  = sub_t(t, 0.65, 0.92)
    btn_col = lerp_c(EMERALD600, EMERALD700, cur_t * 0.5)
    rr(d, [36, btn_y, 140, btn_y+32], 7, btn_col)
    lbl = "Approve"
    lw  = text_w(d, lbl, fnt(12, bold=True))
    d.text((36 + (104-lw)//2, btn_y+9), lbl, font=fnt(12, bold=True), fill=WHITE)

    rr(d, [148, btn_y, 230, btn_y+32], 7, WHITE, outline=SLATE200, ow=1)
    d.text((162, btn_y+9), "Deny", font=fnt(12), fill=SLATE700)

    mx = int(lerp(W * 0.6, 90, cur_t))
    my = int(lerp(H * 0.7, btn_y + 16, cur_t))
    if t > 0.6:
        d.polygon([(mx,my),(mx+10,my+14),(mx+4,my+12),(mx+7,my+20),
                   (mx+3,my+21),(mx,my+13),(mx-5,my+17)], fill=SLATE900, outline=WHITE)

    # card 2 peek at bottom
    if t > 0.45:
        c2_t = sub_t(t, 0.45, 0.70)
        c2_y = int(lerp(H, 384, c2_t))
        clip = min(c2_y + 80, H - 4)
        if c2_y < H - 4 and clip > c2_y:
            rr(d, [24, c2_y, W-24, clip], 12, WHITE, outline=SLATE200, ow=1)
            rr(d, [36, c2_y+14, 90, c2_y+30], 6, BLUE50, outline=BLUE200, ow=1)
            d.text((41, c2_y+16), "UPDATE", font=fnt(10, bold=True), fill=BLUE600)
            if c2_y + 38 < clip:
                d.text((36, c2_y+38), "Implement dark mode", font=fnt(14, bold=True), fill=SLATE900)

    return img

# ── SCENE 6: Approved + Applied ──────────────────────────────────────────────
def scene_applied(t):
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    draw_nav(d, show_btn=False)
    d.text((24, 72), "< Runs", font=fnt(12), fill=INDIGO600)
    d.text((80, 72), "/  Sprint Planning May", font=fnt(12), fill=SLATE500)
    d.text((24, 95), "Sprint Planning May", font=fnt(18, bold=True), fill=SLATE900)

    suc = sub_t(t, 0.0, 0.50)

    # card now shows "applied"
    rr(d, [24, 130, W-24, 370], 12, WHITE, outline=EMERALD200, ow=2)

    # badges — status flips to applied
    rr(d, [36, 144, 90, 160], 6, BLUE50, outline=BLUE200, ow=1)
    d.text((41, 146), "UPDATE", font=fnt(10, bold=True), fill=BLUE600)
    rr(d, [96, 144, 144, 160], 6, EMERALD50, outline=EMERALD200, ow=1)
    d.text((101, 146), "Linear", font=fnt(10), fill=EMERALD600)

    # applied badge
    app_col = lerp_c(AMBER50, EMERALD50, suc)
    app_bdr  = lerp_c(AMBER200, EMERALD200, suc)
    app_txt  = lerp_c(AMBER600, EMERALD600, suc)
    status_lbl = "applied" if t > 0.3 else "pending"
    rr(d, [W-120, 144, W-44, 160], 6, app_col, outline=app_bdr, ow=1)
    d.text((W-114, 146), status_lbl, font=fnt(10), fill=app_txt)

    d.text((36, 168), "Add rate limiting to public API", font=fnt(14, bold=True), fill=SLATE900)
    d.text((36, 190), "TES-11  ·  James Liu", font=fnt(11), fill=SLATE400)

    # green success banner
    if suc > 0.1:
        ban_t = sub_t(t, 0.10, 0.40)
        rr(d, [36, 214, W-36, 260], 8, lerp_c(WHITE, EMERALD50, ban_t),
           outline=lerp_c(WHITE, EMERALD200, ban_t), ow=1)

        # animated check circle
        r = int(lerp(0, 16, ban_t))
        if r > 0:
            d.ellipse([52-r, 237-r, 52+r, 237+r], fill=lerp_c(EMERALD50, EMERALD600, ban_t))
        if ban_t > 0.6:
            ck = sub_t(t, 0.30, 0.50)
            d.line([44, 237, 49, 243], fill=WHITE, width=2)
            d.line([49, 243, 62, 228], fill=WHITE, width=2)

        msg_col = lerp_c(BG, EMERALD700, ban_t)
        d.text((76, 228), "Applied to Linear successfully", font=fnt(13, bold=True), fill=msg_col)
        d.text((76, 247), "Issue TES-11 updated: state, assignee & description", font=fnt(11), fill=lerp_c(BG, SLATE500, ban_t))

    # diff table still visible below
    rows = [
        ("State",    "Backlog",     "In Progress"),
        ("Assignee", "-",           "James Liu"),
    ]
    th_y = 272
    d.line([36, th_y, W-36, th_y], fill=SLATE100, width=1)
    for lbl, x in [("FIELD", 48), ("BEFORE", 220), ("AFTER", 560)]:
        d.text((x, th_y+6), lbl, font=fnt(9, bold=True), fill=SLATE400)
    d.line([36, th_y+22, W-36, th_y+22], fill=SLATE100, width=1)
    for ri, (field, bef, aft) in enumerate(rows):
        ry = th_y + 28 + ri * 36
        d.text((48, ry), field, font=fnt(12), fill=SLATE700)
        rr(d, [200, ry-2, 430, ry+18], 4, RED50)
        d.text((208, ry), bef, font=fnt(11), fill=RED600)
        rr(d, [530, ry-2, W-44, ry+18], 4, EMERALD50)
        d.text((538, ry), aft, font=fnt(11), fill=EMERALD600)

    # "View in Linear" link
    if t > 0.6:
        link_t = sub_t(t, 0.60, 0.85)
        rr(d, [36, 354, 180, 374], 6, lerp_c(WHITE, INDIGO50, link_t), outline=lerp_c(WHITE, INDIGO200, link_t), ow=1)
        d.text((44, 357), "View in Linear ->", font=fnt(11), fill=lerp_c(WHITE, INDIGO600, link_t))

    return img

# ── assemble ──────────────────────────────────────────────────────────────────
def make_gif(out="docs/demo.gif"):
    os.makedirs("docs", exist_ok=True)

    scenes = [
        (scene_board,       2.5),
        (scene_panel,       4.0),
        (scene_processing,  2.5),
        (scene_to_review,   3.0),
        (scene_proposals,   5.0),
        (scene_applied,     3.5),
    ]
    holds = [0.5, 0.0, 0.5, 0.5, 0.8, 2.5]

    frames, durations = [], []
    ms = int(1000 / FPS)

    for (fn, secs), hold in zip(scenes, holds):
        n = int(secs * FPS)
        for i in range(n):
            frames.append(fn(i / max(1, n - 1)))
            durations.append(ms)
        for _ in range(int(hold * FPS)):
            frames.append(fn(1.0))
            durations.append(ms)

    print(f"Rendering {len(frames)} frames at {W}x{H}...")
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )
    size_kb = os.path.getsize(out) // 1024
    print(f"Saved {out}  ({len(frames)} frames, {size_kb} KB)")

if __name__ == "__main__":
    make_gif()
