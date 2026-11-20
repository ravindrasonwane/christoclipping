# ClipCraft Studio V3.3

This build is based on the latest ClipCraft Studio code you provided. It retains the YouTube URL input, transcription, clip selection, hook card, spoken hook, and subtitle themes.

## New in V3.3
- Optional presenter/facecam overlay from `input/my_videos/`
- Presenter layouts:
  - Small overlay, bottom-right
  - Small overlay, bottom-left
  - Half-screen, presenter on top
  - Half-screen, presenter on bottom
- Output resolutions:
  - 1080x1920 vertical (Reels / Shorts)
  - 720x1280 vertical HD
  - 1080x1080 square
  - 1920x1080 Full HD landscape
  - 1280x720 HD landscape

## Setup
1. Install Python 3.10+ and FFmpeg (ffmpeg and ffprobe must be in PATH).
2. Put your facecam/presenter videos in `input/my_videos/`.
3. In PowerShell, open this folder and run:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

4. Paste a YouTube URL, select your presenter video (or choose no presenter), choose its position and output resolution, then create Shorts.

The presenter video is looped to cover each selected source segment. It is composited only over the selected source clip; the 3.2-second hook card remains first and does not show the presenter. The presenter audio is not mixed; the original YouTube audio remains. Use only videos you own or have permission to process.
