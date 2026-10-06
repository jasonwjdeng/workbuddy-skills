#!/usr/bin/env python3
"""Read-aloud recording analyzer: ASR + reference alignment + prosody metrics.

This script produces MEASUREMENTS ONLY. Scoring and teaching feedback are the
job of the model reading the JSON output.

Usage:
  python analyze_reading.py --audio rec.m4a --ref-md output/xxx-formal.md --json out.json
  python analyze_reading.py --audio rec.m4a --ref-text "I am a backend engineer." --json out.json
  python analyze_reading.py --audio rec.m4a --json out.json        # no reference script

Reference sources:
  --ref-md  : a project rewrite file; the "## Rewritten Text" section is extracted.
  --ref-text: raw reference text.
  If neither is given, the ASR transcript itself is used as the reference (only
  fluency / prosody metrics are meaningful in that case).

Requires: openai-whisper + torch + numpy (see SKILL.md), at:
  /Users/lvchajason/.workbuddy/binaries/python/envs/torch312/bin/python
Audio decoding uses the built-in macOS `afconvert` and the waveform is fed to
whisper as a numpy array, so neither ffmpeg nor the `av` package is needed.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass, field

import numpy as np

TARGET_SR = 16000

# Biasing the decoder with the *vocabulary* (never the full script) sharply reduces
# false "mispronunciation" flags on proper nouns and technical terms. It does not
# reveal the sentence structure, so genuine errors elsewhere still surface.
DEFAULT_DOMAIN_PROMPT = (
    "A software engineer describing a backend application. Vocabulary: Kubernetes cluster, "
    "on-premises, Java, Spring Boot, application framework, Docker image, Azure DevOps pipeline, "
    "Helm, PostgreSQL, primary-secondary configuration, microservices, Helm, Grafana, Prometheus, "
    "Micrometer, Actuator, Airflow, GitHub, VPN connectivity, DNS resolution, wealth management "
    "system, retail banking, Azure, Docker, Jenkins, Kafka, Redis."
)

# ---------------------------------------------------------------- audio I/O


def decode_audio(path: str) -> tuple[np.ndarray, int]:
    """Decode any audio file macOS can read into mono float32 @ TARGET_SR."""
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "decoded.wav")
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", f"LEI16@{TARGET_SR}", "-c", "1", path, wav],
            check=True,
            capture_output=True,
        )
        with wave.open(wav, "rb") as f:
            sr = f.getframerate()
            raw = f.readframes(f.getnframes())
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if x.size == 0:
        raise SystemExit(f"decoded empty audio: {path}")
    return x, sr


# ---------------------------------------------------------------- ASR


_MODEL_CACHE: dict = {}
WHISPER_DOWNLOAD_ROOT = os.path.expanduser("~/.cache/whisper")


def transcribe(x: np.ndarray, sr: int, model_size: str = "base.en", language: str = "en",
               initial_prompt: str | None = None) -> dict:
    """Transcribe a float32 mono @16k waveform with word-level timestamps."""
    import whisper

    if model_size not in _MODEL_CACHE:
        _MODEL_CACHE[model_size] = whisper.load_model(model_size, download_root=WHISPER_DOWNLOAD_ROOT)
    model = _MODEL_CACHE[model_size]

    assert sr == TARGET_SR, f"whisper needs {TARGET_SR} Hz mono, got {sr}"
    result = model.transcribe(
        x.astype(np.float32),
        language=language,
        word_timestamps=True,
        verbose=False,
        condition_on_previous_text=False,
        fp16=False,
        initial_prompt=initial_prompt,
    )

    words: list[dict] = []
    segs: list[dict] = []
    for s in result.get("segments", []):
        seg_words = []
        for w in s.get("words", []) or []:
            item = {
                "word": str(w.get("word", "")).strip(),
                "start": round(float(w.get("start", 0.0)), 3),
                "end": round(float(w.get("end", 0.0)), 3),
                "prob": round(float(w.get("probability", 0.0) or 0.0), 3),
            }
            if not normalize(item["word"]):
                continue
            words.append(item)
            seg_words.append(item)
        segs.append(
            {
                "start": round(float(s.get("start", 0.0)), 3),
                "end": round(float(s.get("end", 0.0)), 3),
                "text": str(s.get("text", "")).strip(),
                "avg_logprob": round(float(s.get("avg_logprob", 0.0) or 0.0), 3),
                "no_speech_prob": round(float(s.get("no_speech_prob", 0.0) or 0.0), 3),
                "words": seg_words,
            }
        )
    return {"words": words, "segments": segs, "language_probability": None}


def transcribe_cached(x: np.ndarray, sr: int, model_size: str, language: str = "en",
                      initial_prompt: str | None = None, audio_path: str | None = None,
                      cache_dir: str | None = None) -> dict:
    """Transcribe, reusing a cached result when the same audio+model+prompt was seen.

    Re-running whisper costs ~40 s per minute of audio, which makes iterating on the
    downstream metrics painful. The cache key covers the file identity (size + mtime)
    so a re-recorded file at the same path is never served stale transcriptions.
    """
    if not cache_dir or not audio_path:
        return transcribe(x, sr, model_size, language, initial_prompt)

    st = os.stat(audio_path)
    key_raw = f"{os.path.abspath(audio_path)}|{st.st_size}|{int(st.st_mtime)}|{model_size}|{language}|{initial_prompt or ''}"
    key = hashlib.sha1(key_raw.encode("utf-8")).hexdigest()[:16]
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("words"):
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    result = transcribe(x, sr, model_size, language, initial_prompt)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
    except OSError:
        pass
    return result


# ---------------------------------------------------------------- helpers


def normalize(word: str) -> str:
    """Lowercase, strip punctuation, and drop hyphens (on-premises == onpremises)."""
    w = word.lower().strip()
    w = w.replace("\u2019", "'").replace("\u2018", "'").replace("\u2014", " ").replace("\u2013", " ")
    w = re.sub(r"^[^a-z0-9']+", "", w)
    w = re.sub(r"[^a-z0-9']+$", "", w)
    w = w.replace("-", "")
    return w


# Technical vocabulary the small English ASR models commonly mis-hear. A mismatch
# on one of these is NOT by itself evidence of a pronunciation problem, so the
# report tags them for manual review instead of counting them as errors.
DOMAIN_TERMS = {
    "kubernetes", "postgresql", "postgres", "grafana", "prometheus", "micrometer",
    "actuator", "airflow", "github", "java", "docker", "helm", "azure", "devops",
    "springboot", "spring", "boot", "vpn", "dns", "api", "http", "https", "url",
    "microservice", "microservices", "onpremises", "cluster", "pipeline", "endpoint",
    "dashboard", "repository", "backend", "frontend", "runtime", "namespace",
    "tomcat", "nginx", "kafka", "redis", "pgsql", "sql", "json", "yaml", "token",
}


def tokenize(text: str) -> list[str]:
    text = re.sub(r"\u2014|\u2013", " ", text)
    return [t for t in (normalize(w) for w in re.split(r"\s+", text.strip())) if t]


def strip_markdown(text: str) -> str:
    """Remove markdown scaffolding so it never becomes a 'sentence'."""
    keep: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if re.fullmatch(r"[-*_=]{3,}", s):          # horizontal rule
            continue
        if s.startswith((">", "|", "#")):            # quote / table / heading
            continue
        keep.append(s)
    text = " ".join(keep)
    text = re.sub(r"\*\*|__|`", "", text)            # inline emphasis / code
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # links -> label
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def extract_rewritten_text(md_path: str) -> str:
    """Pull the body of the '## Rewritten Text' section out of a rewrite file."""
    with open(md_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    out: list[str] = []
    inside = False
    for ln in lines:
        if re.match(r"^#{1,6}\s*Rewritten Text\s*$", ln.strip(), re.I):
            inside = True
            continue
        if inside and re.match(r"^#{1,2}\s+\S", ln.strip()):
            break
        if inside:
            out.append(ln)
    text = "\n".join(out).strip()
    if not text:
        raise SystemExit(f"no '## Rewritten Text' section found in {md_path}")
    return strip_markdown(text)


# ---------------------------------------------------------------- pitch


def estimate_f0_ac(x: np.ndarray, sr: int, fmin: float = 60.0, fmax: float = 350.0,
                   frame: float = 0.04, hop: float = 0.01, thresh: float = 0.35):
    """Energy-gated autocorrelation F0 tracker (fallback when Praat is absent).

    Quiet recordings are the hard case: on low-energy frames the autocorrelation
    peak collapses to the shortest lag and reports a bogus F0 pinned at the search
    ceiling. Frames below the adaptive energy gate are therefore marked unvoiced,
    and any lag that lands on the ceiling is rejected outright.
    """
    fl = int(frame * sr)
    hl = max(1, int(hop * sr))
    minlag = max(2, int(sr / fmax))
    maxlag = min(fl - 2, int(sr / fmin))

    frames = [x[i:i + fl].astype(np.float64) for i in range(0, max(1, len(x) - fl), hl)]
    rmss = np.array([float(np.sqrt(((f - f.mean()) ** 2).mean())) for f in frames])
    times = np.array([(i * hl + fl / 2) / sr for i in range(len(frames))])

    # Adaptive gate: above the noise floor and a meaningful fraction of speech level.
    noise_floor = float(np.percentile(rmss, 15))
    speech_level = float(np.percentile(rmss, 90))
    gate = max(noise_floor * 3.0, speech_level * 0.12)

    f0s = np.full(len(frames), np.nan)
    for i, fr in enumerate(frames):
        if rmss[i] < gate:
            continue
        fr = fr - fr.mean()
        ac = np.correlate(fr, fr, mode="full")[fl - 1:]
        ac = ac / (ac[0] + 1e-12)
        seg = ac[minlag:maxlag + 1]
        if seg.size < 3:
            continue
        idx = int(np.argmax(seg))
        cand = np.where(seg >= max(thresh, 0.85 * seg[idx]))[0]
        if cand.size:
            idx = int(cand[0])
        if seg[idx] < thresh:
            continue
        lag = float(minlag + idx)
        if lag - minlag < 2:            # pinned to the F0 ceiling -> artifact
            continue
        if 0 < idx < seg.size - 1:
            y0, y1, y2 = seg[idx - 1], seg[idx], seg[idx + 1]
            denom = y0 - 2 * y1 + y2
            if abs(denom) > 1e-12:
                lag += 0.5 * (y0 - y2) / denom
        if lag > 0:
            f0s[i] = sr / lag
    return times, f0s, rmss


def estimate_f0_praat(x: np.ndarray, sr: int, step: float = 0.01,
                      floor: float = 70.0, ceiling: float = 400.0):
    """Praat's autocorrelation pitch tracker (Boersma). Preferred over the
    hand-rolled tracker: it is the de-facto standard and far less prone to
    locking onto a harmonic of the true F0."""
    import parselmouth

    snd = parselmouth.Sound(x.astype(np.float64), sampling_frequency=sr)
    pitch = snd.to_pitch_ac(
        time_step=step, pitch_floor=floor, pitch_ceiling=ceiling,
        voicing_threshold=0.45, silence_threshold=0.03,
        octave_cost=0.055, octave_jump_cost=0.35, voiced_unvoiced_cost=0.14,
    )
    f = pitch.selected_array["frequency"].astype(np.float64).copy()
    f[f == 0] = np.nan
    times = np.arange(len(f)) * step + step / 2
    return times, f


def estimate_f0(x: np.ndarray, sr: int, **kwargs):
    """F0 + frame energy on one shared time grid. Uses Praat when available."""
    try:
        times, f0 = estimate_f0_praat(x, sr)
    except ImportError:
        return estimate_f0_ac(x, sr)

    # Energy must live on the *same* grid, otherwise boolean masks computed from
    # `times` cannot index both arrays.
    fl = int(0.04 * sr)
    rms = np.zeros(len(times), dtype=np.float64)
    for i, t in enumerate(times):
        a = int(max(0, t * sr - fl / 2))
        seg = x[a:a + fl].astype(np.float64)
        seg = seg - seg.mean()
        if seg.size:
            rms[i] = float(np.sqrt((seg ** 2).mean()))
    return times, f0, rms


def _clean_f0(f0: np.ndarray, window: int = 45, jump_st: float = 5.0) -> np.ndarray:
    """Remove F0 tracking errors, then smooth.

    Both Praat and the local tracker occasionally lock onto a harmonic, reporting a
    value an octave (or a fifth-octave) off for anything from 1 to ~200 ms. Such
    spikes inflate a speaker's measured pitch range by several semitones and can
    flip a sentence-final contour verdict.

    A Hampel filter on the semitone scale removes them: a frame is dropped when it
    sits more than ``jump_st`` semitones from the median of a ``window`` (450 ms)
    neighbourhood. The window is deliberately long relative to the threshold — a
    genuine fast glide (say an 8-semitone terminal fall over 400 ms) stays within
    ±4 semitones of its own neighbourhood median and survives, while an isolated
    or short-lived harmonic lock does not.
    """
    out = f0.copy()
    v = out[np.isfinite(out)]
    if v.size < 5:
        return out

    med = float(np.median(v))
    out[np.isfinite(out) & ((out > 2.5 * med) | (out < 0.4 * med))] = np.nan

    n = out.size
    half = max(1, window // 2)
    local = np.full(n, np.nan)
    for i in range(n):
        w = out[max(0, i - half):min(n, i + half + 1)]
        w = w[np.isfinite(w)]
        if w.size >= 3:
            local[i] = np.median(w)

    finite = np.isfinite(out) & np.isfinite(local)
    with np.errstate(invalid="ignore", divide="ignore"):
        dev = np.abs(12.0 * np.log2(out / local))
    out[finite & (dev > jump_st)] = np.nan

    sm = out.copy()
    shalf = 2
    for i in range(n):
        w = out[max(0, i - shalf):min(n, i + shalf + 1)]
        w = w[np.isfinite(w)]
        sm[i] = np.median(w) if w.size >= 3 else np.nan
    return sm


def robust_range_st(f0: np.ndarray, ref: float) -> float | None:
    """Pitch span in semitones, using 5th-95th percentiles to ignore outliers."""
    v = f0[np.isfinite(f0)]
    if v.size < 5:
        return None
    st = to_semitones(v, ref)
    return round(float(np.percentile(st, 95) - np.percentile(st, 5)), 2)


def to_semitones(f0: np.ndarray, ref: float) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return 12.0 * np.log2(f0 / ref)


def frame_slice(times: np.ndarray, f0: np.ndarray, rms: np.ndarray, a: float, b: float):
    m = (times >= a) & (times <= b)
    return f0[m], rms[m]


def slope_semitones_per_sec(t: np.ndarray, st: np.ndarray) -> float | None:
    m = np.isfinite(st)
    if m.sum() < 4:
        return None
    tt, ss = t[m], st[m]
    if tt[-1] - tt[0] < 0.08:
        return None
    return float(np.polyfit(tt - tt[0], ss, 1)[0])


# ---------------------------------------------------------------- alignment


@dataclass
class AlignResult:
    pairs: list[tuple[int, int]] = field(default_factory=list)   # (ref_idx, asr_idx)
    skipped: list[dict] = field(default_factory=list)            # in ref, missing in ASR
    substituted: list[dict] = field(default_factory=list)        # ref word -> what was heard
    added: list[dict] = field(default_factory=list)              # heard but not in ref
    low_conf: list[dict] = field(default_factory=list)           # ASR unsure


def align(ref: list[str], asr: list[dict]) -> AlignResult:
    a = [normalize(w["word"]) for w in asr]
    sm = difflib.SequenceMatcher(a=ref, b=a, autojunk=False)
    res = AlignResult()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                res.pairs.append((i1 + k, j1 + k))
        elif tag == "replace":
            for k in range(i2 - i1):
                j = j1 + k
                if j < j2:
                    res.pairs.append((i1 + k, j))
                    res.substituted.append(
                        {
                            "ref": ref[i1 + k],
                            "heard": asr[j]["word"],
                            "start": asr[j]["start"],
                            "prob": asr[j]["prob"],
                            "domain_term": ref[i1 + k] in DOMAIN_TERMS,
                        }
                    )
                else:
                    res.skipped.append(
                        {"ref": ref[i1 + k], "reason": "merged/unclear",
                         "domain_term": ref[i1 + k] in DOMAIN_TERMS}
                    )
        elif tag == "delete":
            for k in range(i1, i2):
                res.skipped.append(
                    {"ref": ref[k], "reason": "not detected", "domain_term": ref[k] in DOMAIN_TERMS}
                )
        elif tag == "insert":
            for j in range(j1, j2):
                res.added.append(
                    {"heard": asr[j]["word"], "start": asr[j]["start"], "prob": asr[j]["prob"],
                     "domain_term": normalize(asr[j]["word"]) in DOMAIN_TERMS}
                )
    for w in asr:
        if w["prob"] < 0.60 and len(normalize(w["word"])) > 2:
            res.low_conf.append(
                {"word": w["word"], "start": w["start"], "prob": w["prob"],
                 "domain_term": normalize(w["word"]) in DOMAIN_TERMS}
            )
    return res


# ---------------------------------------------------------------- metrics


def pause_stats(asr_words: list[dict], total_dur: float, min_pause: float = 0.25) -> dict:
    pauses = []
    for i in range(len(asr_words) - 1):
        gap = asr_words[i + 1]["start"] - asr_words[i]["end"]
        if gap >= min_pause:
            pauses.append(
                {
                    "after": asr_words[i]["word"],
                    "start": round(asr_words[i]["end"], 2),
                    "duration": round(gap, 2),
                }
            )
    speech = sum(w["end"] - w["start"] for w in asr_words)
    return {
        "count": len(pauses),
        "total_silence": round(sum(p["duration"] for p in pauses), 2),
        "longest": max((p["duration"] for p in pauses), default=0.0),
        "pauses": sorted(pauses, key=lambda p: -p["duration"])[:25],
        "total_duration": round(total_dur, 2),
        "voiced_duration": round(speech, 2),
    }


def terminal_contour(times, f0, a: float, b: float, median_f0: float,
                     window: float = 0.5, min_frames: int = 8,
                     min_span: float = 0.20) -> dict | None:
    """Classify the pitch movement at the very end of a span.

    Takes every voiced frame inside the final ``window`` seconds of speech, counted
    back from the last voiced frame. Quiet recordings produce intermittently voiced
    frames, so requiring an unbroken run of frames would throw away most samples;
    instead the constraints are on frame count and time span. Returns None when
    there is not enough clean data to judge.
    """
    m = (times >= a) & (times <= b)
    tt, ff = times[m], f0[m]
    if ff.size == 0:
        return None
    good = np.isfinite(ff)
    if good.sum() < min_frames:
        return None

    t_last = float(tt[good][-1])
    sel = np.where(good & (tt >= t_last - window))[0]
    if sel.size < min_frames:
        return None
    ts, st = tt[sel], to_semitones(ff[sel], median_f0)
    span = float(ts[-1] - ts[0])
    if span < min_span:
        return None

    slope = float(np.polyfit(ts - ts[0], st, 1)[0])
    delta = float(st[-1] - st[0])
    if delta <= -1.0:
        verdict = "下降"
    elif delta >= 1.0:
        verdict = "上升"
    else:
        verdict = "基本持平"
    return {
        "delta_st": round(delta, 2),
        "slope_st_per_s": round(slope, 2),
        "frames": int(sel.size),
        "span_s": round(span, 2),
        "verdict": verdict,
    }


def sentence_prosody(sentences: list[str], ref_tokens: list[str], asr: dict,
                     align_pairs: list[tuple[int, int]], times, f0, rms,
                     median_f0: float) -> list[dict]:
    """Measure each reference sentence on the ASR timeline.

    Sentence boundaries come from the word alignment (ref index -> ASR index), not
    from a proportional word-count split, so repetitions and dropped words in the
    recording cannot shift the boundaries onto the wrong audio.
    """
    words = asr["words"]
    if not words:
        return []
    ref2asr = dict(align_pairs)
    counts = [len(tokenize(s)) for s in sentences]
    out = []
    cursor = 0
    for sent, n in zip(sentences, counts):
        idxs = [ref2asr[i] for i in range(cursor, cursor + n) if i in ref2asr]
        cursor += n
        if not idxs:
            continue
        a, b = min(idxs), max(idxs)
        seg_words = words[a:b + 1]
        if not seg_words:
            continue
        t0, t1 = seg_words[0]["start"], seg_words[-1]["end"]
        item = {
            "sentence": sent,
            "start": round(t0, 2),
            "end": round(t1, 2),
            "duration": round(t1 - t0, 2),
            "words": len(seg_words),
            "ref_words": n,
            "wpm": round(len(seg_words) / max(t1 - t0, 1e-6) * 60, 1),
            "low_conf_words": [w["word"] for w in seg_words if w["prob"] < 0.5],
        }

        sf0, _ = frame_slice(times, f0, rms, t0, t1)
        voiced = sf0[np.isfinite(sf0)]
        if voiced.size >= 6:
            st_all = to_semitones(voiced, median_f0)
            item["f0_median"] = round(float(np.median(voiced)), 1)
            item["range_st"] = round(float(np.percentile(st_all, 95) - np.percentile(st_all, 5)), 2)
            item["std_st"] = round(float(st_all.std()), 2)

        # terminal contour: measured on the final contiguous voiced run
        last_word = seg_words[-1]
        tc = terminal_contour(times, f0, max(last_word["start"], t1 - 0.9), last_word["end"],
                              median_f0)
        if tc:
            item["final_word"] = last_word["word"]
            item["final_contour"] = tc
        out.append(item)
    return out


def flat_speech_ratio(sentences_prosody: list[dict], limit: float = 3.0,
                      min_duration: float = 1.5) -> list[dict]:
    """Sentences with too little pitch movement to sound natural (monotone)."""
    return [
        s for s in sentences_prosody
        if s.get("range_st") is not None
        and s["range_st"] < limit
        and s.get("duration", 0) >= min_duration
    ]


# ---------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze an English read-aloud recording.")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--ref-md", help="rewrite .md; its '## Rewritten Text' section is used")
    ap.add_argument("--ref-text", help="raw reference text")
    ap.add_argument("--model", default="base.en", help="faster-whisper model (tiny.en/base.en/small.en)")
    ap.add_argument("--domain-prompt", action="store_true",
                    help="bias decoding with the built-in technical vocabulary (recommended)")
    ap.add_argument("--initial-prompt", help="custom decoder bias text")
    ap.add_argument("--asr-cache", help="directory for cached transcriptions (speeds up re-runs)")
    ap.add_argument("--json", help="write full JSON report here")
    args = ap.parse_args()

    initial_prompt = args.initial_prompt
    if args.domain_prompt and not initial_prompt:
        initial_prompt = DEFAULT_DOMAIN_PROMPT

    x, sr = decode_audio(args.audio)
    total_dur = len(x) / sr
    times, f0, rms = estimate_f0(x, sr)
    f0 = _clean_f0(f0)
    voiced = f0[np.isfinite(f0)]
    median_f0 = float(np.median(voiced)) if voiced.size else 0.0

    peak_dbfs = round(20 * math.log10(float(np.abs(x).max()) + 1e-12), 1)
    rms_dbfs = round(20 * math.log10(float(np.sqrt((x ** 2).mean())) + 1e-12), 1)
    noise_floor = float(np.percentile(rms, 15))
    gate = max(noise_floor * 3.0, float(np.percentile(rms, 90)) * 0.12)
    activity = round(float((rms > gate).mean()), 3)

    asr = transcribe_cached(x, sr, args.model, initial_prompt=initial_prompt,
                            audio_path=args.audio, cache_dir=args.asr_cache)

    if args.ref_md:
        ref_source = f"md:{args.ref_md}"
        ref_text = extract_rewritten_text(args.ref_md)
    elif args.ref_text:
        ref_source = "text"
        ref_text = strip_markdown(args.ref_text)
    else:
        ref_source = "asr"
        ref_text = strip_markdown(" ".join(s["text"] for s in asr["segments"]))

    ref_tokens = tokenize(ref_text)
    sentences = split_sentences(ref_text)
    al = align(ref_tokens, asr["words"])
    ps = pause_stats(asr["words"], total_dur)
    sp = sentence_prosody(sentences, ref_tokens, asr, al.pairs, times, f0, rms, median_f0)

    n_asr = len(asr["words"])
    articulation_wpm = (
        n_asr / max(ps["total_duration"] - ps["total_silence"], 1e-6) * 60
    )

    report = {
        "audio": os.path.abspath(args.audio),
        "reference_source": ref_source,
        "reference_text": ref_text,
        "model": args.model,
        "initial_prompt": initial_prompt,
        "duration_s": round(total_dur, 2),
        "audio_quality": {
            "peak_dbfs": peak_dbfs,
            "rms_dbfs": rms_dbfs,
            "speech_activity": activity,
            "voiced_frame_share": round(float(np.isfinite(f0).mean()), 3),
        },
        "word_count_asr": n_asr,
        "word_count_ref": len(ref_tokens),
        "speech_rate": {
            "overall_wpm": round(n_asr / max(total_dur, 1e-6) * 60, 1),
            "articulation_wpm": round(articulation_wpm, 1),
            "silence_share": round(ps["total_silence"] / max(total_dur, 1e-6) * 100, 1),
        },
        "pause": ps,
        "pitch": {
            "median_f0_hz": round(median_f0, 1),
            "voiced_frames": int(voiced.size),
            "voiced_share": round(float(voiced.size / max(len(f0), 1)), 3),
            "overall_range_st": robust_range_st(f0, median_f0),
            "overall_std_st": round(float(to_semitones(voiced, median_f0).std()), 2) if voiced.size else None,
            "flat_sentences": len(flat_speech_ratio(sp)),
            "flat_sentence_total": len(sp),
        },
        "alignment": {
            "matched": len(al.pairs),
            "match_rate": round(len(al.pairs) / max(len(ref_tokens), 1), 3),
            "skipped": al.skipped,
            "substituted": al.substituted,
            "added": al.added,
            "low_confidence": al.low_conf,
        },
        "sentences": sp,
        "asr_segments": asr["segments"],
    }

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    # ---- console summary
    print(f"duration        : {report['duration_s']}s   words: {n_asr} (ref {len(ref_tokens)})")
    print(f"rate            : overall {report['speech_rate']['overall_wpm']} wpm | "
          f"articulation {report['speech_rate']['articulation_wpm']} wpm | "
          f"silence {report['speech_rate']['silence_share']}%")
    print(f"pauses          : {ps['count']} (longest {ps['longest']}s)")
    print(f"pitch           : median {report['pitch']['median_f0_hz']} Hz | "
          f"range {report['pitch']['overall_range_st']} st | std {report['pitch']['overall_std_st']} st")
    print(f"alignment       : {len(al.pairs)}/{len(ref_tokens)} matched "
          f"({report['alignment']['match_rate']:.0%})")
    if al.substituted:
        print("  substituted   : " + "; ".join(f"{s['ref']}->{s['heard']}" for s in al.substituted[:20]))
    if al.skipped:
        print("  skipped       : " + ", ".join(s["ref"] for s in al.skipped[:20]))
    if al.added:
        print("  added         : " + ", ".join(s["heard"] for s in al.added[:20]))
    print("sentences:")
    for s in sp:
        tc = s.get("final_contour") or {}
        print(f"  [{s['start']:6.2f}-{s['end']:6.2f}] {s['wpm']:6.1f}wpm "
              f"range={s.get('range_st','-')}st "
              f"尾调={tc.get('verdict','n/a')}({tc.get('delta_st','-')}st/{tc.get('frames',0)}帧)"
              f" | {s['sentence'][:58]}")
    if args.json:
        print(f"\nJSON -> {args.json}")


if __name__ == "__main__":
    main()
