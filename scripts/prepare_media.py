#!/usr/bin/env python3
"""Prepare video / image inputs for visual analysis.

Video: probe metadata, detect scene cuts, extract keyframes, build a contact
sheet, generate a palette and an audio waveform.
Image: make a <=1080px preview and a palette.

Only the Python standard library is used. ffmpeg and ffprobe must be on PATH.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path


VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".flv", ".wmv", ".mts", ".m2ts", ".gif"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".avif"}


def die(message: str, code: int = 1) -> None:
    print(f"[error] {message}", file=sys.stderr)
    raise SystemExit(code)


def require_tools() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if not shutil.which(name)]
    if not missing:
        return
    print(f"[error] missing: {', '.join(missing)}", file=sys.stderr)
    print("install:", file=sys.stderr)
    print("  macOS:   brew install ffmpeg", file=sys.stderr)
    print("  Ubuntu:  sudo apt install ffmpeg", file=sys.stderr)
    print("  Windows: winget install Gyan.FFmpeg", file=sys.stderr)
    raise SystemExit(2)


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def ffprobe_json(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    proc = run(cmd)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe returned invalid JSON for {path}") from exc


def parse_rate(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else None
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def pick_video_stream(info: dict) -> dict | None:
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    return None


def pick_audio_stream(info: dict) -> dict | None:
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "audio":
            return stream
    return None


def media_duration(info: dict) -> float:
    format_duration = info.get("format", {}).get("duration")
    if format_duration not in (None, "N/A"):
        try:
            return float(format_duration)
        except ValueError:
            pass
    video = pick_video_stream(info) or {}
    stream_duration = video.get("duration")
    if stream_duration not in (None, "N/A"):
        try:
            return float(stream_duration)
        except ValueError:
            pass
    return 0.0


def format_timecode(seconds: float) -> str:
    # Floor keeps filenames stable: 3.6s and 4.5s must not both become 00m04s.
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}h{minutes:02d}m{secs:02d}s"
    return f"{minutes:02d}m{secs:02d}s"


def detect_scenes(path: Path, threshold: float) -> list[float]:
    # Scale down before scene detection; decoding at 320px is much faster and
    # scene scores are stable enough for editorial use.
    vf = f"scale=320:-2,select='gt(scene,{threshold})',showinfo"
    cmd = [
        "ffmpeg", "-hide_banner", "-i", str(path), "-vf", vf,
        "-an", "-f", "null", "-",
    ]
    proc = run(cmd, check=False)
    times: list[float] = []
    for line in proc.stderr.splitlines():
        match = re.search(r"pts_time:([0-9.]+)", line)
        if match:
            times.append(float(match.group(1)))
    return times


def uniform_times(duration: float, count: int) -> list[float]:
    if duration <= 0 or count <= 0:
        return [0.0]
    if count == 1:
        return [min(duration * 0.5, max(0.0, duration - 0.1))]
    step = duration / (count + 1)
    return [step * i for i in range(1, count + 1)]


def merge_times(scene_times: list[float], sample_times: list[float], duration: float, max_frames: int) -> list[float]:
    merged: list[float] = []
    for value in sorted(scene_times + sample_times):
        if value < 0 or (duration and value > duration):
            continue
        if not merged or abs(value - merged[-1]) >= 0.35:
            merged.append(value)
    if len(merged) <= max_frames:
        return merged
    # Keep evenly spaced frames if the video produces too many cuts.
    indexes = [round(i * (len(merged) - 1) / (max_frames - 1)) for i in range(max_frames)]
    return [merged[i] for i in sorted(set(indexes))]


def extract_frame(path: Path, seconds: float, width: int, output: Path) -> None:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{seconds:.3f}", "-i", str(path),
        "-frames:v", "1", "-vf", f"scale={width}:-2",
        "-q:v", "3", str(output),
    ]
    run(cmd)


def build_contact_sheet(frames: list[Path], output: Path, columns: int = 6) -> bool:
    if not frames:
        return False
    rows = max(1, math.ceil(len(frames) / columns))
    # tile fills remaining cells with the padding colour.
    vf = f"scale=320:-1,tile={columns}x{rows}:padding=6:margin=6:color=white"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-pattern_type", "glob", "-i", str(frames[0].parent / "frame-*.jpg"),
        "-vf", vf, "-frames:v", "1", str(output),
    ]
    proc = run(cmd, check=False)
    return proc.returncode == 0 and output.exists()


def make_video_palette(path: Path, duration: float, output: Path) -> bool:
    fps = "1" if duration <= 60 else "1/5"
    vf = f"fps={fps},scale=200:-1:flags=lanczos,palettegen=max_colors=8:stats_mode=full"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(path), "-vf", vf, "-frames:v", "1", str(output),
    ]
    proc = run(cmd, check=False)
    return proc.returncode == 0 and output.exists()


def make_image_palette(path: Path, output: Path) -> bool:
    vf = "format=rgb24,scale=200:-1:flags=lanczos,palettegen=max_colors=8"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(path), "-vf", vf, "-frames:v", "1", str(output),
    ]
    proc = run(cmd, check=False)
    return proc.returncode == 0 and output.exists()


def make_waveform(path: Path, output: Path) -> bool:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(path),
        "-filter_complex", "showwavespic=s=1200x240:colors=white",
        "-frames:v", "1", str(output),
    ]
    proc = run(cmd, check=False)
    return proc.returncode == 0 and output.exists()


def write_contact_index(frame_times: list[float], frame_paths: list[Path], output: Path, columns: int = 6) -> None:
    lines = [
        "# 联系表索引",
        "",
        f"联系表每行 {columns} 格，从左到右、从上到下。",
        "",
        "| 格 | 文件 | 时间码 |",
        "| --- | --- | --- |",
    ]
    for index, (seconds, path) in enumerate(zip(frame_times, frame_paths), start=1):
        lines.append(f"| {index} | {path.name} | {format_timecode(seconds)} |")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", path.stem).strip("-")
    return stem or "input"


def process_image(path: Path, out_dir: Path, max_side: int) -> dict:
    info = ffprobe_json(path)
    video = pick_video_stream(info) or {}
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    preview = out_dir / f"{safe_stem(path)}-preview.jpg"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(path),
        "-vf", f"scale={max_side}:{max_side}:force_original_aspect_ratio=decrease",
        "-q:v", "3", str(preview),
    ]
    run(cmd)
    palette = out_dir / "palette.png"
    has_palette = make_image_palette(path, palette)
    result = {
        "input": str(path),
        "type": "image",
        "width": width,
        "height": height,
        "preview": str(preview),
        "palette": str(palette) if has_palette else None,
        "streams": info.get("streams", []),
    }
    return result


def process_video(path: Path, out_dir: Path, args: argparse.Namespace) -> dict:
    info = ffprobe_json(path)
    video = pick_video_stream(info) or {}
    audio = pick_audio_stream(info)
    duration = media_duration(info)
    fps = parse_rate(video.get("avg_frame_rate")) or parse_rate(video.get("r_frame_rate"))
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)

    scene_times: list[float] = []
    if not args.no_scene and duration > 0:
        scene_times = detect_scenes(path, args.scene_threshold)

    interval = args.interval
    if interval is None:
        interval = max(1.0, min(30.0, duration / 24)) if duration else 1.0
    sample_count = max(1, min(args.max_frames, int(duration / interval) if duration else 1))
    samples = uniform_times(duration, sample_count)
    frame_times = merge_times(scene_times, samples, duration, args.max_frames)

    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("frame-*.jpg"):
        old.unlink()

    frame_paths: list[Path] = []
    extracted_times: list[float] = []
    for index, seconds in enumerate(frame_times, start=1):
        output = frames_dir / f"frame-{index:03d}-{format_timecode(seconds)}.jpg"
        try:
            extract_frame(path, seconds, args.frame_width, output)
        except subprocess.CalledProcessError:
            continue
        if output.exists():
            frame_paths.append(output)
            extracted_times.append(seconds)
            print(f"[frame] {format_timecode(seconds)} -> {output.name}")

    contact_sheet = out_dir / "contact-sheet.jpg"
    has_contact = build_contact_sheet(frame_paths, contact_sheet)
    contact_index = out_dir / "contact-sheet-index.md"
    if has_contact:
        write_contact_index(extracted_times, frame_paths, contact_index)

    palette = out_dir / "palette.png"
    has_palette = False if args.no_palette else make_video_palette(path, duration, palette)

    waveform = out_dir / "waveform.png"
    has_waveform = False
    if audio and not args.no_waveform:
        has_waveform = make_waveform(path, waveform)

    result = {
        "input": str(path),
        "type": "video",
        "duration_seconds": round(duration, 3),
        "width": width,
        "height": height,
        "fps": round(fps, 3) if fps else None,
        "video_codec": video.get("codec_name"),
        "bitrate": info.get("format", {}).get("bit_rate"),
        "audio": {
            "codec": audio.get("codec_name"),
            "sample_rate": audio.get("sample_rate"),
            "channels": audio.get("channels"),
        } if audio else None,
        "scene_threshold": args.scene_threshold,
        "scene_count": len(scene_times),
        "scene_times": [round(value, 3) for value in scene_times],
        "frame_times": [round(value, 3) for value in extracted_times],
        "frames": [str(item) for item in frame_paths],
        "contact_sheet": str(contact_sheet) if has_contact else None,
        "contact_sheet_index": str(contact_index) if has_contact else None,
        "palette": str(palette) if has_palette else None,
        "waveform": str(waveform) if has_waveform else None,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract analysis frames / previews from video and image files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("inputs", nargs="+", help="video or image files")
    parser.add_argument("--out", help="output directory")
    parser.add_argument("--max-frames", type=int, default=36, help="cap on extracted video frames")
    parser.add_argument("--interval", type=float, default=None, help="seconds between uniform samples")
    parser.add_argument("--scene-threshold", type=float, default=0.3, help="ffmpeg scene score threshold, 0-1")
    parser.add_argument("--frame-width", type=int, default=640, help="width of extracted frames")
    parser.add_argument("--max-side", type=int, default=1080, help="longest side of image previews")
    parser.add_argument("--no-scene", action="store_true", help="skip scene detection")
    parser.add_argument("--no-palette", action="store_true", help="skip palette generation")
    parser.add_argument("--no-waveform", action="store_true", help="skip audio waveform")
    args = parser.parse_args()

    require_tools()

    results = []
    multi = len(args.inputs) > 1
    base_out = Path(args.out).expanduser().resolve() if args.out else None
    for input_index, raw in enumerate(args.inputs, start=1):
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            die(f"not found: {path}")
        if path.is_dir():
            die(f"directories are not supported; pass files: {path}")

        suffix = path.suffix.lower()
        if suffix in IMAGE_EXT:
            kind = "image"
        elif suffix in VIDEO_EXT:
            kind = "video"
        else:
            probe = ffprobe_json(path)
            kind = "video" if pick_video_stream(probe) else "image"

        if base_out and multi:
            out_dir = base_out / f"{input_index:02d}-{safe_stem(path)}"
        elif base_out:
            out_dir = base_out
        elif multi:
            out_dir = path.parent / f"{input_index:02d}-{safe_stem(path)}-decode"
        else:
            out_dir = path.parent / f"{safe_stem(path)}-decode"
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"[input] {path} ({kind})")
        if kind == "image":
            result = process_image(path, out_dir, args.max_side)
            print(f"[ok] image {result['width']}x{result['height']}")
            print(f"     preview: {result['preview']}")
            if result["palette"]:
                print(f"     palette: {result['palette']}")
        else:
            result = process_video(path, out_dir, args)
            print(f"[ok] video {result['duration_seconds']}s, {result['width']}x{result['height']}, {result['fps']}fps")
            print(f"     frames: {len(result['frames'])}")
            if result["contact_sheet"]:
                print(f"     contact sheet: {result['contact_sheet']}")
                print(f"     index: {result['contact_sheet_index']}")
            if result["palette"]:
                print(f"     palette: {result['palette']}")
            if result["waveform"]:
                print(f"     waveform: {result['waveform']}")

        results.append(result)
        metadata_path = out_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"     metadata: {metadata_path}")

    if len(results) > 1:
        if base_out:
            combined = base_out / "combined-metadata.json"
        else:
            combined = Path(args.inputs[0]).expanduser().resolve().parent / "combined-metadata.json"
        combined.parent.mkdir(parents=True, exist_ok=True)
        combined.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] combined metadata: {combined}")


if __name__ == "__main__":
    main()
