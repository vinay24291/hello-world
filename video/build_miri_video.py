#!/usr/bin/env python3
"""Render the Miri Authentication Platform integration explainer."""

from __future__ import annotations

import asyncio
import math
import subprocess
import sys
import wave
from pathlib import Path

import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
BUILD = ROOT / "build"
ROBOT_PATH = ASSETS / "miri-robot.jpg"
BG_PATH = ASSETS / "server-bg.jpg"
OUT_PATH = Path("/opt/cursor/artifacts/miri-integration-apis.mp4")

W, H = 1920, 1080
FPS = 30
SR = 44100

VOICE = "en-US-GuyNeural"
PITCH = "-2Hz"

FONT_DIR = Path("/usr/share/fonts/truetype/macos")
FONT_BOLD = str(FONT_DIR / "Inter-Bold.ttf")
FONT_SEMI = str(FONT_DIR / "Inter-SemiBold.ttf")
FONT_MED = str(FONT_DIR / "Inter-Medium.ttf")
FONT_REG = str(FONT_DIR / "Inter-Regular.ttf")
FONT_MONO = str(FONT_DIR / "JetBrainsMono-Regular.ttf")
FONT_MONO_B = str(FONT_DIR / "JetBrainsMono-Bold.ttf")

CYAN = (72, 214, 255)
CYAN_SOFT = (150, 210, 235)
GOLD = (242, 186, 72)
GREEN = (78, 214, 140)
WHITE = (244, 248, 252)
MUTED = (176, 196, 216)
DIM = (130, 156, 180)
RED_SOFT = (255, 120, 110)

ALPH = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# Voice lines. On-screen copy carries the same facts, slightly more structured.
BEATS = [
    {
        "id": "intro",
        "voice": "The Miri Authentication Platform. Three products, one defense against static secrets.",
        "kicker": "THREE PRODUCTS",
        "title": "Three products.\nOne defense.",
        "visual": "overview",
    },
    {
        "id": "id",
        "voice": "Miri ID. A sixteen-character credential, dynamic and one-time, replacing usernames and passwords.",
        "kicker": "PRODUCT  01",
        "title": "Miri ID",
        "visual": "id",
    },
    {
        "id": "token",
        "voice": "Miri Token. Nine digits, generated offline: a one-time password that replaces SMS codes for multi-factor authentication.",
        "kicker": "PRODUCT  02",
        "title": "Miri Token",
        "visual": "token",
    },
    {
        "id": "card",
        "voice": "Miri Card. A one-time virtual card number, generated offline, obscuring the real card and supporting recurring merchant payments.",
        "kicker": "PRODUCT  03",
        "title": "Miri Card",
        "visual": "card",
    },
    {
        "id": "bridge",
        "voice": "Four processes take Miri live.",
        "kicker": "INTEGRATION",
        "title": "Four processes.",
        "visual": "bridge",
    },
    {
        "id": "reg",
        "voice": "Registration. Integrate MIS APIs with your application to onboard users and create their profiles and accounts.",
        "kicker": "PROCESS  01",
        "title": "Registration",
        "visual": "reg",
    },
    {
        "id": "act",
        "voice": "Activation. Use MAS APIs in your mobile apps so users can activate a Miri account and sync the authentication seed data.",
        "kicker": "PROCESS  02",
        "title": "Activation",
        "visual": "act",
    },
    {
        "id": "gen",
        "voice": "Generation. Embed the Miri SDKs for Android, iOS, Windows, and Mac, so mobile, PC, and web apps can generate a dynamic, one-time Miri number.",
        "kicker": "PROCESS  03",
        "title": "Miri Number\nGeneration",
        "visual": "gen",
    },
    {
        "id": "val",
        "voice": "Validation. Connect MDS Decoder APIs to your authentication servers to check Miri ID at login, Miri Token for two-factor, and Miri Card on each transaction.",
        "kicker": "PROCESS  04",
        "title": "Miri Number\nValidation",
        "visual": "val",
    },
    {
        "id": "outro",
        "voice": "Dynamic credentials, verified at the source.",
        "kicker": "MIRI PLATFORM",
        "title": "Verified at\nthe source.",
        "visual": "outro",
    },
]

GAP = 0.12
END_HOLD = 0.95


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


F = {
    "brand": font(FONT_BOLD, 30),
    "kicker": font(FONT_MONO, 18),
    "title": font(FONT_BOLD, 68),
    "title_sm": font(FONT_BOLD, 60),
    "body": font(FONT_REG, 28),
    "body_m": font(FONT_MED, 26),
    "small": font(FONT_REG, 20),
    "semi": font(FONT_SEMI, 22),
    "semi_sm": font(FONT_SEMI, 18),
    "mono": font(FONT_MONO_B, 42),
    "mono_md": font(FONT_MONO_B, 34),
    "mono_sm": font(FONT_MONO, 16),
    "mono_xs": font(FONT_MONO, 14),
    "digit": font(FONT_MONO_B, 64),
    "node": font(FONT_SEMI, 20),
    "node_sm": font(FONT_REG, 16),
    "card_name": font(FONT_BOLD, 26),
    "huge": font(FONT_BOLD, 84),
}


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def rgba(color, a):
    return (color[0], color[1], color[2], int(max(0, min(255, a))))


def wrap_text(text, fnt, max_w):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else f"{cur} {word}"
        if fnt.getlength(trial) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def rounded_panel(draw, box, radius, fill, outline=None, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pill(draw, xy, text, fnt, fg, bg, outline=None):
    x, y = xy
    tw = fnt.getlength(text)
    pad_x, pad_y = 14, 8
    box = (x, y, x + tw + pad_x * 2, y + fnt.size + pad_y * 2)
    rounded_panel(draw, box, radius=14, fill=bg, outline=outline, width=1)
    draw.text((x + pad_x, y + pad_y - 1), text, font=fnt, fill=fg)
    return box


def load_bases():
    bg = Image.open(BG_PATH).convert("RGB")
    # Cover 1080p with headroom for a slow drift.
    scale = max(W / bg.width, H / bg.height) * 1.12
    bg = bg.resize((int(bg.width * scale), int(bg.height * scale)), Image.Resampling.LANCZOS)
    robot = Image.open(ROBOT_PATH).convert("RGB")
    rh = 880
    rw = int(robot.width * (rh / robot.height))
    robot = robot.resize((rw, rh), Image.Resampling.LANCZOS)
    mask = Image.new("L", (rw, rh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, rw - 2, rh - 2), radius=18, fill=255)
    # A short feather on the left edge only, so the hand stays intact.
    fade = np.ones((rh, rw), np.float32)
    fade[:, :16] *= np.linspace(0.35, 1.0, 16)[None, :]
    mask = Image.fromarray((np.asarray(mask).astype(np.float32) * fade).astype(np.uint8), mode="L")
    return bg, robot, mask


def crop_bg(bg, t):
    max_x = bg.width - W
    max_y = bg.height - H
    x = int(max_x * (0.18 + 0.06 * math.sin(t * 0.17)))
    y = int(max_y * (0.42 + 0.08 * math.sin(t * 0.11)))
    x = max(0, min(max_x, x))
    y = max(0, min(max_y, y))
    frame = bg.crop((x, y, x + W, y + H))
    arr = np.asarray(frame).astype(np.float32)
    xs = np.linspace(0, 1, W)[None, :]
    # Keep the left field dark enough for type; leave the racks alive on the right.
    dark = np.clip(1.15 - xs * 0.95, 0.28, 1.0)
    lift = 0.55 + 0.45 * np.clip((xs - 0.45) / 0.55, 0, 1)
    arr *= (dark * (0.62 + 0.38 * lift))[..., None]
    # Vignette
    yy = np.linspace(-1, 1, H)[:, None]
    xx = np.linspace(-1, 1, W)[None, :]
    vig = 1 - 0.38 * np.clip(xx ** 2 * 0.6 + yy ** 2 - 0.15, 0, 1)
    arr *= vig[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def robot_origin():
    # Placed after we know robot size. Filled in main via closure.
    return ROBOT_XY


ROBOT_XY = (1368, 250)


def draw_brackets(draw, x, y, w, h, color, length=32, thick=3):
    c = rgba(color, 220)
    pairs = [
        ((x, y, x + length, y), (x, y, x, y + length)),
        ((x + w - length, y, x + w, y), (x + w, y, x + w, y + length)),
        ((x, y + h, x + length, y + h), (x, y + h - length, x, y + h)),
        ((x + w - length, y + h, x + w, y + h), (x + w, y + h - length, x + w, y + h)),
    ]
    for a, b in pairs:
        draw.line(a, fill=c, width=thick)
        draw.line(b, fill=c, width=thick)


def paste_robot(frame, robot, mask, t):
    rw, rh = robot.size
    x = W - rw - 36
    y = 132 + int(math.sin(t * 1.3) * 5)
    global ROBOT_XY
    ROBOT_XY = (x, y)
    glow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = x + rw * 0.50, y + rh * 0.22
    gd.ellipse((cx - 150, cy - 90, cx + 150, cy + 130), fill=(30, 120, 190, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    frame.paste(glow, (0, 0), glow)
    frame.paste(robot, (x, y), mask)
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    draw_brackets(d, x - 10, y - 10, rw + 20, rh + 20, CYAN, length=36, thick=3)
    # Scan line
    sy = y + int((t * 150) % rh)
    d.rectangle((x + 8, sy, x + rw - 8, sy + 2), fill=(170, 240, 255, 70))
    d.text((x + 8, y - 36), "MIRI  //  LIVE", font=F["mono_sm"], fill=rgba(CYAN, 230))
    frame.paste(overlay, (0, 0), overlay)
    return x


def header(draw, film_p):
    draw.text((72, 36), "MIRI", font=F["brand"], fill=WHITE)
    brand_w = F["brand"].getlength("MIRI")
    draw.text((72 + brand_w + 16, 42), "AUTHENTICATION PLATFORM", font=F["mono_sm"], fill=rgba(CYAN_SOFT, 230))
    # Gold-to-green swoosh under the wordmark, echoing the shield.
    x0, y0, span = 72, 78, 168
    for i in range(span):
        u = i / span
        if u < 0.45:
            col = tuple(int(lerp(GOLD[k], (220, 210, 90)[k], u / 0.45)) for k in range(3))
        else:
            col = tuple(int(lerp((220, 210, 90)[k], GREEN[k], (u - 0.45) / 0.55)) for k in range(3))
        draw.line([(x0 + i, y0), (x0 + i, y0 + 4)], fill=col + (255,))
    # Film progress
    track_x, track_w = 72, 1120
    draw.rectangle((track_x, 96, track_x + track_w, 99), fill=(255, 255, 255, 28))
    draw.rectangle((track_x, 96, track_x + int(track_w * film_p), 99), fill=rgba(CYAN, 220))


def kicker_title(draw, kicker, title, fade):
    a = int(255 * fade)
    draw.text((72, 124), kicker, font=F["kicker"], fill=rgba(CYAN, a))
    y = 156
    title_font = F["title"] if title.count("\n") == 0 and len(title) < 18 else F["title_sm"]
    for line in title.split("\n"):
        draw.text((72, y + int((1 - fade) * 16)), line, font=title_font, fill=rgba(WHITE, a))
        y += title_font.size + 6
    return y


def bullets(draw, items, y, fade, accents=None):
    a = int(255 * fade)
    for i, item in enumerate(items):
        col = (accents[i] if accents else CYAN)
        yy = y + i * 40
        draw.rounded_rectangle((74, yy + 10, 86, yy + 22), radius=2, fill=rgba(col, a))
        draw.text((100, yy), item, font=F["body_m"], fill=rgba(WHITE, a))
    return y + len(items) * 40


def stagger(p, i, n):
    start = i / (n + 0.4)
    return ease(max(0.0, min(1.0, (p - start) / 0.35)))


def flow_row(draw, labels, subs, y, p, accent=CYAN):
    n = len(labels)
    gap = 22
    left = 72
    right = 1260
    node_w = int((right - left - gap * (n - 1)) / n)
    node_h = 108
    for i, (label, sub) in enumerate(zip(labels, subs)):
        lp = stagger(p, i, n)
        x = left + i * (node_w + gap)
        rounded_panel(
            draw,
            (x, y, x + node_w, y + node_h),
            radius=16,
            fill=(8, 16, 32, int(210 * lp)),
            outline=rgba(accent, int(180 * lp)),
            width=2,
        )
        draw.text((x + 16, y + 22), f"{i + 1:02d}", font=F["mono_xs"], fill=rgba(accent, int(255 * lp)))
        draw.text((x + 16, y + 42), label, font=F["node"], fill=rgba(WHITE, int(255 * lp)))
        draw.text((x + 16, y + 70), sub, font=F["node_sm"], fill=rgba(MUTED, int(255 * lp)))
        if i < n - 1:
            ax1 = x + node_w + 2
            ax2 = x + node_w + gap - 2
            mid = y + node_h / 2
            ap = stagger(p, i + 0.45, n)
            x_end = lerp(ax1, ax2, ap)
            draw.line((ax1, mid, x_end, mid), fill=rgba(accent, int(220 * ap)), width=3)
            if ap > 0.85:
                draw.polygon(
                    [(ax2, mid), (ax2 - 9, mid - 5), (ax2 - 9, mid + 5)],
                    fill=rgba(accent, 230),
                )


def scrambled(final, local_t, frame_i, lock_time=1.15):
    locked = int(ease(min(1.0, local_t / lock_time)) * len(final))
    rng = np.random.default_rng((frame_i // 2) * 17 + 3)
    out = []
    for i, ch in enumerate(final):
        if ch in " -":
            out.append(ch)
        elif i < locked:
            out.append(ch)
        else:
            out.append(ALPH[int(rng.integers(0, len(ALPH)))])
    return "".join(out), locked / max(1, len(final.replace(" ", "").replace("-", "")))


def draw_overview(draw, y, p):
    cards = [
        ("01", "Miri ID", "16-character credential", "One-time  ·  replaces passwords", CYAN),
        ("02", "Miri Token", "9-digit one-time password", "Offline  ·  replaces SMS OTP", GOLD),
        ("03", "Miri Card", "Dynamic virtual card", "Offline  ·  recurring payments", GREEN),
    ]
    top = max(y + 28, 430)
    cw, ch, gap = 376, 230, 18
    for i, (num, name, line, sub, col) in enumerate(cards):
        lp = stagger(p, i, 3)
        x = 72 + i * (cw + gap)
        rounded_panel(draw, (x, top, x + cw, top + ch), 18, (7, 14, 28, int(200 * lp)), rgba(col, int(210 * lp)), 2)
        draw.text((x + 22, top + 22), num, font=F["mono_sm"], fill=rgba(col, int(255 * lp)))
        draw.text((x + 22, top + 58), name, font=F["card_name"], fill=rgba(WHITE, int(255 * lp)))
        draw.text((x + 22, top + 108), line, font=F["semi"], fill=rgba(WHITE, int(240 * lp)))
        draw.text((x + 22, top + 146), sub, font=F["small"], fill=rgba(MUTED, int(255 * lp)))
        # Accent bar
        draw.rectangle((x + 22, top + 196, x + 22 + int(120 * lp), top + 200), fill=rgba(col, int(255 * lp)))


def draw_id(draw, y, local_t, frame_i, p):
    bullets(
        draw,
        [
            "16-character dynamic credential",
            "One-time use",
            "Replaces static usernames and passwords",
        ],
        y + 16,
        min(1.0, p * 1.3),
    )
    code, _ = scrambled("K7M4 Q2R9 L8C3 W5N1", local_t, frame_i)
    top = 620
    rounded_panel(draw, (72, top, 1248, top + 168), 18, (6, 14, 28, 215), rgba(CYAN, 160), 2)
    draw.text((96, top + 22), "EXAMPLE  ·  ONE-TIME MIRI ID", font=F["mono_xs"], fill=rgba(CYAN, 220))
    draw.text((96, top + 58), code, font=F["mono"], fill=WHITE)
    pill(draw, (96, top + 118), "DYNAMIC", F["mono_xs"], CYAN, (10, 28, 40, 220), rgba(CYAN, 160))
    pill(draw, (230, top + 118), "ONE-TIME", F["mono_xs"], GOLD, (36, 28, 10, 220), rgba(GOLD, 150))


def draw_token(draw, y, local_t, frame_i, p):
    bullets(
        draw,
        [
            "9-digit dynamic one-time password",
            "Generated offline",
            "Secure alternative to SMS OTPs for MFA",
        ],
        y + 16,
        min(1.0, p * 1.3),
        accents=[GOLD, GOLD, GOLD],
    )
    groups = ["629", "184", "357"]
    top = 640
    rounded_panel(draw, (72, top, 1100, top + 180), 18, (6, 14, 28, 215), rgba(GOLD, 150), 2)
    draw.text((96, top + 20), "EXAMPLE  ·  OFFLINE MIRI TOKEN", font=F["mono_xs"], fill=rgba(GOLD, 230))
    x = 96
    for i, g in enumerate(groups):
        shown, _ = scrambled(g, local_t + i * 0.08, frame_i + i * 9, lock_time=1.0)
        draw.text((x, top + 62), shown, font=F["digit"], fill=WHITE)
        x += int(F["digit"].getlength(shown)) + 36
    pill(draw, (96, top + 138), "OFFLINE", F["mono_xs"], GOLD, (36, 28, 10, 220), rgba(GOLD, 150))
    pill(draw, (230, top + 138), "MULTI-FACTOR", F["mono_xs"], CYAN, (10, 28, 40, 220), rgba(CYAN, 150))


def draw_card(draw, y, local_t, p):
    bullets(
        draw,
        [
            "Dynamic one-time virtual card number",
            "Generated offline, obscuring the real card",
            "Supports recurring merchant transactions",
        ],
        y + 8,
        min(1.0, p * 1.4),
        accents=[GREEN, GREEN, GREEN],
    )
    x, top, cw, ch = 72, 590, 760, 270
    lp = ease(min(1, p * 1.2))
    rounded_panel(draw, (x, top, x + cw, top + ch), 22, (8, 22, 48, int(235 * lp)), rgba(GREEN, int(190 * lp)), 2)
    # Swoosh sits inside the card, echoing the shield mark.
    draw.arc((x + cw - 250, top + 8, x + cw + 30, top + 150), 188, 332, fill=rgba(GOLD, int(210 * lp)), width=7)
    draw.arc((x + cw - 232, top + 22, x + cw + 18, top + 162), 188, 326, fill=rgba(GREEN, int(210 * lp)), width=6)
    draw.rounded_rectangle((x + 32, top + 32, x + 86, top + 72), radius=6, fill=rgba(GOLD, int(235 * lp)))
    draw.text((x + 104, top + 36), "MIRI CARD", font=F["semi"], fill=rgba(WHITE, int(255 * lp)))
    draw.text((x + 32, top + 96), "SAMPLE  ·  DYNAMIC  ·  ONE-TIME", font=F["mono_xs"], fill=rgba(MUTED, int(255 * lp)))
    last = f"{2104 + (int(local_t / 0.45) * 173) % 7000:04d}"
    draw.text((x + 32, top + 124), f"****  ****  ****  {last}", font=F["mono_md"], fill=rgba(WHITE, int(255 * lp)))
    pill(draw, (x + 32, top + 200), "OFFLINE", F["mono_xs"], GOLD, (36, 28, 10, int(230 * lp)), rgba(GOLD, int(160 * lp)))
    pill(draw, (x + 168, top + 200), "RECURRING PAYMENTS", F["mono_xs"], GREEN, (8, 32, 24, int(230 * lp)), rgba(GREEN, int(170 * lp)))


def draw_bridge(draw, y, p):
    items = [
        ("01", "Registration", "MIS APIs", CYAN),
        ("02", "Activation", "MAS APIs", CYAN),
        ("03", "Generation", "Miri SDKs", GOLD),
        ("04", "Validation", "MDS Decoder", GREEN),
    ]
    top = max(y + 36, 460)
    cw, ch, gap = 286, 250, 16
    for i, (num, name, sub, col) in enumerate(items):
        lp = stagger(p, i, 4)
        x = 72 + i * (cw + gap)
        rounded_panel(draw, (x, top, x + cw, top + ch), 18, (7, 14, 28, int(210 * lp)), rgba(col, int(200 * lp)), 2)
        draw.text((x + 22, top + 28), num, font=F["huge"], fill=rgba(col, int(255 * lp)))
        draw.text((x + 22, top + 140), name, font=F["semi"], fill=rgba(WHITE, int(255 * lp)))
        draw.text((x + 22, top + 176), sub, font=F["small"], fill=rgba(MUTED, int(255 * lp)))


def draw_reg(draw, y, p):
    draw.text((72, y + 8), "Integrate MIS APIs with your application.", font=F["body"], fill=rgba(MUTED, int(255 * min(1, p * 1.5))))
    flow_row(
        draw,
        ["YOUR APP", "MIS APIs", "PROFILES", "ACCOUNTS"],
        ["Onboard here", "Integration", "User profiles", "Miri accounts"],
        y + 80,
        p,
        CYAN,
    )
    draw.text(
        (72, y + 220),
        "Onboard users  ·  generate the required user profiles and accounts",
        font=F["semi"],
        fill=rgba(WHITE, int(255 * ease(max(0, (p - 0.45) / 0.4)))),
    )


def draw_act(draw, y, p):
    draw.text((72, y + 8), "MAS APIs inside your mobile apps.", font=F["body"], fill=rgba(MUTED, int(255 * min(1, p * 1.5))))
    flow_row(
        draw,
        ["MOBILE APP", "MAS APIs", "ACTIVATE", "SEED DATA"],
        ["End user", "Call from device", "Miri account", "Synchronized"],
        y + 80,
        p,
        CYAN,
    )
    draw.text(
        (72, y + 220),
        "Activate the Miri account  ·  synchronize authentication seed data",
        font=F["semi"],
        fill=rgba(WHITE, int(255 * ease(max(0, (p - 0.45) / 0.4)))),
    )


def draw_gen(draw, y, local_t, frame_i, p):
    draw.text((72, y + 4), "Embed the Miri SDKs. Generate on device.", font=F["body"], fill=rgba(MUTED, int(255 * min(1, p * 1.4))))
    sdks = ["Android", "iOS", "Windows", "Mac"]
    x = 72
    yy = y + 64
    for i, name in enumerate(sdks):
        lp = stagger(p, i, 6)
        box = pill(draw, (x, yy), name.upper(), F["mono_sm"], rgba(WHITE, int(255 * lp)), (8, 20, 36, int(220 * lp)), rgba(GOLD, int(180 * lp)))
        x = box[2] + 12
    hosts = ["Mobile", "PC", "Web"]
    x = 72
    yy = y + 130
    draw.text((72, yy), "RUNS IN", font=F["mono_xs"], fill=rgba(DIM, int(255 * min(1, p * 1.2))))
    x = 180
    for i, name in enumerate(hosts):
        lp = stagger(p, i + 2, 6)
        box = pill(draw, (x, yy - 10), name.upper(), F["mono_sm"], rgba(CYAN, int(255 * lp)), (8, 24, 36, int(200 * lp)), rgba(CYAN, int(160 * lp)))
        x = box[2] + 12
    code, _ = scrambled("K7M4 Q2R9 L8C3 W5N1", local_t, frame_i, lock_time=1.3)
    top = y + 200
    rounded_panel(draw, (72, top, 1220, top + 140), 16, (6, 14, 28, 220), rgba(GOLD, 150), 2)
    draw.text((96, top + 18), "EXAMPLE  ·  DYNAMIC ONE-TIME MIRI NUMBER", font=F["mono_xs"], fill=rgba(GOLD, 230))
    draw.text((96, top + 52), code, font=F["mono"], fill=WHITE)


def draw_val(draw, y, p):
    draw.text((72, y + 4), "MDS Decoder APIs on your authentication servers.", font=F["body"], fill=rgba(MUTED, int(255 * min(1, p * 1.4))))
    rows = [
        ("Miri ID", "Login", CYAN),
        ("Miri Token", "Two-factor", GOLD),
        ("Miri Card", "Card transaction", GREEN),
    ]
    top = y + 64
    rh = 78
    for i, (name, use, col) in enumerate(rows):
        lp = stagger(p, i, 4)
        yy = top + i * (rh + 14)
        rounded_panel(draw, (72, yy, 560, yy + rh), 14, (7, 16, 30, int(210 * lp)), rgba(col, int(190 * lp)), 2)
        draw.text((94, yy + 14), name, font=F["semi"], fill=rgba(WHITE, int(255 * lp)))
        draw.text((94, yy + 42), use, font=F["small"], fill=rgba(MUTED, int(255 * lp)))
        # connector
        ap = stagger(p, i + 0.4, 4)
        ymid = yy + rh / 2
        draw.line((560, ymid, lerp(560, 680, ap), ymid), fill=rgba(col, int(200 * ap)), width=3)
    dec_p = ease(max(0, (p - 0.35) / 0.4))
    rounded_panel(draw, (690, top + 30, 980, top + 250), 16, (8, 24, 28, int(220 * dec_p)), rgba(GREEN, int(200 * dec_p)), 2)
    draw.text((714, top + 52), "MDS", font=F["mono_sm"], fill=rgba(GREEN, int(255 * dec_p)))
    draw.text((714, top + 80), "DECODER", font=F["card_name"], fill=rgba(WHITE, int(255 * dec_p)))
    draw.text((714, top + 124), "Authentication", font=F["small"], fill=rgba(MUTED, int(255 * dec_p)))
    draw.text((714, top + 150), "servers", font=F["small"], fill=rgba(MUTED, int(255 * dec_p)))
    ok = ease(max(0, (p - 0.62) / 0.3))
    if ok > 0.05:
        rounded_panel(draw, (1004, top + 78, 1240, top + 200), 16, (10, 36, 28, int(230 * ok)), rgba(GREEN, int(230 * ok)), 2)
        draw.text((1030, top + 100), "VALID", font=F["card_name"], fill=rgba(GREEN, int(255 * ok)))
        draw.text((1030, top + 140), "MATCHED", font=F["mono_sm"], fill=rgba(WHITE, int(255 * ok)))


def draw_outro(draw, y, p):
    a = int(255 * ease(min(1, p * 1.4)))
    draw.text((72, y + 10), "Dynamic credentials.", font=F["body"], fill=rgba(WHITE, a))
    items = [
        ("Miri ID", "Login"),
        ("Miri Token", "Two-factor"),
        ("Miri Card", "Payments"),
    ]
    x = 72
    yy = y + 90
    for i, (name, use) in enumerate(items):
        lp = stagger(p, i, 3)
        box = pill(
            draw,
            (x, yy),
            f"{name.upper()}   {use.upper()}",
            F["mono_sm"],
            rgba(WHITE, int(255 * lp)),
            (8, 18, 32, int(210 * lp)),
            rgba(CYAN if i == 0 else GOLD if i == 1 else GREEN, int(180 * lp)),
        )
        x = box[2] + 14
    procs = ["01  MIS", "02  MAS", "03  SDKs", "04  MDS"]
    x = 72
    yy = y + 170
    for i, name in enumerate(procs):
        lp = stagger(p, i + 1, 5)
        box = pill(draw, (x, yy), name, F["mono_sm"], rgba(CYAN, int(255 * lp)), (6, 16, 28, int(200 * lp)), rgba(CYAN, int(140 * lp)))
        x = box[2] + 12


VISUALS = {}


def render_content(overlay_draw, beat, local_t, dur, frame_i, film_p):
    p = ease(min(1.0, local_t / max(0.8, dur * 0.55)))
    fade = ease(min(1.0, local_t / 0.28))
    header(overlay_draw, film_p)
    y = kicker_title(overlay_draw, beat["kicker"], beat["title"], fade)
    kind = beat["visual"]
    if kind == "overview":
        draw_overview(overlay_draw, y, p)
    elif kind == "id":
        draw_id(overlay_draw, y, local_t, frame_i, p)
    elif kind == "token":
        draw_token(overlay_draw, y, local_t, frame_i, p)
    elif kind == "card":
        draw_card(overlay_draw, y, local_t, p)
    elif kind == "bridge":
        draw_bridge(overlay_draw, y, p)
    elif kind == "reg":
        draw_reg(overlay_draw, y, p)
    elif kind == "act":
        draw_act(overlay_draw, y, p)
    elif kind == "gen":
        draw_gen(overlay_draw, y, local_t, frame_i, p)
    elif kind == "val":
        draw_val(overlay_draw, y, p)
    elif kind == "outro":
        draw_outro(overlay_draw, y, p)


def particles(draw, t):
    rng = np.random.default_rng(4)
    for i in range(48):
        px = float(rng.random() * 1300)
        speed = 18 + float(rng.random() * 40)
        py = (float(rng.random() * H) - t * speed) % H
        r = 1.2 + float(rng.random() * 1.8)
        alpha = 40 + int(rng.random() * 70)
        col = CYAN if rng.random() > 0.75 else (140, 180, 210)
        draw.ellipse((px, py, px + r, py + r), fill=rgba(col, alpha))


def frame_at(bg, robot, mask, t, beat, local_t, dur, film_p, frame_i):
    frame = crop_bg(bg, t).convert("RGBA")
    fx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    particles(ImageDraw.Draw(fx), t)
    frame = Image.alpha_composite(frame, fx)
    base = frame.convert("RGBA")
    # robot paste expects RGB-able; use a canvas
    canvas = Image.new("RGBA", (W, H))
    canvas.paste(base, (0, 0))
    paste_robot(canvas, robot, mask, t)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    render_content(ImageDraw.Draw(overlay), beat, local_t, dur, frame_i, film_p)
    # Fade content only at the very start of each beat.
    if local_t < 0.22:
        factor = ease(local_t / 0.22)
        alpha = overlay.getchannel("A")
        overlay.putalpha(alpha.point(lambda v: int(v * factor)))
    canvas = Image.alpha_composite(canvas, overlay)
    return canvas.convert("RGB")


def beat_schedule(durations):
    timeline = []
    t = 0.0
    for beat, dur in zip(BEATS, durations):
        timeline.append((beat, t, t + dur))
        t += dur + GAP
    total = t - GAP + END_HOLD
    return timeline, total


def active_beat(timeline, t, total):
    for i, (beat, a, b) in enumerate(timeline):
        if a <= t < b:
            return beat, t - a, b - a
        if i + 1 < len(timeline) and b <= t < timeline[i + 1][1]:
            # Hold the current card across the short beat gap.
            return beat, (b - a) + (t - b), (b - a)
    beat, a, b = timeline[-1]
    return beat, (b - a) + (t - b), (b - a)


def tighten_clip(audio: np.ndarray) -> np.ndarray:
    """Shorten the long pauses neural TTS inserts after periods."""
    thresh = 0.01
    win = max(1, int(0.008 * SR))
    env = np.convolve(np.abs(audio), np.ones(win) / win, mode="same")
    silent = env < thresh
    padded = np.concatenate([[False], silent, [False]])
    diff = np.diff(padded.astype(np.int8))
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]
    max_keep = int(0.15 * SR)
    pieces = []
    cursor = 0
    for s, e in zip(starts, ends):
        pieces.append(audio[cursor:s])
        run = audio[s:e]
        if len(run) > max_keep:
            mid = len(run) // 2
            half = max_keep // 2
            pieces.append(run[mid - half : mid - half + max_keep])
        else:
            pieces.append(run)
        cursor = e
    pieces.append(audio[cursor:])
    if not pieces:
        return audio
    out = np.concatenate(pieces)
    # Trim only the outer silence, leaving a breath at each end.
    env = np.convolve(np.abs(out), np.ones(win) / win, mode="same")
    audible = np.where(env >= thresh)[0]
    if len(audible) == 0:
        return out
    pad_l, pad_r = int(0.04 * SR), int(0.06 * SR)
    a = max(0, int(audible[0]) - pad_l)
    b = min(len(out), int(audible[-1]) + pad_r)
    return out[a:b]


async def synthesize(rate: str):
    BUILD.mkdir(parents=True, exist_ok=True)
    paths = []
    for beat in BEATS:
        path = BUILD / f"{beat['id']}.mp3"
        comm = edge_tts.Communicate(beat["voice"], VOICE, rate=rate, pitch=PITCH)
        await comm.save(str(path))
        paths.append(path)
    return paths


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def mp3_to_wav(src: Path, dst: Path):
    subprocess.check_call(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ar", str(SR), "-ac", "1", str(dst)],
    )


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        n = wf.getnframes()
        audio = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    return audio


def write_wav(path: Path, audio: np.ndarray):
    pcm = np.clip(audio, -1, 1)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def assemble_audio(mp3s):
    wavs = []
    durations = []
    for src in mp3s:
        dst = src.with_suffix(".wav")
        mp3_to_wav(src, dst)
        durations.append(wav_duration(dst))
        wavs.append(dst)
    timeline, total = beat_schedule(durations)
    clips = [tighten_clip(read_wav(path)) for path in wavs]
    durations = [len(clip) / SR for clip in clips]
    timeline, total = beat_schedule(durations)
    n = int(math.ceil(total * SR))
    voice = np.zeros(n, dtype=np.float32)
    for clip, (beat, a, b) in zip(clips, timeline):
        start = int(a * SR)
        end = min(start + len(clip), n)
        voice[start:end] += clip[: end - start]
    # Low cyber drone under the voice.
    tt = np.arange(n) / SR
    drone = (
        0.035 * np.sin(2 * np.pi * 55 * tt)
        + 0.018 * np.sin(2 * np.pi * 82.4 * tt)
        + 0.012 * np.sin(2 * np.pi * 110 * tt)
    )
    drone *= 0.65 + 0.35 * np.sin(2 * np.pi * 0.08 * tt)
    mix = voice * 0.92 + drone
    fin = int(0.12 * SR)
    fout = int(0.40 * SR)
    mix[:fin] *= np.linspace(0, 1, fin)
    mix[-fout:] *= np.linspace(1, 0, fout)
    peak = np.max(np.abs(mix)) + 1e-6
    mix *= min(1.0, 0.92 / peak)
    out = BUILD / "mix.wav"
    write_wav(out, mix)
    return out, timeline, total, durations


def render(preview: bool):
    BUILD.mkdir(parents=True, exist_ok=True)
    rate = "+4%"
    audio_path = timeline = total = None
    for attempt in range(3):
        mp3s = asyncio.run(synthesize(rate))
        audio_path, timeline, total, durations = assemble_audio(mp3s)
        print(f"speech {sum(durations):.2f}s  total {total:.2f}s  rate {rate}")
        if total <= 66 or attempt == 2:
            break
        # Speed the read just enough to land near one minute.
        faster = int(round((total / 61.0 - 1.0) * 100 + int(rate.strip("%+"))))
        rate = f"+{min(18, max(6, faster))}%"
        print(f"retiming at {rate}")
    bg, robot, mask = load_bases()
    nframes = int(round(total * FPS))
    print(f"frames {nframes}  duration {total:.2f}s  robot {robot.size}")

    if preview:
        prev = BUILD / "preview"
        prev.mkdir(exist_ok=True)
        for beat, a, b in timeline:
            t = (a + b) / 2
            local = t - a
            img = frame_at(bg, robot, mask, t, beat, local, b - a, t / total, int(t * FPS))
            img.save(prev / f"{beat['id']}.jpg", quality=90)
            print("preview", beat["id"])
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-",
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(OUT_PATH),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(nframes):
            t = i / FPS
            beat, local_t, dur = active_beat(timeline, t, total)
            img = frame_at(bg, robot, mask, t, beat, local_t, dur, min(1, t / total), i)
            proc.stdin.write(img.tobytes())
            if i % 150 == 0:
                print(f"frame {i}/{nframes}  {beat['id']}")
    finally:
        proc.stdin.close()
        code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg exited {code}")
    print("wrote", OUT_PATH)


def main():
    preview = "--preview" in sys.argv
    render(preview)


if __name__ == "__main__":
    main()
