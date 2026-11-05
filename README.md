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
The default voice is `shubh_en_narration` (model `bulbul:v4-flash`, English).
Options: `--speaker <voice>`, `--language hi-IN`, `--model bulbul:v3`.

## 2. Merge video and audio — `merge_video_audio/`

```
python merge_video_audio/merge.py recording_31.mp4 output/recording_31/timeline.csv
```

If one video holds several recordings back to back, pass each recording's timeline
with `@` and the time that recording starts in the video:

```
python merge_video_audio/merge.py full_video.mp4 output/recording_31/timeline.csv@0:00 output/recording_33/timeline.csv@19:05 output/recording_34/timeline.csv@30:10 output/recording_35/timeline.csv@32:40
```

Each clip starts at its script timestamp (plus its recording's start time). A clip that runs into the next line is
sped up, at most 1.3x by default (`--max-speedup`), and a warning is printed if
it still doesn't fit. The video is copied as-is and the narration replaces the
original audio. Output: `recording_31_narrated.mp4` next to the video.

To get only the narration audio, give the length instead of a video:

```
python merge_video_audio/merge.py 36:47 output/recording_31/timeline.csv@0:00 output/recording_33/timeline.csv@19:05 output/recording_34/timeline.csv@30:10 output/recording_35/timeline.csv@32:40 --out narration.mp3
```
