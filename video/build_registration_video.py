#!/usr/bin/env python3
"""Registration-process explainer, using the same Miri film template."""

from __future__ import annotations

import asyncio
import math
import subprocess
import sys
from pathlib import Path

import edge_tts
import numpy as np
from PIL import Image, ImageDraw

import build_miri_video as base

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
BUILD = ROOT / "build-registration"
OUT_PATH = Path("/opt/cursor/artifacts/miri-registration-process.mp4")
REQUEST_PATH = ASSETS / "profile-create-request.png"
RESPONSE_PATH = ASSETS / "profile-create-response.png"

W, H = base.W, base.H
FPS = base.FPS
SR = base.SR
VOICE = base.VOICE
PITCH = base.PITCH

GAP = 0.14
END_HOLD = 1.05

BEATS = [
    {
        "id": "intro",
        "voice": "Registration uses three API calls. Profile Create, Account Create, and Create Activation Record.",
        "kicker": "REGISTRATION",
        "title": "Three API calls.",
        "visual": "intro",
    },
    {
        "id": "model",
        "voice": "A profile is a real user of the application you are integrating with Miri. An account is that user's device or app, and accounts are created under the profile. For an offline one-time password on both an iPhone and an Android phone, create two accounts under the same profile, and activate both devices.",
        "kicker": "PROFILE  AND  ACCOUNT",
        "title": "One user.\nMany devices.",
        "visual": "model",
    },
    {
        "id": "order",
        "voice": "Create the profile first. Then create an account for each device. Then create an activation record for the account you want to activate.",
        "kicker": "CALL ORDER",
        "title": "In this order.",
        "visual": "order",
    },
    {
        "id": "request",
        "voice": "Profile Create is a POST to base URL, MIS URL, slash profile slash create. Issuer and Profile Expire Date are the only mandatory parameters. Issuer is the issuer ID. Profile Expire Date is the profile expiry, and every account under that profile shares the same date. Lookup Data 1 and 2 are optional identifiers used when a Miri Token is validated. Response Data 1, 2, and 3 are optional values returned after a successful Miri number validation. Every other field is optional.",
        "kicker": "01   PROFILE CREATE",
        "title": "Profile Create",
        "visual": "request",
    },
    {
        "id": "response",
        "voice": "Store the Profile ID from the response against your user record. Later calls need it. A status code of 0, and a status message of Success, mean the profile was created. Any other status code is an error, and the status message describes that error.",
        "kicker": "01   PROFILE CREATE",
        "title": "Save the Profile ID.",
        "visual": "response",
    },
    {
        "id": "account",
        "voice": "Account Create adds one device or app under that profile. Call it once for every device the user will activate.",
        "kicker": "02   ACCOUNT CREATE",
        "title": "Account Create",
        "visual": "account",
    },
    {
        "id": "activation",
        "voice": "Create Activation Record generates an activation code for a Miri account. The mobile app needs that code to activate the account. The code is one-time use, and it must be used within the validity time configured for the issuer.",
        "kicker": "03   ACTIVATION RECORD",
        "title": "Activation code.",
        "visual": "activation",
    },
    {
        "id": "outro",
        "voice": "Profile, then account, then a one-time activation code.",
        "kicker": "REGISTRATION",
        "title": "Three calls.\nOne user live.",
        "visual": "outro",
    },
]


def beat_schedule(durations):
    timeline = []
    t = 0.0
    for beat, dur in zip(BEATS, durations):
        timeline.append((beat, t, t + dur))
        t += dur + GAP
    total = t - GAP + END_HOLD
    return timeline, total


def active_beat(timeline, t):
    for i, (beat, a, b) in enumerate(timeline):
        if a <= t < b:
            return beat, t - a, b - a
        if i + 1 < len(timeline) and b <= t < timeline[i + 1][1]:
            return beat, (b - a) + (t - b), (b - a)
    beat, a, b = timeline[-1]
    return beat, (b - a) + (t - b), (b - a)


def load_shots():
    request = Image.open(REQUEST_PATH).convert("RGB")
    response = Image.open(RESPONSE_PATH).convert("RGB")
    width = 1200

    def fit(img):
        h = int(img.height * width / img.width)
        return img.resize((width, h), Image.Resampling.LANCZOS)

    return {"request": fit(request), "response": fit(response), "width": width}


def blit_shot(canvas, shot, x, y, view_h, pan):
    w, sh = shot.size
    if sh <= view_h:
        crop = shot
        top = y + (view_h - sh) // 2
        view_h = sh
    else:
        off = int((sh - view_h) * pan)
        crop = shot.crop((0, off, w, off + view_h))
        top = y
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, crop.width - 1, crop.height - 1), radius=14, fill=255)
    canvas.paste(crop, (x, top), mask)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    base.draw_brackets(d, x - 8, top - 8, w + 16, view_h + 16, base.CYAN, length=26, thick=3)
    canvas.paste(overlay, (0, 0), overlay)
    return top, top + view_h


def draw_intro(draw, y, p):
    items = [
        ("01", "Profile Create", "The real user", base.CYAN),
        ("02", "Account Create", "A device or app", base.GOLD),
        ("03", "Activation Record", "One-time code", base.GREEN),
    ]
    top = max(y + 36, 430)
    cw, ch, gap = 380, 250, 18
    for i, (num, name, sub, col) in enumerate(items):
        lp = base.stagger(p, i, 3)
        x = 72 + i * (cw + gap)
        base.rounded_panel(draw, (x, top, x + cw, top + ch), 18, (7, 14, 28, int(215 * lp)), base.rgba(col, int(210 * lp)), 2)
        draw.text((x + 24, top + 28), num, font=base.F["huge"], fill=base.rgba(col, int(255 * lp)))
        draw.text((x + 24, top + 140), name, font=base.F["semi"], fill=base.rgba(base.WHITE, int(255 * lp)))
        draw.text((x + 24, top + 178), sub, font=base.F["small"], fill=base.rgba(base.MUTED, int(255 * lp)))


def draw_model(draw, y, p):
    top = y + 16
    lp = base.stagger(p, 0, 3)
    base.rounded_panel(draw, (72, top, 560, top + 168), 16, (7, 16, 30, int(220 * lp)), base.rgba(base.CYAN, int(200 * lp)), 2)
    draw.text((96, top + 22), "PROFILE", font=base.F["mono_sm"], fill=base.rgba(base.CYAN, int(255 * lp)))
    draw.text((96, top + 56), "A real user", font=base.F["card_name"], fill=base.rgba(base.WHITE, int(255 * lp)))
    draw.text((96, top + 100), "Of the integrating application", font=base.F["small"], fill=base.rgba(base.MUTED, int(255 * lp)))

    rp = base.stagger(p, 1, 3)
    base.rounded_panel(draw, (590, top, 1240, top + 168), 16, (7, 16, 30, int(220 * rp)), base.rgba(base.GOLD, int(200 * rp)), 2)
    draw.text((614, top + 22), "ACCOUNT", font=base.F["mono_sm"], fill=base.rgba(base.GOLD, int(255 * rp)))
    draw.text((614, top + 56), "A device or app", font=base.F["card_name"], fill=base.rgba(base.WHITE, int(255 * rp)))
    draw.text((614, top + 100), "Created under that user profile", font=base.F["small"], fill=base.rgba(base.MUTED, int(255 * rp)))

    devices = [("iPhone", "Account 1"), ("Android", "Account 2")]
    x = 72
    yy = top + 210
    draw.text((72, yy), "SAME PROFILE", font=base.F["mono_xs"], fill=base.rgba(base.CYAN, int(255 * min(1, p * 1.4))))
    x = 250
    for i, (name, sub) in enumerate(devices):
        ep = base.stagger(p, i + 1.4, 4)
        base.rounded_panel(draw, (x, yy - 8, x + 280, yy + 78), 14, (8, 18, 32, int(220 * ep)), base.rgba(base.GREEN, int(180 * ep)), 2)
        draw.text((x + 18, yy + 6), name, font=base.F["semi"], fill=base.rgba(base.WHITE, int(255 * ep)))
        draw.text((x + 18, yy + 38), sub + "  ·  activate", font=base.F["small"], fill=base.rgba(base.MUTED, int(255 * ep)))
        x += 304
    note_a = int(255 * base.ease(max(0, (p - 0.55) / 0.35)))
    draw.text((72, yy + 100), "Two devices means two accounts. Activate both.", font=base.F["body"], fill=base.rgba(base.WHITE, note_a))


def draw_order(draw, y, p):
    labels = ["PROFILE\nCREATE", "ACCOUNT\nCREATE", "ACTIVATION\nRECORD"]
    subs = ["The user", "Each device", "One-time code"]
    cols = [base.CYAN, base.GOLD, base.GREEN]
    base.flow_row(draw, ["PROFILE CREATE", "ACCOUNT CREATE", "ACTIVATION RECORD"], subs, y + 48, p, base.CYAN)
    # Recolor is handled inside flow_row with one accent. The labels above are unused
    # except as documentation of the sequence; flow_row draws the cards.
    del labels, cols


def draw_account(draw, y, p):
    draw.text((72, y + 6), "One account per device or app, under the profile.", font=base.F["body"], fill=base.rgba(base.MUTED, int(255 * min(1, p * 1.4))))
    base.flow_row(
        draw,
        ["PROFILE", "ACCOUNT", "DEVICE"],
        ["Profile ID", "Device or app", "Ready to activate"],
        y + 70,
        p,
        base.GOLD,
    )
    draw.text(
        (72, y + 210),
        "Repeat Account Create for every device the user will activate.",
        font=base.F["semi"],
        fill=base.rgba(base.WHITE, int(255 * base.ease(max(0, (p - 0.4) / 0.4)))),
    )


def draw_activation(draw, y, p):
    draw.text((72, y + 6), "Required before the account can be activated in the mobile app.", font=base.F["body"], fill=base.rgba(base.MUTED, int(255 * min(1, p * 1.4))))
    top = y + 70
    lp = base.ease(min(1, p * 1.3))
    base.rounded_panel(draw, (72, top, 760, top + 210), 18, (7, 18, 28, int(225 * lp)), base.rgba(base.GREEN, int(200 * lp)), 2)
    draw.text((96, top + 24), "ACTIVATION CODE", font=base.F["mono_sm"], fill=base.rgba(base.GREEN, int(255 * lp)))
    draw.text((96, top + 68), "One-time use", font=base.F["card_name"], fill=base.rgba(base.WHITE, int(255 * lp)))
    draw.text((96, top + 116), "Use it within the validity time", font=base.F["body_m"], fill=base.rgba(base.WHITE, int(240 * lp)))
    draw.text((96, top + 154), "configured for the issuer.", font=base.F["body_m"], fill=base.rgba(base.WHITE, int(240 * lp)))
    chips = [("ONE-TIME", base.GOLD), ("MOBILE APP", base.CYAN), ("ISSUER VALIDITY", base.GREEN)]
    x = 800
    for i, (label, col) in enumerate(chips):
        cp = base.stagger(p, i + 0.6, 4)
        base.rounded_panel(draw, (x, top + i * 72, 1240, top + 58 + i * 72), 12, (8, 18, 30, int(210 * cp)), base.rgba(col, int(180 * cp)), 2)
        draw.text((x + 18, top + 16 + i * 72), label, font=base.F["semi_sm"], fill=base.rgba(base.WHITE, int(255 * cp)))


def draw_outro(draw, y, p):
    items = [
        ("01", "Profile Create", "Store ProfileId"),
        ("02", "Account Create", "One per device"),
        ("03", "Activation Record", "One-time code"),
    ]
    x = 72
    yy = y + 24
    for i, (num, name, sub) in enumerate(items):
        lp = base.stagger(p, i, 3)
        col = [base.CYAN, base.GOLD, base.GREEN][i]
        base.rounded_panel(draw, (x, yy, x + 380, yy + 150), 16, (7, 16, 30, int(220 * lp)), base.rgba(col, int(200 * lp)), 2)
        draw.text((x + 20, yy + 18), num, font=base.F["mono_sm"], fill=base.rgba(col, int(255 * lp)))
        draw.text((x + 20, yy + 52), name, font=base.F["semi"], fill=base.rgba(base.WHITE, int(255 * lp)))
        draw.text((x + 20, yy + 92), sub, font=base.F["small"], fill=base.rgba(base.MUTED, int(255 * lp)))
        x += 400


def legend(draw, items, y, p, start=0.0):
    x = 72
    for i, (text, col) in enumerate(items):
        lp = base.ease(max(0.0, min(1.0, (p - start - i * 0.08) / 0.25)))
        if lp <= 0.02:
            continue
        box = base.pill(draw, (x, y), text, base.F["mono_xs"], base.rgba(base.WHITE, int(255 * lp)), (8, 18, 32, int(220 * lp)), base.rgba(col, int(190 * lp)))
        x = box[2] + 10
        if x > 1180:
            break


def render_content(draw, beat, local_t, dur, film_p):
    p = base.ease(min(1.0, local_t / max(0.9, dur * 0.45)))
    fade = base.ease(min(1.0, local_t / 0.28))
    kind = beat["visual"]
    # Screenshot scenes keep the title compact so the capture stays readable.
    if kind in ("request", "response"):
        base.header(draw, film_p)
        a = int(255 * fade)
        draw.text((72, 118), beat["kicker"], font=base.F["kicker"], fill=base.rgba(base.CYAN, a))
        draw.text((72, 144), beat["title"], font=base.F["title_sm"], fill=base.rgba(base.WHITE, a))
        if kind == "request":
            legend(
                draw,
                [("POST", base.CYAN), ("ISSUER", base.GOLD), ("PROFILE EXPIRE DATE", base.GOLD), ("OTHER FIELDS OPTIONAL", base.GREEN)],
                214,
                p,
            )
        else:
            legend(
                draw,
                [("STORE PROFILE ID", base.CYAN), ("STATUS CODE  0", base.GREEN), ("SUCCESS", base.GREEN)],
                214,
                p,
            )
        return
    base.header(draw, film_p)
    y = base.kicker_title(draw, beat["kicker"], beat["title"], fade)
    if kind == "intro":
        draw_intro(draw, y, p)
    elif kind == "model":
        draw_model(draw, y, p)
    elif kind == "order":
        draw_order(draw, y, p)
    elif kind == "account":
        draw_account(draw, y, p)
    elif kind == "activation":
        draw_activation(draw, y, p)
    elif kind == "outro":
        draw_outro(draw, y, p)


def shot_pan(kind, local_t, dur):
    if kind != "response":
        return 0.0
    u = 0 if dur <= 0 else local_t / dur
    if u < 0.22:
        return 0.0
    if u > 0.68:
        return 1.0
    return base.ease((u - 0.22) / 0.46)


def frame_at(bg, robot, mask, shots, t, beat, local_t, dur, film_p):
    frame = base.crop_bg(bg, t).convert("RGBA")
    fx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    base.particles(ImageDraw.Draw(fx), t)
    frame = Image.alpha_composite(frame, fx)
    canvas = Image.new("RGBA", (W, H))
    canvas.paste(frame, (0, 0))
    base.paste_robot(canvas, robot, mask, t)
    kind = beat["visual"]
    if kind in ("request", "response"):
        shot = shots[kind]
        view_h = 760 if kind == "response" else min(700, shot.height)
        blit_shot(canvas, shot, 56, 268, view_h, shot_pan(kind, local_t, dur))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    render_content(ImageDraw.Draw(overlay), beat, local_t, dur, film_p)
    if local_t < 0.22:
        factor = base.ease(local_t / 0.22)
        overlay.putalpha(overlay.getchannel("A").point(lambda v: int(v * factor)))
    canvas = Image.alpha_composite(canvas, overlay)
    return canvas.convert("RGB")


async def synthesize(rate: str):
    BUILD.mkdir(parents=True, exist_ok=True)
    paths = []
    for beat in BEATS:
        path = BUILD / f"{beat['id']}.mp3"
        comm = edge_tts.Communicate(beat["voice"], VOICE, rate=rate, pitch=PITCH)
        await comm.save(str(path))
        paths.append(path)
    return paths


def assemble_audio(mp3s):
    wavs = []
    for src in mp3s:
        dst = src.with_suffix(".wav")
        base.mp3_to_wav(src, dst)
        wavs.append(dst)
    clips = [base.tighten_clip(base.read_wav(path)) for path in wavs]
    durations = [len(clip) / SR for clip in clips]
    timeline, total = beat_schedule(durations)
    n = int(math.ceil(total * SR))
    voice = np.zeros(n, np.float32)
    for clip, (beat, a, b) in zip(clips, timeline):
        start = int(round(a * SR))
        end = min(start + len(clip), n)
        voice[start:end] += clip[: end - start]
    tt = np.arange(n) / SR
    drone = (
        0.035 * np.sin(2 * np.pi * 55 * tt)
        + 0.018 * np.sin(2 * np.pi * 82.4 * tt)
        + 0.012 * np.sin(2 * np.pi * 110 * tt)
    )
    drone *= 0.65 + 0.35 * np.sin(2 * np.pi * 0.08 * tt)
    mix = voice * 0.92 + drone
    fin = int(0.12 * SR)
    fout = int(0.45 * SR)
    if n > fin + fout:
        mix[:fin] *= np.linspace(0, 1, fin)
        mix[-fout:] *= np.linspace(1, 0, fout)
    peak = float(np.max(np.abs(mix)) + 1e-6)
    mix *= min(1.0, 0.92 / peak)
    out = BUILD / "mix.wav"
    base.write_wav(out, mix)
    return out, timeline, total, durations


def render(preview: bool):
    BUILD.mkdir(parents=True, exist_ok=True)
    rate = "+0%"
    audio_path = timeline = total = None
    for attempt in range(3):
        mp3s = asyncio.run(synthesize(rate))
        audio_path, timeline, total, durations = assemble_audio(mp3s)
        print(f"speech {sum(durations):.2f}s  total {total:.2f}s  rate {rate}", flush=True)
        if 70 <= total <= 130 or attempt == 2:
            break
        target = 105.0
        current = int(rate.strip("%+") or "0")
        faster = int(round((total / target - 1.0) * 100 + current))
        rate = f"+{min(16, max(0, faster))}%"
        print(f"retiming at {rate}", flush=True)
    bg, robot, mask = base.load_bases()
    shots = load_shots()
    nframes = int(round(total * FPS))
    print(f"frames {nframes}  duration {total:.2f}s  shots {[shots[k].size for k in ('request', 'response')]}", flush=True)
    if preview:
        prev = BUILD / "preview"
        prev.mkdir(exist_ok=True)
        for beat, a, b in timeline:
            for mark, name in ((0.18, "a"), (0.55, "b"), (0.88, "c")):
                t = a + (b - a) * mark
                img = frame_at(bg, robot, mask, shots, t, beat, t - a, b - a, t / total)
                img.save(prev / f"{beat['id']}-{name}.jpg", quality=88)
            print("preview", beat["id"], flush=True)
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
            beat, local_t, dur = active_beat(timeline, t)
            img = frame_at(bg, robot, mask, shots, t, beat, local_t, dur, min(1, t / total))
            proc.stdin.write(img.tobytes())
            if i % 150 == 0:
                print(f"frame {i}/{nframes}  {beat['id']}", flush=True)
    finally:
        proc.stdin.close()
        code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg exited {code}")
    print("wrote", OUT_PATH, flush=True)


def main():
    render("--preview" in sys.argv)


if __name__ == "__main__":
    main()
