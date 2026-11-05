"""Put the narration clips onto the video, each starting at its script timestamp.

Reads the timeline.csv files written by script_to_audio/script_to_audio.py. When one
video holds several recordings back to back, pass one timeline per recording with
@ and the time that recording starts in the video. Script timestamps are relative
to their own recording, so they are shifted by that start time.

A clip that runs past the next line (or into the next recording) is sped up, up to
--max-speedup, so lines don't pile up. The video stream is copied untouched; the
narration replaces the original audio. Needs ffmpeg and ffprobe on PATH.

Usage:
    python merge_video_audio/merge.py recording_31.mp4 output/recording_31/timeline.csv

    python merge_video_audio/merge.py full_video.mp4 \\
        output/recording_31/timeline.csv@0:00 \\
        output/recording_33/timeline.csv@19:05 \\
        output/recording_34/timeline.csv@30:10 \\
        output/recording_35/timeline.csv@32:40

Give a length instead of a video to make just the narration audio (an mp3 of that length):
    python merge_video_audio/merge.py 36:47 output/recording_31/timeline.csv@0:00 ... --out narration.mp3
"""
import argparse
import csv
import re
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


def to_seconds(stamp):
    total = 0.0
    for part in stamp.split(":"):
        total = total * 60 + float(part)
    return total


def read_parts(specs):
    """Each spec is 'timeline.csv' or 'timeline.csv@MM:SS'. Returns parts sorted by start."""
    parts = []
    for spec in specs:
        path, _, at = spec.rpartition("@") if "@" in spec else (spec, "", "0")
        timeline = Path(path)
        with open(timeline, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        parts.append((to_seconds(at), timeline, rows))
    return sorted(parts, key=lambda p: p[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="screen recording to narrate, or a length like 36:47 to make only the audio track")
    ap.add_argument("timelines", nargs="+", help="timeline.csv, optionally @start time in the video (e.g. @19:05)")
    ap.add_argument("--out", help="output file (default: <video>_narrated.mp4 next to the video, or narration.mp3)")
    ap.add_argument("--max-speedup", type=float, default=1.3, help="fastest a clip may be played to fit its slot (default 1.3)")
    args = ap.parse_args()

    audio_only = re.fullmatch(r"(\d+:)?\d+:\d{2}(\.\d+)?", args.video) is not None
    if audio_only:
        video, video_len = None, to_seconds(args.video)
    else:
        video = Path(args.video)
        video_len = duration_of(video)
    parts = read_parts(args.timelines)

    # One flat list of clips on the video's clock; a clip may not run into the next part.
    clips = []
    for n, (offset, timeline, rows) in enumerate(parts):
        part_end = parts[n + 1][0] if n + 1 < len(parts) else video_len
        for row in rows:
            clips.append({
                "start": offset + float(row["start"]),
                "length": float(row["duration"]),
                "file": timeline.parent / row["file"],
                "text": row["text"],
                "limit": part_end,
                "limit_name": "the next recording starts" if n + 1 < len(parts) else "the video ends",
            })
    clips.sort(key=lambda c: c["start"])
    if not clips:
        sys.exit("no clips in the timeline(s)")

    inputs, chains, labels = ([] if audio_only else ["-i", str(video)]), [], []
    first = len(inputs) // 2  # input index of the first clip
    for i, clip in enumerate(clips):
        start, length = clip["start"], clip["length"]
        stop, stop_name = clip["limit"], clip["limit_name"]
        if i + 1 < len(clips) and clips[i + 1]["start"] < stop:
            stop, stop_name = clips[i + 1]["start"], "the next line starts"
        slot = max(stop - start, 0.1)
        tempo = min(length / slot, args.max_speedup) if length > slot else 1.0
        end = start + length / tempo
        if end > stop + 0.05:
            print(f"warning: line at {start:.2f}s ends at {end:.2f}s, after {stop_name} at {stop:.2f}s: {clip['text'][:50]}")

        inputs += ["-i", str(clip["file"])]
        steps = ([f"atempo={tempo:.3f}"] if tempo > 1.001 else []) + [f"adelay={round(start * 1000)}:all=1"]
        chains.append(f"[{first + i}:a]{','.join(steps)}[c{i}]")
        labels.append(f"[c{i}]")

    # Mix all clips without lowering their volume, then pad with silence to the full length.
    chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad[narration]")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(chains)]
    if audio_only:
        out = Path(args.out or "narration.mp3")
        cmd += ["-map", "[narration]", "-t", f"{video_len:.3f}", str(out)]
    else:
        out = Path(args.out) if args.out else video.with_name(f"{video.stem}_narrated.mp4")
        cmd += ["-map", "0:v", "-map", "[narration]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)]
    if subprocess.run(cmd).returncode != 0:
        sys.exit("ffmpeg failed")
    print(f"Wrote {out} ({len(clips)} lines from {len(parts)} part(s), {video_len:.1f}s long)")


if __name__ == "__main__":
    main()
