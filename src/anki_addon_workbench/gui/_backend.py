"""pyautogui + Pillow backed primitives.

Heavy GUI dependencies (pyautogui, Pillow) are imported lazily so that the
core smoke/profile tooling, ``doctor`` reporting, and the unit tests do not
require a display server or the optional ``[gui]`` extra to be installed.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from .models import ActiveWindow, Marker, PointerLocation

_GUI_EXTRA_HINT = (
    "pyautogui and Pillow are required for GUI commands. "
    "Install them with: pip install 'anki-addon-workbench[gui]' "
    "(or: uv add 'anki-addon-workbench[gui]')."
)


def pyautogui_available() -> bool:
    return importlib.util.find_spec("pyautogui") is not None


def pillow_available() -> bool:
    return importlib.util.find_spec("PIL") is not None


def load_pyautogui() -> Any:
    if not (pyautogui_available() and pillow_available()):
        raise RuntimeError(_GUI_EXTRA_HINT)
    try:
        import pyautogui  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - depends on display/runtime
        raise RuntimeError(
            f"failed to initialize pyautogui (is DISPLAY set on this platform?): {exc}"
        ) from exc
    # Agents drive this headlessly; the corner-abort failsafe and per-call pause
    # are counterproductive and slow.
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0
    return pyautogui


def button_name(button: int) -> str:
    return {1: "left", 2: "middle", 3: "right"}.get(int(button), "left")


def position() -> PointerLocation:
    pyautogui = load_pyautogui()
    point = pyautogui.position()
    return PointerLocation(x=int(point.x), y=int(point.y))


def active_window() -> ActiveWindow:
    xdotool = shutil.which("xdotool")
    if not xdotool or not os.environ.get("DISPLAY"):
        return ActiveWindow(id=None, name=None)
    try:
        result = subprocess.run(
            [xdotool, "getactivewindow"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            return ActiveWindow(id=None, name=None)
        window_id = int(result.stdout.strip())
        name_result = subprocess.run(
            [xdotool, "getwindowname", str(window_id)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        name = name_result.stdout.strip() if name_result.returncode == 0 else None
        return ActiveWindow(id=window_id, name=name)
    except (ValueError, OSError):
        return ActiveWindow(id=None, name=None)


def move(x: int, y: int) -> PointerLocation:
    pyautogui = load_pyautogui()
    pyautogui.moveTo(int(x), int(y))
    return position()


def drag(x: int, y: int, *, duration: float = 0.5, button: int = 1) -> PointerLocation:
    pyautogui = load_pyautogui()
    pyautogui.dragTo(
        int(x),
        int(y),
        duration=max(0.0, float(duration)),
        button=button_name(button),
    )
    return position()


def path(
    points: list[tuple[int, int]],
    *,
    duration: float = 1.0,
    button: int = 1,
) -> PointerLocation:
    if not points:
        raise ValueError("path requires at least one point")
    pyautogui = load_pyautogui()
    per_point_duration = max(0.0, float(duration)) / max(1, len(points))
    pyautogui.mouseDown(button=button_name(button))
    try:
        for x, y in points:
            pyautogui.moveTo(int(x), int(y), duration=per_point_duration)
    finally:
        pyautogui.mouseUp(button=button_name(button))
    return position()


def click(button: int = 1) -> dict[str, Any]:
    pyautogui = load_pyautogui()
    before = position()
    pyautogui.click(button=button_name(button))
    after = position()
    return {
        "button": int(button),
        "before": before.to_json(),
        "after": after.to_json(),
    }


def _normalize_key(name: str) -> str:
    return name.strip().lower()


def press_key(name: str) -> None:
    pyautogui = load_pyautogui()
    if "+" in name and len(name) > 1:
        parts = [_normalize_key(part) for part in name.split("+") if part.strip()]
        pyautogui.hotkey(*parts)
    else:
        pyautogui.press(_normalize_key(name))


def type_text(text: str) -> None:
    pyautogui = load_pyautogui()
    pyautogui.write(text)


def _load_font() -> Any:
    from PIL import ImageFont  # noqa: PLC0415

    for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttf"):
        try:
            return ImageFont.truetype(name, 12)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_marker(image: Any, marker: Marker) -> None:
    """Draw a high-contrast synthetic cursor marker onto a Pillow image.

    Headless screenshots do not include the real X cursor, so the marker is
    drawn explicitly at the pointer (or an override) location.
    """
    from PIL import ImageDraw  # noqa: PLC0415

    draw = ImageDraw.Draw(image)
    half = marker.size // 2
    for width, color in ((7, "#000000"), (4, "#ffea00"), (2, "#ff00ff")):
        draw.line(
            (marker.x - marker.size, marker.y, marker.x + marker.size, marker.y),
            fill=color,
            width=width,
        )
        draw.line(
            (marker.x, marker.y - marker.size, marker.x, marker.y + marker.size),
            fill=color,
            width=width,
        )
        draw.ellipse(
            (marker.x - half, marker.y - half, marker.x + half, marker.y + half),
            outline=color,
            width=width,
        )

    label = marker.label or f"x={marker.x} y={marker.y}"
    font = _load_font()
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    text_width = right - left
    text_height = bottom - top
    box_width = text_width + 12
    box_height = text_height + 8
    image_width, image_height = image.size
    label_x = min(max(0, marker.x + marker.size + 8), max(0, image_width - box_width - 1))
    label_y = min(max(0, marker.y - box_height - 8), max(0, image_height - box_height - 1))
    draw.rectangle(
        (label_x, label_y, label_x + box_width, label_y + box_height),
        fill="#fff8bf",
        outline="#000000",
        width=1,
    )
    draw.text((label_x + 6, label_y + 4 - top), label, fill="#000000", font=font)


def _capture_image_linux() -> Any:
    """Capture the X11 root window without going through pyscreeze.

    pyscreeze chooses its screenshot tool from ``XDG_SESSION_TYPE``, which is
    unset under Xvfb -- so it ignores an installed ``scrot`` and insists on
    gnome-screenshot. We instead use Pillow's native XCB grab (no external tool),
    falling back to ``scrot`` directly if this Pillow build lacks XCB support.
    """
    from PIL import Image, ImageGrab  # noqa: PLC0415

    display = os.environ.get("DISPLAY")
    if not display:
        raise RuntimeError("DISPLAY is not set; cannot capture a screenshot on Linux.")

    try:
        return ImageGrab.grab(xdisplay=display)
    except Exception:  # noqa: BLE001 - fall back to scrot on any XCB issue
        pass

    scrot = shutil.which("scrot")
    if scrot is None:
        raise RuntimeError(
            "screenshot capture failed: this Pillow build lacks XCB support and "
            "scrot is not installed. Install scrot (e.g. `apt install scrot`)."
        )
    tmp_dir = tempfile.mkdtemp(prefix="aaw-shot-")
    tmp_path = os.path.join(tmp_dir, "shot.png")
    try:
        result = subprocess.run(
            [scrot, tmp_path],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0 or not os.path.exists(tmp_path):
            raise RuntimeError(f"scrot failed to capture the screen: {result.stderr.strip()}")
        return Image.open(tmp_path).copy()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def capture_image() -> Any:
    if not pillow_available():
        raise RuntimeError(_GUI_EXTRA_HINT)
    if sys.platform.startswith("linux"):
        image = _capture_image_linux()
    else:
        pyautogui = load_pyautogui()
        image = pyautogui.screenshot()
    return image.convert("RGB")
