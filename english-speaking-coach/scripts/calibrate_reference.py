#!/usr/bin/env python3
"""Calibration harness: run the prosody + alignment pipeline over the reference
TTS readings in output/ and report how the measurements behave on known-good
native speech.

Why: every metric in analyze_reading.py is an estimate. Before trusting a number
on a learner's recording, check that it behaves correctly on a professional
native reading. Statement-final pitch, for instance, must come out as a fall.

Usage:
  python calibrate_reference.py --dir /path/to/output [--limit N] [--json out.json]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import analyze_reading as ar  # noqa: E402


def run_one(audio: str, md: str, model: str, cache_dir: str | None = None) -> dict:
    x, sr = ar.decode_audio(audio)
    times, f0, rms = ar.estimate_f0(x, sr)
    f0 = ar._clean_f0(f0)
    voiced = f0[np.isfinite(f0)]
    med = float(np.median(voiced)) if voiced.size else 0.0

    asr = ar.transcribe_cached(x, sr, model, initial_prompt=ar.DEFAULT_DOMAIN_PROMPT,
                               audio_path=audio, cache_dir=cache_dir)
    ref_text = ar.extract_rewritten_text(md)
    ref_tokens = ar.tokenize(ref_text)
    sentences = ar.split_sentences(ref_text)
    al = ar.align(ref_tokens, asr["words"])
    sp = ar.sentence_prosody(sentences, ref_tokens, asr, al.pairs, times, f0, rms, med)

    ps = ar.pause_stats(asr["words"], len(x) / sr)
    return {
        "audio": os.path.basename(audio),
        "model_ok": getattr(asr, "get", lambda *_: None) and True,
        "duration_s": round(len(x) / sr, 2),
        "overall_wpm": round(len(asr["words"]) / max(len(x) / sr, 1e-6) * 60, 1),
        "silence_share": round(ps["total_silence"] / max(ps["total_duration"], 1e-6) * 100, 1),
        "median_f0": round(med, 1),
        "range_st": ar.robust_range_st(f0, med),
        "std_st": round(float(ar.to_semitones(voiced, med).std()), 2) if voiced.size else None,
        "match_rate": round(len(al.pairs) / max(len(ref_tokens), 1), 3),
        "sentences": [
            {
                "text": s["sentence"],
                "wpm": s["wpm"],
                "final_word": s.get("final_word"),
                "verdict": (s.get("final_contour") or {}).get("verdict"),
                "delta_st": (s.get("final_contour") or {}).get("delta_st"),
                "frames": (s.get("final_contour") or {}).get("frames"),
            }
            for s in sp
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="/Users/lvchajason/Documents/workspace/notes/output")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--asr-cache", default=os.path.expanduser("~/.cache/english-speaking-coach/asr"))
    ap.add_argument("--json")
    args = ap.parse_args()

    audios = sorted(glob.glob(os.path.join(args.dir, "*-reading.m4a")))
    if args.limit:
        audios = audios[: args.limit]

    results = []
    for audio in audios:
        md = audio.replace("-reading.m4a", ".md")
        if not os.path.exists(md):
            print(f"skip (no md): {os.path.basename(audio)}")
            continue
        r = run_one(audio, md, args.model, args.asr_cache)
        results.append(r)

        verdicts = [s["verdict"] for s in r["sentences"] if s["verdict"]]
        falls = sum(1 for v in verdicts if v == "下降")
        print(f"\n{os.path.basename(audio)}")
        print(f"  {r['duration_s']}s | {r['overall_wpm']} wpm | 静音 {r['silence_share']}% "
              f"| F0 {r['median_f0']}Hz | 音域 {r['range_st']}st | 对齐 {r['match_rate']:.0%}")
        print(f"  尾调判定: {falls}/{len(verdicts)} 句为下降")
        for s in r["sentences"]:
            print(f"    {str(s['verdict']):<6} {str(s['delta_st']):>7}st "
                  f"{str(s['frames']):>3}帧  末词={str(s['final_word']):<14} {s['text'][:44]}")

    allv = [s["verdict"] for r in results for s in r["sentences"] if s["verdict"]]
    judgeable = [s for r in results for s in r["sentences"] if s["verdict"]]
    total_sent = sum(len(r["sentences"]) for r in results)
    falls = sum(1 for v in allv if v == "下降")
    print("\n================ 汇总 ================")
    print(f"文件 {len(results)} 个 | 句子 {total_sent} 个 | 可判定 {len(allv)} 个")
    print(f"判定为「下降」的比例: {falls}/{len(allv)} = {falls/max(len(allv),1):.0%}")
    print("（母语者朗读陈述句应绝大多数为下降；偏低说明该指标不可靠）")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"JSON -> {args.json}")


if __name__ == "__main__":
    main()
