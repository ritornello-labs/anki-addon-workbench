from __future__ import annotations

from pathlib import Path

from anki_addon_workbench.config import WorkbenchConfig
from anki_addon_workbench.dockerfile import (
    render_android_dockerfile,
    render_dockerfile,
    write_dockerfile,
)


def _config(root: Path, **overrides: object) -> WorkbenchConfig:
    params: dict[str, object] = dict(
        root=root,
        config_file=root / "pyproject.toml",
        project_name="Fixture",
        addon_package="fixture_addon",
        source_root=root,
        include=(),
        exclude=(),
    )
    params.update(overrides)
    return WorkbenchConfig(**params)  # type: ignore[arg-type]


def test_render_includes_anki_version_and_runtime_tools(tmp_path: Path) -> None:
    text = render_dockerfile(_config(tmp_path, anki_version="25.09"))

    assert "ARG ANKI_LAUNCHER_VERSION=25.09" in text
    assert 'ARG ANKI_ADDON_WORKBENCH_SPEC="anki-addon-workbench[gui]"' in text
    assert "libxi6" in text
    assert "xdotool" in text
    assert "xvfb" in text
    assert "ffmpeg" in text
    assert "python3-tk" in text
    # GUI backend deps arrive through the published workbench package.
    assert 'pip3 install --break-system-packages --no-cache-dir "${ANKI_ADDON_WORKBENCH_SPEC}"' in text
    assert "scrot" in text
    assert "ENV ANKI_BIN=" in text
    # The image must be standalone; no sibling checkout or source path is required.
    assert "PYTHONPATH" not in text
    assert "gui-agent-workbench" not in text
    assert "/workspace/anki-addon-workbench/src" not in text


def test_render_allows_workbench_package_spec_override(tmp_path: Path) -> None:
    text = render_dockerfile(
        _config(tmp_path),
        workbench_spec="anki-addon-workbench[gui]==0.2.1.dev0",
    )

    assert 'ARG ANKI_ADDON_WORKBENCH_SPEC="anki-addon-workbench[gui]==0.2.1.dev0"' in text


def test_render_android_dockerfile_includes_emulator_tooling(tmp_path: Path) -> None:
    text = render_android_dockerfile(
        _config(tmp_path),
        workbench_spec="anki-addon-workbench==0.5.0",
        ankidroid_apk_url="https://example.test/AnkiDroid.apk",
    )

    assert "FROM ubuntu:24.04" in text
    assert "platform-tools" in text
    assert "system-images;android-${ANDROID_API_LEVEL};google_apis" in text
    assert 'ARG ANKI_ADDON_WORKBENCH_SPEC="anki-addon-workbench==0.5.0"' in text
    assert 'ARG ANKIDROID_APK_URL="https://example.test/AnkiDroid.apk"' in text
    assert "android-smoke --start-emulator" in text


def test_render_can_install_local_workbench_wheel(tmp_path: Path) -> None:
    text = render_dockerfile(
        _config(tmp_path),
        local_workbench_wheel="wheels/anki_addon_workbench-0.2.1-py3-none-any.whl",
    )

    assert (
        'COPY ["wheels/anki_addon_workbench-0.2.1-py3-none-any.whl", '
        '"/tmp/anki-addon-workbench/anki_addon_workbench-0.2.1-py3-none-any.whl"]'
    ) in text
    assert (
        'ARG ANKI_ADDON_WORKBENCH_SPEC='
        '"/tmp/anki-addon-workbench/anki_addon_workbench-0.2.1-py3-none-any.whl[gui]"'
    ) in text


def test_render_rejects_multiline_workbench_package_spec(tmp_path: Path) -> None:
    try:
        render_dockerfile(_config(tmp_path), workbench_spec="good\nbad")
    except ValueError as exc:
        assert "workbench_spec" in str(exc)
    else:
        raise AssertionError("expected multiline workbench spec to fail")


def test_render_rejects_unsafe_local_workbench_wheel_path(tmp_path: Path) -> None:
    try:
        render_dockerfile(_config(tmp_path), local_workbench_wheel="../wheel.whl")
    except ValueError as exc:
        assert "local_workbench_wheel" in str(exc)
    else:
        raise AssertionError("expected unsafe wheel path to fail")


def test_write_dockerfile_creates_parent_directory(tmp_path: Path) -> None:
    out = write_dockerfile(_config(tmp_path), tmp_path / "nested" / "Dockerfile")

    assert out.exists()
