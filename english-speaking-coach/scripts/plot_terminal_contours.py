#!/usr/bin/env python3
"""Render a small-multiples SVG of sentence-final pitch contours.

One panel per reference sentence; each panel overlays the learner's recording with
a native reference reading. This is the clearest way to show an intonation problem:
"the native voice falls at the full stop, yours rises" is obvious in a picture and
easy to miss in a table of numbers.

Usage:
  python plot_terminal_contours.py \
    --ref-md output/xxx-formal.md \
    --series "本次=recordings/a.m4a" \
    --series "上次=draft/b.m4a" \
    --series "Daniel=output/xxx-formal-reading.m4a" \
    --out /tmp/contours.svg [--json /tmp/contours.json]

Each --series is LABEL=PATH (repeatable, max 3). The first series is drawn thickest.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import analyze_reading as ar  # noqa: E402

PALETTE = ["#D85A30", "#185FA5", "#1D9E75"]
PW, PH, GAPX, GAPY = 186, 122, 14, 36
X0, Y0 = 40, 44
PL, PT, PR, PB = 30, 46, 176, 106
SMIN, SMAX = -12.0, 12.0


def contours_for(audio: str, md: str, cache_dir: str | None):
    x, sr = ar.decode_audio(audio)
    times, f0, rms = ar.estimate_f0(x, sr)
    f0 = ar._clean_f0(f0)
    voiced = f0[np.isfinite(f0)]
    med = float(np.median(voiced)) if voiced.size else 0.0

    asr = ar.transcribe_cached(x, sr, "small.en", initial_prompt=ar.DEFAULT_DOMAIN_PROMPT,
                               audio_path=audio, cache_dir=cache_dir)
    ref_text = ar.extract_rewritten_text(md)
    toks = ar.tokenize(ref_text)
    sents = ar.split_sentences(ref_text)
    al = ar.align(toks, asr["words"])
    r2a = dict(al.pairs)
    words = asr["words"]

    out = []
    cursor = 0
    for sent in sents:
        n = len(ar.tokenize(sent))
        idxs = [r2a[j] for j in range(cursor, cursor + n) if j in r2a]
        cursor += n
        if not idxs:
            out.append({"word": "", "pts": [], "verdict": None, "delta_st": None})
            continue
        seg = words[min(idxs):max(idxs) + 1]
        last = seg[-1]
        a = max(last["start"], last["end"] - 0.9)
        tc = ar.terminal_contour(times, f0, a, last["end"], med)
        m = (times >= a) & (times <= last["end"]) & np.isfinite(f0)
        pts = []
        if m.sum() >= 8:
            t_last = float(times[m][-1])
            sel = m & (times >= t_last - 0.5)
            pts = [[round(float(t - t_last), 3), round(float(12 * np.log2(f / med)), 2)]
                   for t, f in zip(times[sel], f0[sel])]
        out.append({"word": last["word"], "pts": pts,
                    "verdict": (tc or {}).get("verdict"),
                    "delta_st": (tc or {}).get("delta_st")})
    return out


def build_svg(series: list[dict]) -> str:
    n_sent = max(len(s["sentences"]) for s in series)

    def px(t):
        return PL + (t + 0.5) / 0.5 * (PR - PL)

    def py(st):
        st = max(SMIN, min(SMAX, st))
        return PB - (st - SMIN) / (SMAX - SMIN) * (PB - PT)

    parts = []
    for i in range(n_sent):
        col, row = i % 3, i // 3
        ox, oy = X0 + col * (PW + GAPX), Y0 + row * (PH + GAPY)
        word = ""
        for s in series:
            if i < len(s["sentences"]) and s["sentences"][i]["word"]:
                word = s["sentences"][i]["word"]
                break
        g = [f'<g transform="translate({ox},{oy})">',
             f'<rect x="0" y="0" width="{PW}" height="{PH}" rx="10" fill="#FFFFFF" stroke="#D3D1C7" stroke-width="0.8"/>',
             f'<text x="12" y="18" font-size="12.5" fill="#2C2C2A" font-weight="600">句 {i+1} · {word}</text>']
        for st, lab in ((12, "+12"), (0, "0"), (-12, "−12")):
            yy = py(st)
            dash = ' stroke-dasharray="3 3"' if st == 0 else ""
            g.append(f'<line x1="{PL}" y1="{yy:.1f}" x2="{PR}" y2="{yy:.1f}" stroke="#E4E2DB" stroke-width="0.8"{dash}/>')
            g.append(f'<text x="{PL-5}" y="{yy+3.5:.1f}" font-size="9.5" fill="#888780" text-anchor="end">{lab}</text>')

        any_pts = False
        for k, s in enumerate(series):
            sent = s["sentences"][i] if i < len(s["sentences"]) else None
            if not sent or len(sent["pts"]) < 2:
                continue
            any_pts = True
            poly = " ".join(f"{px(t):.1f},{py(st):.1f}" for t, st in sent["pts"])
            w = 2.0 if k == 0 else 1.5
            g.append(f'<polyline points="{poly}" fill="none" stroke="{s["color"]}" '
                     f'stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"/>')
            t, st = sent["pts"][-1]
            g.append(f'<circle cx="{px(t):.1f}" cy="{py(st):.1f}" r="2.6" fill="{s["color"]}"/>')
        if not any_pts:
            g.append(f'<text x="{(PL+PR)/2:.0f}" y="{(PT+PB)/2+4:.0f}" font-size="11" '
                     f'fill="#A8A69E" text-anchor="middle">数据不足，无法判定</text>')

        # verdict badges, stacked at the top-right of the panel
        for k, s in enumerate(series):
            sent = s["sentences"][i] if i < len(s["sentences"]) else None
            if not sent or not sent["verdict"]:
                continue
            color = {"下降": "#1D9E75", "上升": "#D85A30", "基本持平": "#BA7517"}.get(sent["verdict"], "#888780")
            g.append(f'<text x="{PW-12}" y="{13 + k*12}" font-size="10.5" fill="{color}" '
                     f'text-anchor="end">{s["label"]} {sent["verdict"]} {sent["delta_st"]:+.1f}</text>')
        g.append("</g>")
        parts.append("".join(g))

    height = Y0 + ((n_sent - 1) // 3 + 1) * PH + GAPY + 8
    legend = ['<g transform="translate(40,14)">']
    x = 0
    for k, s in enumerate(series):
        legend.append(f'<line x1="{x}" y1="0" x2="{x+18}" y2="0" stroke="{s["color"]}" stroke-width="2.4"/>')
        legend.append(f'<text x="{x+24}" y="4" font-size="12" fill="#5F5E5A">{s["label"]}</text>')
        x += 32 + 10 * len(s["label"])
    legend.append(f'<text x="{x+16}" y="4" font-size="11.5" fill="#888780">'
                  f'横轴：句末最后 0.5 秒（右端＝句号）</text>')
    legend.append("</g>")

    return (f'<svg viewBox="0 0 680 {height}" width="100%" role="img" '
            f'aria-label="各句句末音高曲线对比">\n' + "".join(legend) + "\n" + "".join(parts) + "\n</svg>")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-md", required=True)
    ap.add_argument("--series", action="append", required=True, help="LABEL=PATH")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json")
    ap.add_argument("--asr-cache", default=os.path.expanduser("~/.cache/english-speaking-coach/asr"))
    args = ap.parse_args()

    series = []
    for k, spec in enumerate(args.series[:3]):
        label, path = spec.split("=", 1)
        series.append({"label": label, "color": PALETTE[k],
                       "sentences": contours_for(path, args.ref_md, args.asr_cache)})

    svg = build_svg(series)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(series, f, ensure_ascii=False, indent=1)
    print(f"SVG -> {args.out}  ({len(svg)} bytes)")
    for s in series:
        v = [x["verdict"] for x in s["sentences"] if x["verdict"]]
        print(f"  {s['label']}: 可判定 {len(v)}/{len(s['sentences'])}，下降 {sum(1 for x in v if x=='下降')}")


if __name__ == "__main__":
    main()
