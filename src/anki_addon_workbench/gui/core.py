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
    if width is not None:
        if width <= 0:
            raise ValueError("recording width must be positive")
        height = max(1, round(original_height * width / original_width))
        image = image.resize((width, height), Image.Resampling.LANCZOS)

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
            "24",
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


def record(
    out: str | Path,
    *,
    duration: float = 8.0,
    fps: int = 8,
    region: tuple[int, int, int, int] | None = None,
    width: int | None = 960,
    show_pointer: bool = True,
    meta: str | Path | None = None,
) -> JsonDict:
    if duration <= 0:
        raise ValueError("recording duration must be positive")
    if fps <= 0 or fps > 60:
        raise ValueError("recording fps must be between 1 and 60")

    output = Path(str(out))
    suffix = output.suffix.lower()
    if suffix not in {".gif", ".mp4"}:
        raise ValueError("recording output must end in .gif or .mp4")
    output.parent.mkdir(parents=True, exist_ok=True)

    frame_count = max(1, math.ceil(duration * fps))
    frames: list[Any] = []
    raw_path: Path | None = None
    raw_file = None
    started = time.monotonic()
    frame_size: tuple[int, int] | None = None
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
            if suffix == ".gif":
                frames.append(frame)
            else:
                assert raw_file is not None
                raw_file.write(frame.tobytes())

        assert frame_size is not None
        if suffix == ".gif":
            _write_gif(frames, output, fps=fps)
        else:
            assert raw_file is not None and raw_path is not None
            raw_file.flush()
            _write_mp4(
                raw_path,
                output,
                width=frame_size[0],
                height=frame_size[1],
                fps=fps,
            )
    finally:
        if raw_file is not None:
            raw_file.close()

    captured_seconds = time.monotonic() - started
    metadata: JsonDict = {
        "ok": True,
        "recording": str(output),
        "format": suffix.removeprefix("."),
        "duration": float(duration),
        "captured_seconds": captured_seconds,
        "fps": int(fps),
        "frames": frame_count,
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
        "ffmpeg": shutil.which("ffmpeg"),
        "captured_at": int(time.time()),
    }
    meta_path = Path(str(meta)) if meta else output.with_suffix(".json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    metadata["metadata"] = str(meta_path)
    return metadata
