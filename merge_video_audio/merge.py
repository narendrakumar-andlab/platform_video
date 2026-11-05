"""Put the narration clips onto the video, each starting at its script timestamp.

Reads the timeline.csv written by script_to_audio/script_to_audio.py. A clip that
runs past the next cue is sped up (up to --max-speedup) so lines don't pile up.
The video stream is copied untouched; the narration replaces the original audio.
Needs ffmpeg and ffprobe on PATH.

Usage:
    python merge_video_audio/merge.py recording_31.mp4 output/recording_31/timeline.csv
"""
import argparse
import csv
import subprocess
import sys
from pathlib import Path


def duration_of(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"ffprobe could not read {path}: {result.stderr.strip()}")
    return float(result.stdout.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="screen recording to narrate")
    ap.add_argument("timeline", help="timeline.csv from script_to_audio")
    ap.add_argument("--out", help="output file (default: <video>_narrated.mp4 next to the video)")
    ap.add_argument("--max-speedup", type=float, default=1.3, help="fastest a clip may be played to fit its slot (default 1.3)")
    args = ap.parse_args()

    video = Path(args.video)
    timeline = Path(args.timeline)
    with open(timeline, newline="", encoding="utf-8") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: float(r["start"]))
    if not rows:
        sys.exit(f"{timeline} has no clips")
    video_len = duration_of(video)

    inputs, chains, labels = ["-i", str(video)], [], []
    for i, row in enumerate(rows):
        start, length = float(row["start"]), float(row["duration"])
        next_start = float(rows[i + 1]["start"]) if i + 1 < len(rows) else video_len
        slot = max(next_start - start, 0.1)
        tempo = min(length / slot, args.max_speedup) if length > slot else 1.0
        end = start + length / tempo
        if end > next_start + 0.05:
            what = "the video ends" if i + 1 == len(rows) else "the next line starts"
            print(f"warning: line at {start:.2f}s ends at {end:.2f}s, after {what} at {next_start:.2f}s: {row['text'][:50]}")

        inputs += ["-i", str(timeline.parent / row["file"])]
        steps = ([f"atempo={tempo:.3f}"] if tempo > 1.001 else []) + [f"adelay={round(start * 1000)}:all=1"]
        chains.append(f"[{i + 1}:a]{','.join(steps)}[c{i}]")
        labels.append(f"[c{i}]")

    # Mix all clips without lowering their volume, then pad with silence to the video's length.
    chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad[narration]")
    out = Path(args.out) if args.out else video.with_name(f"{video.stem}_narrated.mp4")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(chains),
        "-map", "0:v", "-map", "[narration]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out),
    ]
    if subprocess.run(cmd).returncode != 0:
        sys.exit("ffmpeg failed")
    print(f"Wrote {out} ({len(rows)} lines on a {video_len:.1f}s video)")


if __name__ == "__main__":
    main()
