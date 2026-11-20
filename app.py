import asyncio

import re

import shutil

import subprocess

from urllib.parse import urlparse

from pathlib import Path



import streamlit as st

from faster_whisper import WhisperModel



st.set_page_config(page_title="ClipCraft Studio", page_icon="✂️", layout="wide")



HIGHLIGHT_WORDS = {

    "important", "secret", "mistake", "never", "always", "best", "worst",

    "why", "how", "learn", "truth", "problem", "solution", "result",

    "money", "career", "job", "success", "fail", "failure", "tip",

    "strategy", "finally", "actually", "remember", "because", "imagine",

    "example", "discover", "warning", "avoid", "difference", "reason"

}

STOP_WORDS = {

    "this", "that", "with", "from", "your", "about", "what", "when", "where",

    "which", "while", "will", "would", "there", "their", "they", "them",

    "have", "has", "had", "into", "than", "then", "just", "like", "some",

    "more", "very", "video", "talk", "talking", "show", "shows", "explains",

    "explaining", "the", "and", "for", "are", "you", "not", "but", "was",

    "were", "its", "our", "can", "could", "should", "how", "why"

}



def run(cmd, cwd=None):

    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

    if result.returncode != 0:

        raise RuntimeError(result.stderr[-5000:] or "FFmpeg command failed")

    return result



def check_ffmpeg():

    for binary in ("ffmpeg", "ffprobe"):

        try:

            subprocess.run([binary, "-version"], capture_output=True, check=True)

        except Exception:

            raise RuntimeError(f"{binary} was not found. Install FFmpeg and add it to PATH.")



def clean_text(text):

    return re.sub(r"\s+", " ", text).strip()



def tokens(text):

    return {

        word for word in re.findall(r"[a-zA-Z0-9']+", (text or "").lower())

        if len(word) > 2 and word not in STOP_WORDS

    }



def timestamp_ass(seconds):

    centis = max(0, int(round(seconds * 100)))

    h, centis = divmod(centis, 360000)

    m, centis = divmod(centis, 6000)

    s, cs = divmod(centis, 100)

    return f"{h}:{m:02}:{s:02}.{cs:02}"



def score_window(segments, start, end, context_terms):

    words, parts = [], []

    for seg in segments:

        if seg.end > start and seg.start < end:

            parts.append(seg.text)

            words.extend(re.findall(r"[A-Za-z0-9']+", seg.text.lower()))

    text = clean_text(" ".join(parts))

    if not words:

        return -1, text

    word_set = set(words)

    score = (

        sum(1.5 for w in words if w in HIGHLIGHT_WORDS)

        + text.count("?") * 1.5

        + min(len(re.findall(r"\b\d+\b", text)), 5) * 0.5

        + len(word_set.intersection(context_terms)) * 3.0

        + min(len(words) / 35, 2.0)

    )

    return score, text



def make_hook_from_description(description):

    """Turn the user's video brief into a short on-screen + spoken opening hook."""

    brief = clean_text(description)

    if not brief:

        return "Watch this before you scroll."

    # Use the first complete thought supplied by the user, trimmed for a short opener.

    first = re.split(r"(?<=[.!?])\s+", brief)[0]

    first = re.sub(r"^(this video is about|video about|topic:)\s*", "", first, flags=re.I)

    words = first.split()

    if len(words) > 12:

        first = " ".join(words[:12]).rstrip(",;:")

    first = first.rstrip(".!?")

    if len(first.split()) < 4:

        return f"Here's what you need to know about {first}."

    return first + "."



def ass_header(font_size, primary, outline, alignment, margin_v):

    return f"""[Script Info]

ScriptType: v4.00+

PlayResX: 1080

PlayResY: 1920

ScaledBorderAndShadow: yes



[V4+ Styles]

Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding

Style: Default,Arial,{font_size},{primary},&H000000FF,{outline},&H90000000,-1,0,1,5,2,{alignment},85,85,{margin_v},1



[Events]

Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text

"""



def write_caption_ass(segments, clip_start, clip_end, path, subtitle_style):

    themes = {

        "Creator Pop (yellow + white)": ("&H00FFFFFF", "&H00101010", "&H0000D7FF", 58),

        "Clean Professional (white + cyan)": ("&H00FFFFFF", "&H00101010", "&H00FFFF55", 52),

        "Bold Viral (white + lime)": ("&H00FFFFFF", "&H00101010", "&H0000FF66", 60)

    }

    primary, outline, highlight, size = themes[subtitle_style]

    header = ass_header(size, primary, outline, 2, 165)

    events = []

    for seg in segments:

        start, end = max(seg.start, clip_start), min(seg.end, clip_end)

        if end <= start:

            continue

        words = clean_text(seg.text).split()

        if not words:

            continue

        rendered = []

        for word in words:

            plain = re.sub(r"[^A-Za-z0-9']", "", word).lower()

            safe = word.replace("{", r"\{").replace("}", r"\}")

            if plain in HIGHLIGHT_WORDS or len(plain) >= 9:

                rendered.append(r"{\c" + highlight + "}" + safe + r"{\c" + primary + "}")

            else:

                rendered.append(safe)

        lines, line = [], []

        for word in rendered:

            line.append(word)

            if len(" ".join(line)) > 27 and len(line) > 1:

                last = line.pop()

                lines.append(" ".join(line))

                line = [last]

        if line:

            lines.append(" ".join(line))

        text = r"\N".join(lines[:2])

        events.append(

            f"Dialogue: 0,{timestamp_ass(start-clip_start)},{timestamp_ass(end-clip_start)},"

            f"Default,,0,0,0,,{{\\an2}}{text}"

        )

    Path(path).write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")



def write_hook_ass(hook, path, subtitle_style):

    themes = {

        "Creator Pop (yellow + white)": ("&H00FFFFFF", "&H0000D7FF", 76),

        "Clean Professional (white + cyan)": ("&H00FFFFFF", "&H00FFFF55", 68),

        "Bold Viral (white + lime)": ("&H00FFFFFF", "&H0000FF66", 78)

    }

    primary, highlight, size = themes[subtitle_style]

    header = ass_header(size, primary, "&H00101010", 5, 0)

    safe = hook.replace("{", r"\{").replace("}", r"\}")

    # Emphasize a short central phrase in the selected accent color.

    words = safe.split()

    if len(words) > 2:

        words[0] = r"{\c" + highlight + "}" + words[0] + r"{\c" + primary + "}"

    text = r"\N".join(

        [" ".join(words[:4]), " ".join(words[4:8]), " ".join(words[8:12])]

    ).strip()

    event = f"Dialogue: 0,0:00:00.00,0:00:03.20,Default,,0,0,0,,{{\\an5}}{text}\n"

    Path(path).write_text(header + event, encoding="utf-8-sig")



async def generate_voice(text, output_mp3, voice):

    import edge_tts

    await edge_tts.Communicate(text, voice).save(str(output_mp3))



def create_vertical_clip(video_path, ass_path, hook_ass_path, output_path,
                         start, duration, hook, voice_enabled, voice_name,
                         presenter_path=None, presenter_layout="Small overlay - bottom right",
                         output_width=1080, output_height=1920):
    video_path = Path(video_path).resolve()
    ass_path = Path(ass_path).resolve()
    hook_ass_path = Path(hook_ass_path).resolve()
    output_path = Path(output_path).resolve()
    work_dir = output_path.parent
    main_only = work_dir / (output_path.stem + "_main.mp4")
    intro_video = work_dir / (output_path.stem + "_intro.mp4")
    intro_voice = work_dir / (output_path.stem + "_voice.mp3")

    def ass_filter(path):
        return "ass=filename='" + path.as_posix().replace(":", r"\:") + "'"

    base_scale = (
        f"scale={output_width}:{output_height}:force_original_aspect_ratio=increase,"
        f"crop={output_width}:{output_height},setsar=1"
    )

    if presenter_path:
        presenter_path = Path(presenter_path).resolve()
        filters = []
        if presenter_layout == "Half screen - presenter on top":
            main_h = output_height // 2
            presenter_h = output_height - main_h
            filters += [
                f"[0:v]scale={output_width}:{main_h}:force_original_aspect_ratio=increase,crop={output_width}:{main_h},setsar=1[main]",
                f"[1:v]scale={output_width}:{presenter_h}:force_original_aspect_ratio=increase,crop={output_width}:{presenter_h},setsar=1[presenter]",
                "[presenter][main]vstack=inputs=2[composed]"
            ]
        elif presenter_layout == "Half screen - presenter on bottom":
            presenter_h = output_height // 2
            main_h = output_height - presenter_h
            filters += [
                f"[0:v]scale={output_width}:{main_h}:force_original_aspect_ratio=increase,crop={output_width}:{main_h},setsar=1[main]",
                f"[1:v]scale={output_width}:{presenter_h}:force_original_aspect_ratio=increase,crop={output_width}:{presenter_h},setsar=1[presenter]",
                "[main][presenter]vstack=inputs=2[composed]"
            ]
        else:
            pip_w, pip_h = int(output_width * 0.34), int(output_height * 0.27)
            margin = max(18, int(min(output_width, output_height) * 0.025))
            x = f"W-w-{margin}" if presenter_layout == "Small overlay - bottom right" else str(margin)
            filters += [
                f"[0:v]{base_scale}[main]",
                f"[1:v]scale={pip_w}:{pip_h}:force_original_aspect_ratio=increase,crop={pip_w}:{pip_h},setsar=1,drawbox=x=0:y=0:w=iw:h=ih:color=white@0.95:t=4[presenter]",
                f"[main][presenter]overlay=x={x}:y=H-h-{margin}[composed]"
            ]
        filters.append(f"[composed]{ass_filter(ass_path)}[vout]")
        cmd = [
            "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video_path),
            "-stream_loop", "-1", "-i", str(presenter_path),
            "-t", f"{duration:.3f}", "-filter_complex", ";".join(filters),
            "-map", "[vout]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
            "-movflags", "+faststart", str(main_only)
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video_path),
            "-t", f"{duration:.3f}", "-vf", base_scale + "," + ass_filter(ass_path),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
            "-movflags", "+faststart", str(main_only)
        ]
    run(cmd)

    if voice_enabled:
        asyncio.run(generate_voice(hook, intro_voice, voice_name))
        run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"color=c=0x101827:s={output_width}x{output_height}:r=30:d=3.2",
            "-i", str(intro_voice), "-vf", ass_filter(hook_ass_path), "-t", "3.2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
            "-shortest", str(intro_video)
        ])
        concat_file = work_dir / (output_path.stem + "_concat.txt")

        def quote_path(p):
            return str(p.resolve()).replace("\\", "/").replace("'", r"'\''")

        concat_file.write_text(
            f"file '{quote_path(intro_video)}'\nfile '{quote_path(main_only)}'\n",
            encoding="utf-8"
        )
        run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy", "-movflags", "+faststart", str(output_path)
        ])
    else:
        main_only.replace(output_path)
    return output_path


def is_youtube_url(url):

    """Accept standard YouTube watch, Shorts, embed and youtu.be URLs only."""

    try:

        parsed = urlparse(url.strip())

        host = (parsed.hostname or "").lower()

        allowed = {

            "youtube.com", "www.youtube.com", "m.youtube.com",

            "music.youtube.com", "youtu.be", "www.youtube-nocookie.com"

        }

        return parsed.scheme in {"http", "https"} and host in allowed

    except Exception:

        return False





def download_youtube_video(url, work_dir, progress):

    """Download a user-provided YouTube video with yt-dlp for local processing."""

    if not is_youtube_url(url):

        raise ValueError("Please enter a valid YouTube URL (youtube.com or youtu.be).")



    work_dir = Path(work_dir).resolve()

    work_dir.mkdir(parents=True, exist_ok=True)



    # Remove stale source files so we don't accidentally process an older download.

    for old_file in work_dir.glob("source_video.*"):

        if old_file.is_file():

            old_file.unlink()



    progress.progress(3, text="Downloading video from YouTube...")

    output_template = str(work_dir / "source_video.%(ext)s")

    cmd = [

        "python", "-m", "yt_dlp",

        "--no-playlist",

        "--no-warnings",

        "--format", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",

        "--merge-output-format", "mp4",

        "--output", output_template,

        url.strip()

    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:

        error_text = (result.stderr or result.stdout or "yt-dlp could not download this video.")[-3500:]

        raise RuntimeError(

            "YouTube download failed. The video may be private, restricted, unavailable, "

            "or not downloadable with your current access. Details:\\\n" + error_text

        )



    candidates = [

        p for p in work_dir.glob("source_video.*")

        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}

    ]

    if not candidates:

        raise RuntimeError("Download finished, but no supported video file was found.")

    video_path = max(candidates, key=lambda p: p.stat().st_size)

    if video_path.stat().st_size == 0:

        raise RuntimeError("The downloaded video file is empty.")

    progress.progress(8, text="Video downloaded. Preparing transcription...")

    return video_path





def process_video(video_path, output_dir, clip_duration, number_clips, model_size,
                  description, subtitle_style, voice_enabled, voice_name, progress,
                  presenter_path=None, presenter_layout="Small overlay - bottom right",
                  output_width=1080, output_height=1920):

    check_ffmpeg()

    context_terms = tokens(description)

    progress.progress(12, text="Loading speech recognition model...")

    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    progress.progress(20, text="Transcribing video...")

    seg_iter, info = model.transcribe(str(video_path), beam_size=5, vad_filter=True)

    segments = list(seg_iter)

    if not segments:

        raise RuntimeError("No speech detected. Try a video with clear spoken audio.")



    total = max(s.end for s in segments)

    progress.progress(42, text="Finding moments that match your video brief...")

    step = max(8, clip_duration // 3)

    candidates, start = [], 0.0

    while start < total:

        end = min(start + clip_duration, total)

        if end - start >= min(10, clip_duration * 0.5):

            score, transcript = score_window(segments, start, end, context_terms)

            if transcript:

                candidates.append((score, start, end, transcript))

        start += step



    candidates.sort(key=lambda x: x[0], reverse=True)

    chosen = []

    for item in candidates:

        _, a, b, _ = item

        if all(b <= c[1] or a >= c[2] for c in chosen):

            chosen.append(item)

        if len(chosen) >= number_clips:

            break

    chosen.sort(key=lambda x: x[1])

    if not chosen:

        raise RuntimeError("Could not identify usable speech sections.")



    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for i, (_, a, b, transcript) in enumerate(chosen, 1):

        clip_dir = output_dir / f"clip_{i:02d}"

        clip_dir.mkdir(exist_ok=True)

        caption_ass = clip_dir / "captions.ass"

        hook_ass = clip_dir / "opening_hook.ass"

        write_caption_ass(segments, a, b, caption_ass, subtitle_style)



        # The user's description is now the source for the opening hook and spoken narration.

        hook = make_hook_from_description(description)

        write_hook_ass(hook, hook_ass, subtitle_style)



        output_path = output_dir / f"youtube_short_{i:02d}.mp4"

        progress.progress(45 + int(50 * i / len(chosen)),

                          text=f"Building opening hook and rendering clip {i}/{len(chosen)}...")

        create_vertical_clip(

            video_path, caption_ass, hook_ass, output_path, a, b-a,

            hook, voice_enabled, voice_name, presenter_path,
            presenter_layout, output_width, output_height
        )

        details = output_dir / f"youtube_short_{i:02d}_details.txt"

        details.write_text(

            f"Opening hook from your video brief:\n{hook}\n\n"

            f"Your video brief:\n{description}\n\n"

            f"Clip transcript:\n{transcript}\n",

            encoding="utf-8"

        )

        results.append((output_path, hook, transcript, a, b, details))

    progress.progress(100, text="All clips rendered!")

    return results



st.title("✂️ ClipCraft Studio")

st.caption("A visual hook first, then your video — with colorful captions and optional presenter overlay.")



with st.sidebar:

    st.header("Video settings")

    clip_duration = st.slider("Clip length", 15, 90, 45, 5)

    number_clips = st.slider("Number of clips", 1, 10, 3)

    model_size = st.selectbox("Transcription quality", ["tiny", "base", "small"], index=1)

    st.divider()

    st.header("Caption design")

    subtitle_style = st.selectbox(

        "Subtitle theme",

        ["Creator Pop (yellow + white)", "Clean Professional (white + cyan)", "Bold Viral (white + lime)"]

    )

    voice_enabled = st.toggle("Add spoken opening hook", value=True)

    voice_name = st.selectbox(

        "Hook voice",

        ["en-IN-NeerjaNeural", "en-IN-PrabhatNeural", "en-US-AriaNeural", "en-US-GuyNeural"],

        format_func=lambda v: {

            "en-IN-NeerjaNeural": "Indian English — Neerja (female)",

            "en-IN-PrabhatNeural": "Indian English — Prabhat (male)",

            "en-US-AriaNeural": "US English — Aria (female)",

            "en-US-GuyNeural": "US English — Guy (male)"

        }[v],

        disabled=not voice_enabled

    )

    st.caption("Spoken hook is placed before the original video. Internet is required for voice generation.")



st.subheader("Video layout and resolution")

presenter_folder = Path("input") / "my_videos"
presenter_folder.mkdir(parents=True, exist_ok=True)
presenter_files = sorted(
    [p for p in presenter_folder.iterdir()
     if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi"}],
    key=lambda p: p.name.lower()
)
presenter_options = ["No presenter video"] + [p.name for p in presenter_files]
selected_presenter_name = st.selectbox(
    "Choose your video from input/my_videos",
    presenter_options,
    help="Place your facecam/presenter videos in input/my_videos before launching ClipCraft."
)
presenter_path = None if selected_presenter_name == "No presenter video" else presenter_folder / selected_presenter_name

presenter_layout = st.selectbox(
    "Presenter position",
    [
        "Small overlay - bottom right",
        "Small overlay - bottom left",
        "Half screen - presenter on top",
        "Half screen - presenter on bottom",
    ],
    disabled=presenter_path is None
)

resolution_options = {
    "Mobile vertical — Reels / Shorts (1080 × 1920)": (1080, 1920),
    "Mobile vertical HD (720 × 1280)": (720, 1280),
    "Square — Instagram feed (1080 × 1080)": (1080, 1080),
    "Laptop / YouTube Full HD (1920 × 1080)": (1920, 1080),
    "Laptop / YouTube HD (1280 × 720)": (1280, 720),
}
selected_resolution = st.selectbox("Output resolution", list(resolution_options.keys()))
output_width, output_height = resolution_options[selected_resolution]

st.subheader("1. Enter your YouTube video URL")

youtube_url = st.text_input(

    "YouTube URL",

    placeholder="https\://www\.youtube.com/watch?v=... or https\://youtu.be/...",

    help="Paste a public or otherwise accessible YouTube video URL that you own or have permission to process."

)

st.caption("ClipCraft downloads the source video locally, then uses the same transcription and clipping workflow as before.")



st.subheader("2. Describe the video and the hook you want viewers to hear")

description = st.text_area(

    "Video brief / opening hook",

    placeholder="Example: Want to become a Data Analyst? In this video, we reveal the SQL skills and resume mistakes that decide whether you get shortlisted.",

    height=120,

    help="This text is used directly to create the opening visual hook and spoken narration. Keep it punchy: ideally 8–15 words for a strong opener. It also guides highlight relevance."

)

st.caption("This field is used at the very start of every generated clip: it appears on a 3.2-second title card and is spoken by the selected voice.")



if youtube_url.strip():

    st.caption("YouTube source URL entered. The video will be downloaded when you click Create polished Shorts.")



if youtube_url.strip() and st.button("Create polished Shorts", type="primary", use_container_width=True):

    if not is_youtube_url(youtube_url):

        st.error("Please enter a valid YouTube URL (youtube.com or youtu.be).")

    elif not description.strip():

        st.warning("Write the video brief / opening hook before generating.")

    else:

        work = Path("work")

        work.mkdir(exist_ok=True)

        progress = st.progress(0)

        try:

            input_path = download_youtube_video(youtube_url, work, progress)

            results = process_video(

                input_path, Path("output"), clip_duration, number_clips, model_size,

                description.strip(), subtitle_style, voice_enabled, voice_name, progress,
                presenter_path, presenter_layout, output_width, output_height
            )

            st.success(f"Created {len(results)} Shorts.")

            for path, hook, transcript, a, b, details in results:

                with st.container(border=True):

                    st.subheader(path.name)

                    st.caption(f"Opening hook: {hook}")

                    st.caption(f"Original source section: {a:.1f}s – {b:.1f}s")

                    st.video(str(path))

                    c1, c2 = st.columns(2)

                    with c1:

                        st.download_button(

                            "Download video", path.read_bytes(), path.name,

                            "video/mp4", key=f"vid_{path.name}", use_container_width=True

                        )

                    with c2:

                        st.download_button(

                            "Download hook + transcript", details.read_bytes(),

                            details.name, "text/plain", key=f"txt_{path.name}",

                            use_container_width=True

                        )

                    with st.expander("Review selected transcript"):

                        st.write(transcript)

        except Exception as exc:

            st.error(f"Something went wrong: {exc}")

            st.caption("If the voice service fails, disable the spoken opening hook and retry.")
