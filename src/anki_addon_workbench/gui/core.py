from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from ..types import JsonDict
from . import _backend
from .models import Marker


def doctor() -> JsonDict:
    pyautogui = _backend.pyautogui_available()
    pillow = _backend.pillow_available()
    return {
        "ok": pyautogui and pillow,
        "platform": sys.platform,
        "display": os.environ.get("DISPLAY"),
        "pyautogui": pyautogui,
        "pillow": pillow,
        "xdotool": shutil.which("xdotool"),
    }


def location() -> JsonDict:
    return {
        "ok": True,
        "pointer": _backend.position().to_json(),
        "active_window": _backend.active_window().to_json(),
    }


def move(x: int, y: int) -> JsonDict:
    return {"ok": True, "location": _backend.move(x, y).to_json()}


def drag(x: int, y: int, *, duration: float = 0.5, button: int = 1) -> JsonDict:
    before = _backend.position()
    after = _backend.drag(x, y, duration=duration, button=button)
    return {
        "ok": True,
        "button": int(button),
        "duration": float(duration),
        "before": before.to_json(),
        "after": after.to_json(),
    }


def path(
    points: list[tuple[int, int]],
    *,
    duration: float = 1.0,
    button: int = 1,
) -> JsonDict:
    before = _backend.position()
    after = _backend.path(points, duration=duration, button=button)
    return {
        "ok": True,
        "button": int(button),
        "duration": float(duration),
        "points": [{"x": x, "y": y} for x, y in points],
        "before": before.to_json(),
        "after": after.to_json(),
    }


def click(button: int = 1, x: int | None = None, y: int | None = None) -> JsonDict:
    if (x is None) != (y is None):
        raise ValueError("x and y must be provided together")
    if x is not None and y is not None:
        _backend.move(x, y)
    return {"ok": True, **_backend.click(button)}


def key(keys: list[str]) -> JsonDict:
    for name in keys:
        _backend.press_key(name)
    return {"ok": True, "keys": keys}


def type_text(text: str) -> JsonDict:
    _backend.type_text(text)
    return {"ok": True, "text": text}


def screenshot(
    out: str | Path,
    *,
    meta: str | Path | None = None,
    mark: tuple[int, int] | None = None,
    label: str | None = None,
    marker_size: int = 22,
    no_marker: bool = False,
) -> JsonDict:
    pointer = _backend.position()
    image = _backend.capture_image()

    marker = None
    if not no_marker:
        marker_x, marker_y = mark if mark is not None else (pointer.x, pointer.y)
        marker = Marker(x=int(marker_x), y=int(marker_y), size=int(marker_size), label=label)
        _backend.draw_marker(image, marker)

    output = Path(str(out))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output), "PNG")

    width, height = image.size
    metadata: JsonDict = {
        "ok": True,
        "backend": "pyautogui",
        "display": os.environ.get("DISPLAY"),
        "screenshot": str(output),
        "marker": marker.to_json() if marker else None,
        "pointer": pointer.to_json(),
        "active_window": _backend.active_window().to_json(),
        "screen": {"x": 0, "y": 0, "width": int(width), "height": int(height)},
        "captured_at": int(time.time()),
    }

    meta_path = Path(str(meta)) if meta else output.with_suffix(".json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    metadata["metadata"] = str(meta_path)
    return metadata


def _prepare_recording_frame(
    image: Any,
    *,
    region: tuple[int, int, int, int] | None,
    width: int | None,
    show_pointer: bool,
) -> Any:
    from PIL import Image, ImageDraw  # noqa: PLC0415

    region_x = 0
    region_y = 0
    if region is not None:
        region_x, region_y, region_width, region_height = region
        if region_width <= 0 or region_height <= 0:
            raise ValueError("recording region width and height must be positive")
        image = image.crop(
            (
                region_x,
                region_y,
                region_x + region_width,
                region_y + region_height,
            )
        )

    original_width, original_height = image.size
    if width is not None and width < original_width:
        if width <= 0:
            raise ValueError("recording width must be positive")
        height = max(1, round(original_height * width / original_width))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    elif width is not None and width <= 0:
        raise ValueError("recording width must be positive")

    if show_pointer:
        pointer = _backend.position()
        scale = image.size[0] / original_width
        x = round((pointer.x - region_x) * scale)
        y = round((pointer.y - region_y) * scale)
        if 0 <= x < image.size[0] and 0 <= y < image.size[1]:
            draw = ImageDraw.Draw(image)
            radius = max(5, round(8 * scale))
            for stroke, color in ((6, "#ffffff"), (3, "#b3122f")):
                draw.ellipse(
                    (x - radius, y - radius, x + radius, y + radius),
                    outline=color,
                    width=stroke,
                )
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill="#b3122f")
    return image.convert("RGB")


def _write_gif(frames: list[Any], output: Path, *, fps: int) -> None:
    from PIL import Image  # noqa: PLC0415

    palette_frames = [
        frame.quantize(colors=160, method=Image.Quantize.MEDIANCUT) for frame in frames
    ]
    duration_ms = max(20, round(1000 / fps))
    palette_frames[0].save(
        output,
        "GIF",
        save_all=True,
        append_images=palette_frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )


def _write_mp4(
    raw_path: Path,
    output: Path,
    *,
    width: int,
    height: int,
    fps: int,
    crf: int,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            "MP4 recording requires ffmpeg on PATH. GIF recording works with "
            "the existing [gui] extra alone."
        )
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgb24",
            "-video_size",
            f"{width}x{height}",
            "-framerate",
            str(fps),
            "-i",
            str(raw_path),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to encode MP4: {result.stderr.strip()}")


def _write_gif_from_raw(
    raw_path: Path,
    output: Path,
    *,
    width: int,
    height: int,
    fps: int,
    gif_width: int,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("secondary GIF recording requires ffmpeg on PATH")
    gif_fps = min(fps, 12)
    scale = f"scale=min(iw\\,{gif_width}):-2:flags=lanczos"
    filter_complex = (
        f"[0:v]fps={gif_fps},{scale},split[s0][s1];"
        "[s0]palettegen=max_colors=160[p];"
        "[s1][p]paletteuse=dither=bayer:bayer_scale=3"
    )
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgb24",
            "-video_size",
            f"{width}x{height}",
            "-framerate",
            str(fps),
            "-i",
            str(raw_path),
            "-filter_complex",
            filter_complex,
            "-loop",
            "0",
            str(output),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to encode GIF: {result.stderr.strip()}")


def _motion_score(previous: Any, current: Any) -> float:
    from PIL import ImageChops, ImageStat  # noqa: PLC0415

    difference = ImageChops.difference(previous, current)
    return float(ImageStat.Stat(difference).mean[0])


def _trim_range(
    fingerprints: list[Any],
    *,
    fps: int,
    threshold: float = 0.8,
) -> tuple[int, int, list[float]]:
    scores = [
        _motion_score(previous, current)
        for previous, current in zip(fingerprints, fingerprints[1:], strict=False)
    ]
    active = [index + 1 for index, score in enumerate(scores) if score >= threshold]
    if not active:
        return (0, len(fingerprints) - 1, scores)
    lead = max(1, round(0.45 * fps))
    trail = max(1, round(0.8 * fps))
    return (
        max(0, active[0] - lead),
        min(len(fingerprints) - 1, active[-1] + trail),
        scores,
    )


def _copy_raw_range(
    source: Path,
    destination: Path,
    *,
    frame_bytes: int,
    start_frame: int,
    end_frame: int,
) -> None:
    frames = end_frame - start_frame + 1
    with source.open("rb") as input_file, destination.open("wb") as output_file:
        input_file.seek(start_frame * frame_bytes)
        remaining = frames * frame_bytes
        while remaining:
            chunk = input_file.read(min(1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError("raw recording ended before the requested frame range")
            output_file.write(chunk)
            remaining -= len(chunk)


def record(
    out: str | Path,
    *,
    duration: float = 8.0,
    fps: int = 8,
    region: tuple[int, int, int, int] | None = None,
    width: int | None = None,
    show_pointer: bool = True,
    meta: str | Path | None = None,
    gif_out: str | Path | None = None,
    gif_width: int = 720,
    trim_idle: bool = False,
    crf: int = 20,
) -> JsonDict:
    if duration <= 0:
        raise ValueError("recording duration must be positive")
    if fps <= 0 or fps > 60:
        raise ValueError("recording fps must be between 1 and 60")

    output = Path(str(out))
    suffix = output.suffix.lower()
    if suffix not in {".gif", ".mp4"}:
        raise ValueError("recording output must end in .gif or .mp4")
    if gif_out is not None and suffix != ".mp4":
        raise ValueError("secondary GIF output requires an MP4 primary output")
    if gif_width <= 0:
        raise ValueError("GIF width must be positive")
    if crf < 0 or crf > 51:
        raise ValueError("MP4 CRF must be between 0 and 51")
    output.parent.mkdir(parents=True, exist_ok=True)
    gif_output = Path(str(gif_out)) if gif_out is not None else None
    if gif_output is not None:
        if gif_output.suffix.lower() != ".gif":
            raise ValueError("secondary GIF output must end in .gif")
        gif_output.parent.mkdir(parents=True, exist_ok=True)

    frame_count = max(1, math.ceil(duration * fps))
    frames: list[Any] = []
    fingerprints: list[Any] = []
    raw_path: Path | None = None
    raw_file = None
    trimmed_raw_path: Path | None = None
    started = time.monotonic()
    frame_size: tuple[int, int] | None = None
    start_frame = 0
    end_frame = frame_count - 1
    motion_scores: list[float] = []
    try:
        if suffix == ".mp4":
            raw_file = tempfile.NamedTemporaryFile(prefix="aaw-record-", suffix=".rgb")
            raw_path = Path(raw_file.name)

        for frame_index in range(frame_count):
            target_time = started + frame_index / fps
            remaining = target_time - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            frame = _prepare_recording_frame(
                _backend.capture_image(),
                region=region,
                width=width,
                show_pointer=show_pointer,
            )
            if frame_size is None:
                frame_size = frame.size
            elif frame.size != frame_size:
                raise RuntimeError("screen dimensions changed during recording")
            if trim_idle:
                fingerprints.append(
                    frame.resize((64, 64)).convert("L")
                )
            if suffix == ".gif":
                frames.append(frame)
            else:
                assert raw_file is not None
                raw_file.write(frame.tobytes())

        assert frame_size is not None
        if trim_idle:
            start_frame, end_frame, motion_scores = _trim_range(
                fingerprints,
                fps=fps,
            )
        if suffix == ".gif":
            _write_gif(frames[start_frame : end_frame + 1], output, fps=fps)
        else:
            assert raw_file is not None and raw_path is not None
            raw_file.flush()
            encode_path = raw_path
            if start_frame != 0 or end_frame != frame_count - 1:
                frame_bytes = frame_size[0] * frame_size[1] * 3
                trimmed_raw = tempfile.NamedTemporaryFile(
                    prefix="aaw-record-trimmed-",
                    suffix=".rgb",
                    delete=False,
                )
                trimmed_raw_path = Path(trimmed_raw.name)
                trimmed_raw.close()
                _copy_raw_range(
                    raw_path,
                    trimmed_raw_path,
                    frame_bytes=frame_bytes,
                    start_frame=start_frame,
                    end_frame=end_frame,
                )
                encode_path = trimmed_raw_path
            _write_mp4(
                encode_path,
                output,
                width=frame_size[0],
                height=frame_size[1],
                fps=fps,
                crf=crf,
            )
            if gif_output is not None:
                _write_gif_from_raw(
                    encode_path,
                    gif_output,
                    width=frame_size[0],
                    height=frame_size[1],
                    fps=fps,
                    gif_width=gif_width,
                )
    finally:
        if raw_file is not None:
            raw_file.close()
        if trimmed_raw_path is not None:
            trimmed_raw_path.unlink(missing_ok=True)

    captured_seconds = time.monotonic() - started
    encoded_frames = end_frame - start_frame + 1
    metadata: JsonDict = {
        "ok": True,
        "recording": str(output),
        "format": suffix.removeprefix("."),
        "duration": float(duration),
        "encoded_duration": encoded_frames / fps,
        "captured_seconds": captured_seconds,
        "fps": int(fps),
        "frames": frame_count,
        "encoded_frames": encoded_frames,
        "region": (
            {"x": region[0], "y": region[1], "width": region[2], "height": region[3]}
            if region is not None
            else None
        ),
        "screen": {
            "width": int(frame_size[0]),
            "height": int(frame_size[1]),
        },
        "show_pointer": bool(show_pointer),
        "trim_idle": bool(trim_idle),
        "trim": {
            "start_frame": start_frame,
            "end_frame": end_frame,
            "motion_transitions": sum(score >= 0.8 for score in motion_scores),
            "max_motion_score": max(motion_scores, default=0.0),
        },
        "gif": str(gif_output) if gif_output is not None else None,
        "gif_width": int(gif_width) if gif_output is not None else None,
        "crf": int(crf) if suffix == ".mp4" else None,
        "ffmpeg": shutil.which("ffmpeg"),
        "captured_at": int(time.time()),
    }
    meta_path = Path(str(meta)) if meta else output.with_suffix(".json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    metadata["metadata"] = str(meta_path)
    return metadata
