"""Turn a timestamped script into one Sarvam TTS clip per line.

Script format (one line per cue, '#' lines are comments):
    00:03 | I'm starting the event.
    01:06 | Now we move to the ingestion service.

Writes <out>/NNN_<seconds>_<hash>.wav for each line plus <out>/timeline.csv,
which merge_video_audio/merge.py uses to place each clip on the video.

Usage:
    python script_to_audio/script_to_audio.py script_to_audio/scripts/recording_31.txt
"""
import argparse
import csv
import hashlib
import os
import re
import sys
import wave
from pathlib import Path

from sarvamai import SarvamAI
from sarvamai.play import save

REPO = Path(__file__).resolve().parents[1]
CUE = re.compile(r"^\s*((?:\d+:)?\d{1,2}:\d{2}(?:\.\d+)?)\s*\|\s*(.+?)\s*$")


def load_env(path):
    """Read KEY=value lines from .env without overriding real env vars."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not line.lstrip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def to_seconds(stamp):
    total = 0.0
    for part in stamp.split(":"):
        total = total * 60 + float(part)
    return total


def read_script(path):
    cues = []
    for n, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = CUE.match(raw)
        if not m:
            sys.exit(f"{path}:{n}: expected 'MM:SS | text', got: {raw!r}")
        cues.append((to_seconds(m[1]), m[2]))
    return sorted(cues, key=lambda c: c[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", help="timestamped script .txt")
    ap.add_argument("--out", help="output folder (default: output/<script name>)")
    ap.add_argument("--language", default="en-IN", help="e.g. en-IN, hi-IN, te-IN (default en-IN)")
    ap.add_argument("--model", default="bulbul:v4-flash")
    ap.add_argument("--speaker", help="Sarvam voice, e.g. shubh_en_narration (default: model default)")
    args = ap.parse_args()

    load_env(REPO / ".env")
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not key:
        sys.exit("SARVAM_API_KEY is empty. Paste your key into .env first.")

    cues = read_script(args.script)
    out = Path(args.out or REPO / "output" / Path(args.script).stem)
    out.mkdir(parents=True, exist_ok=True)
    client = SarvamAI(api_subscription_key=key)

    rows = []
    for i, (start, text) in enumerate(cues, 1):
        tag = hashlib.sha1(f"{args.language}|{args.model}|{args.speaker}|{text}".encode()).hexdigest()[:6]
        clip = out / f"{i:03d}_{int(start):05d}_{tag}.wav"
        if not clip.exists():  # re-runs only synthesize new or edited lines
            extra = {"speaker": args.speaker} if args.speaker else {}
            audio = client.text_to_speech.convert(
                text=text, language_code=args.language, model=args.model, **extra
            )
            save(audio, str(clip))
        with wave.open(str(clip)) as w:
            duration = w.getnframes() / w.getframerate()
        rows.append({"start": f"{start:.2f}", "duration": f"{duration:.2f}", "file": clip.name, "text": text})
        print(f"[{i}/{len(cues)}] {start:7.2f}s  {duration:5.2f}s  {text[:60]}")

    for a, b in zip(rows, rows[1:]):
        gap = float(b["start"]) - float(a["start"])
        if float(a["duration"]) > gap:
            print(f"note: clip at {a['start']}s is {a['duration']}s but the next cue starts {gap:.2f}s later")

    with open(out / "timeline.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["start", "duration", "file", "text"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} clips and {out / 'timeline.csv'}")


if __name__ == "__main__":
    main()
