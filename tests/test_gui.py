"""Unit tests for the GUI primitives.

The pyautogui-driving tests inject a fake backend so they run anywhere, with no
display and without pyautogui installed. The image tests need Pillow (the `[gui]`
extra) and skip cleanly otherwise. The real-display path is covered separately by
``test_gui_xvfb.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anki_addon_workbench.gui import _backend, core
from anki_addon_workbench.gui.models import ActiveWindow, Marker, PointerLocation

_needs_pillow = pytest.mark.skipif(
    not _backend.pillow_available(), reason="Pillow ([gui] extra) not installed"
)


class _Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class _FakePyAutoGui:
    """Records calls and tracks a fake pointer, standing in for pyautogui."""

    def __init__(self) -> None:
        self.events: list[tuple] = []
        self._pos = _Point(0, 0)

    def moveTo(self, x: int, y: int, duration: float = 0.0) -> None:
        self._pos = _Point(x, y)
        self.events.append(("moveTo", x, y, duration))

    def dragTo(
        self, x: int, y: int, duration: float = 0.0, button: str = "left"
    ) -> None:
        self._pos = _Point(x, y)
        self.events.append(("dragTo", x, y, duration, button))

    def mouseDown(self, button: str = "left") -> None:
        self.events.append(("mouseDown", button))

    def mouseUp(self, button: str = "left") -> None:
        self.events.append(("mouseUp", button))

    def position(self) -> _Point:
        return self._pos

    def click(self, button: str = "left") -> None:
        self.events.append(("click", button))

    def press(self, key: str) -> None:
        self.events.append(("press", key))

    def hotkey(self, *keys: str) -> None:
        self.events.append(("hotkey", keys))

    def write(self, text: str) -> None:
        self.events.append(("write", text))


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> _FakePyAutoGui:
    stub = _FakePyAutoGui()
    monkeypatch.setattr(_backend, "load_pyautogui", lambda: stub)
    monkeypatch.setattr(_backend, "active_window", lambda: ActiveWindow(id=None, name=None))
    return stub


def test_button_name_maps_and_defaults() -> None:
    assert _backend.button_name(1) == "left"
    assert _backend.button_name(2) == "middle"
    assert _backend.button_name(3) == "right"
    assert _backend.button_name(99) == "left"


def test_move_reports_new_location(fake: _FakePyAutoGui) -> None:
    out = core.move(10, 20)
    assert out["location"] == {"x": 10, "y": 20, "screen": 0, "window": 0}
    assert ("moveTo", 10, 20, 0.0) in fake.events


def test_click_moves_then_clicks(fake: _FakePyAutoGui) -> None:
    out = core.click(1, x=5, y=6)
    assert out["ok"] is True
    assert ("moveTo", 5, 6, 0.0) in fake.events
    assert ("click", "left") in fake.events
    assert out["after"] == {"x": 5, "y": 6, "screen": 0, "window": 0}


def test_click_requires_both_coordinates(fake: _FakePyAutoGui) -> None:
    with pytest.raises(ValueError, match="x and y must be provided together"):
        core.click(1, x=5)


def test_drag_reports_destination(fake: _FakePyAutoGui) -> None:
    out = core.drag(30, 40, duration=0.25, button=1)
    assert out["after"]["x"] == 30
    assert ("dragTo", 30, 40, 0.25, "left") in fake.events


def test_path_holds_button_through_points(fake: _FakePyAutoGui) -> None:
    out = core.path([(10, 20), (30, 40)], duration=0.4, button=1)
    assert out["after"]["x"] == 30
    assert fake.events[0] == ("mouseDown", "left")
    assert ("moveTo", 10, 20, 0.2) in fake.events
    assert fake.events[-1] == ("mouseUp", "left")


def test_record_actions_run_inside_capture_process(
    fake: _FakePyAutoGui, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(core.time, "sleep", lambda _seconds: None)
    errors: list[BaseException] = []

    core._run_record_actions(
        [
            {"at": 0, "type": "move", "x": 10, "y": 20},
            {"at": 0, "type": "drag", "x": 30, "y": 40, "duration": 0.25},
            {"at": 0, "type": "click", "x": 50, "y": 60},
        ],
        started=core.time.monotonic(),
        errors=errors,
    )

    assert errors == []
    assert ("moveTo", 10, 20, 0.0) in fake.events
    assert ("dragTo", 30, 40, 0.25, "left") in fake.events
    assert ("moveTo", 50, 60, 0.0) in fake.events
    assert ("click", "left") in fake.events


def test_key_normalizes_and_splits_chords(fake: _FakePyAutoGui) -> None:
    core.key(["Escape", "ctrl+a"])
    assert ("press", "escape") in fake.events
    assert ("hotkey", ("ctrl", "a")) in fake.events


def test_type_text_writes(fake: _FakePyAutoGui) -> None:
    core.type_text("hello")
    assert ("write", "hello") in fake.events


def test_doctor_reports_availability_flags() -> None:
    report = core.doctor()
    assert {"ok", "platform", "display", "pyautogui", "pillow", "xdotool"} <= report.keys()
    assert isinstance(report["pyautogui"], bool)
    assert isinstance(report["pillow"], bool)


@_needs_pillow
def test_draw_marker_changes_pixels_and_clamps_at_edges() -> None:
    from PIL import Image

    image = Image.new("RGB", (80, 60), "#3366aa")
    before = image.tobytes()
    _backend.draw_marker(image, Marker(x=40, y=30, size=10, label="center"))
    assert image.tobytes() != before
    # A near-corner marker must not raise when the label box would overflow.
    _backend.draw_marker(image, Marker(x=78, y=2, size=10))


@_needs_pillow
def test_screenshot_writes_png_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import Image

    monkeypatch.setattr(_backend, "capture_image", lambda: Image.new("RGB", (120, 90), "#202020"))
    monkeypatch.setattr(_backend, "position", lambda: PointerLocation(x=10, y=12))
    monkeypatch.setattr(_backend, "active_window", lambda: ActiveWindow(id=None, name=None))

    out = tmp_path / "shot.png"
    meta = tmp_path / "shot.json"
    result = core.screenshot(out, meta=meta, label="hi")

    assert result["ok"] is True
    assert result["screen"]["width"] == 120 and result["screen"]["height"] == 90
    assert out.exists() and meta.exists()

    data = json.loads(meta.read_text(encoding="utf-8"))
    assert data["marker"]["label"] == "hi"
    assert Image.open(out).size == (120, 90)


@_needs_pillow
def test_screenshot_no_marker_skips_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import Image

    monkeypatch.setattr(_backend, "capture_image", lambda: Image.new("RGB", (40, 40), "#000"))
    monkeypatch.setattr(_backend, "position", lambda: PointerLocation(x=1, y=1))
    monkeypatch.setattr(_backend, "active_window", lambda: ActiveWindow(id=None, name=None))

    result = core.screenshot(tmp_path / "s.png", no_marker=True)
    assert result["marker"] is None


@_needs_pillow
def test_record_writes_animated_gif(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import Image

    colors = iter(("#112233", "#334455"))
    monkeypatch.setattr(
        _backend,
        "capture_image",
        lambda: Image.new("RGB", (80, 60), next(colors)),
    )
    monkeypatch.setattr(_backend, "position", lambda: PointerLocation(x=10, y=12))
    monkeypatch.setattr(core.time, "sleep", lambda _seconds: None)

    result = core.record(
        tmp_path / "demo.gif",
        duration=1.0,
        fps=2,
        width=40,
        show_pointer=False,
    )

    assert result["ok"] is True
    assert result["frames"] == 2
    gif = Image.open(tmp_path / "demo.gif")
    assert gif.size == (40, 30)
    assert getattr(gif, "n_frames", 1) == 2


@_needs_pillow
def test_record_does_not_upscale_and_can_trim_idle_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import Image

    colors = iter(("#111111", "#111111", "#111111", "#eeeeee", "#eeeeee", "#eeeeee"))
    monkeypatch.setattr(
        _backend,
        "capture_image",
        lambda: Image.new("RGB", (80, 60), next(colors)),
    )
    monkeypatch.setattr(_backend, "position", lambda: PointerLocation(x=10, y=12))
    monkeypatch.setattr(core.time, "sleep", lambda _seconds: None)

    result = core.record(
        tmp_path / "trimmed.gif",
        duration=3.0,
        fps=2,
        width=160,
        show_pointer=False,
        trim_idle=True,
    )

    assert result["screen"] == {"width": 80, "height": 60}
    assert result["trim"]["motion_transitions"] == 1
    assert result["encoded_frames"] < result["frames"]
    assert Image.open(tmp_path / "trimmed.gif").size == (80, 60)
