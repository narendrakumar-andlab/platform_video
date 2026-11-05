# platform_video

Turn a timestamped script into Sarvam AI voice-over and lay it onto the screen recording in sync.

## Setup

```
pip install sarvamai
```

Install ffmpeg (it includes ffprobe) and make sure it's on your PATH.

Create a `.env` file in this folder (it's git-ignored) with your key:

```
SARVAM_API_KEY=your-key-here
```

Check the key works:

```
python hello_sarvam.py
```

## 1. Script to audio — `script_to_audio/`

Scripts live in `script_to_audio/scripts/`, one line per cue. Write `[silent]`
where there should be no voice-over:

```
00:03 | I'm starting the event.
00:29 | [silent]
01:06 | Now we move to the ingestion service.
```

```
python script_to_audio/script_to_audio.py script_to_audio/scripts/recording_31.txt
```

This writes one `.wav` per line and a `timeline.csv` to `output/recording_31/`.
Re-running only generates lines that are new or edited.
Options: `--language hi-IN`, `--speaker shubh_en_narration`, `--model bulbul:v3`.

## 2. Merge video and audio — `merge_video_audio/`

```
python merge_video_audio/merge.py recording_31.mp4 output/recording_31/timeline.csv
```

Each clip starts at its script timestamp. A clip that runs into the next line is
sped up, at most 1.3x by default (`--max-speedup`), and a warning is printed if
it still doesn't fit. The video is copied as-is and the narration replaces the
original audio. Output: `recording_31_narrated.mp4` next to the video.
