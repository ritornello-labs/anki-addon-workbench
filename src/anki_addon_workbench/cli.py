from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import dockerfile, scaffold
from .android import DEFAULT_ANDROID_AVD, DEFAULT_CDP_PORT, run_android_smoke
from .config import WorkbenchConfig, load_config
from .local_docker import DEFAULT_LOCAL_DOCKER_ARTIFACT_DIR, run_docker_smoke_local
from .runner import DEFAULT_TIMEOUT_SECONDS, doctor, parse_pointer, run_launch, run_smoke
from .types import JsonDict
from .webkit import run_webkit_smoke


def _gui_core() -> Any:
    from .gui import core as gui_core

    return gui_core


def _parse_region(value: str) -> tuple[int, int, int, int]:
    parts = value.replace(",", " ").split()
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("region must be x,y,width,height")
    try:
        return tuple(int(part) for part in parts)  # type: ignore[return-value]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("region values must be integers") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Disposable Anki profile and GUI workbench tooling for add-on development."
    )
    parser.add_argument(
        "--config-root",
        default=".",
        help="directory to search for pyproject.toml or anki-workbench.toml",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="report config and backend availability")

    smoke = subparsers.add_parser("smoke", help="run configured Anki GUI smoke test")
    smoke.add_argument("--anki-bin")
    smoke.add_argument("--anki-python")
    smoke.add_argument("--base")
    smoke.add_argument("--keep", action="store_true")
    smoke.add_argument("--screenshot")
    smoke.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    smoke.add_argument("--no-direct-python", action="store_true")
    smoke.add_argument("--qt-platform")
    smoke.add_argument("--xvfb", action="store_true")
    smoke.add_argument("--display")
    smoke.add_argument("--screen", default="1280x1024x24")
    smoke.add_argument(
        "--allow-foreground",
        "--foreground",
        dest="allow_foreground",
        action="store_true",
        help="on macOS, do not ask Qt to avoid auto-activating the smoke Anki app",
    )

    webkit = subparsers.add_parser(
        "webkit-smoke",
        help="render built-in deck probe samples in Playwright WebKit",
    )
    webkit.add_argument("--anki-bin")
    webkit.add_argument("--anki-python")
    webkit.add_argument("--base")
    webkit.add_argument("--keep", action="store_true")
    webkit.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    webkit.add_argument("--no-direct-python", action="store_true")
    webkit.add_argument("--qt-platform")
    webkit.add_argument("--xvfb", action="store_true")
    webkit.add_argument("--display")
    webkit.add_argument("--screen", default="1280x1024x24")
    webkit.add_argument(
        "--allow-foreground",
        "--foreground",
        dest="allow_foreground",
        action="store_true",
        help="on macOS, do not ask Qt to avoid auto-activating the smoke Anki app",
    )
    webkit.add_argument(
        "--selector",
        action="append",
        dest="selectors",
        help="CSS selector that must become visible in every rendered card side",
    )
    webkit.add_argument(
        "--device",
        help='Playwright device profile to use (default: configured webkit_device, "iPhone 14")',
    )
    webkit.add_argument(
        "--render-timeout-ms",
        type=int,
        help="timeout for each WebKit render and selector assertion",
    )

    launch = subparsers.add_parser("launch", help="launch disposable Anki for agent GUI work")
    launch.add_argument("--anki-bin")
    launch.add_argument("--anki-python")
    launch.add_argument("--base")
    launch.add_argument("--keep", action="store_true")
    launch.add_argument("--artifact-dir", default=".tmp-gui-workbench")
    launch.add_argument("--workbench-python")
    launch.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    launch.add_argument("--no-direct-python", action="store_true")
    launch.add_argument("--xvfb", action="store_true")
    launch.add_argument("--display")
    launch.add_argument("--screen", default="1280x1024x24")
    launch.add_argument("--pointer", type=parse_pointer)
    launch.add_argument("--no-screenshot", action="store_true")
    launch.add_argument("--hold", action="store_true")
    launch.add_argument(
        "--allow-foreground",
        "--foreground",
        dest="allow_foreground",
        action="store_true",
        help="on macOS, let the launched Anki activate and stay on screen "
        "(default: stealth - no activation, window parked off-screen)",
    )

    screenshot = subparsers.add_parser("screenshot", help="capture a cursor-marked PNG")
    screenshot.add_argument("--out", required=True)
    screenshot.add_argument("--meta")
    screenshot.add_argument("--mark", type=parse_pointer)
    screenshot.add_argument("--label")
    screenshot.add_argument("--marker-size", type=int, default=22)
    screenshot.add_argument("--no-marker", action="store_true")

    record = subparsers.add_parser(
        "record", help="capture the screen as an animated GIF or H.264 MP4"
    )
    record.add_argument("--out", required=True)
    record.add_argument("--meta")
    record.add_argument("--duration", type=float, default=8.0)
    record.add_argument("--fps", type=int, default=8)
    record.add_argument("--region", type=_parse_region)
    record.add_argument(
        "--width",
        type=int,
        help="downscale to at most this width; recordings stay at native size by default",
    )
    record.add_argument("--no-pointer", action="store_true")
    record.add_argument("--gif-out", help="also encode a GIF from the same captured frames")
    record.add_argument("--gif-width", type=int, default=720)
    record.add_argument(
        "--trim-idle",
        action="store_true",
        help="trim static lead-in and tail frames around the recorded interaction",
    )
    record.add_argument("--crf", type=int, default=20, help="MP4 H.264 quality (lower is better)")

    move = subparsers.add_parser("move", help="move the pointer")
    move.add_argument("x", type=int)
    move.add_argument("y", type=int)

    drag = subparsers.add_parser("drag", help="drag from the pointer to a destination")
    drag.add_argument("x", type=int)
    drag.add_argument("y", type=int)
    drag.add_argument("--duration", type=float, default=0.5)
    drag.add_argument("--button", type=int, default=1)

    path = subparsers.add_parser(
        "path", help="hold a mouse button while moving through x,y points"
    )
    path.add_argument("points", nargs="+", type=parse_pointer)
    path.add_argument("--duration", type=float, default=1.0)
    path.add_argument("--button", type=int, default=1)

    click = subparsers.add_parser("click", help="click the pointer")
    click.add_argument("--button", type=int, default=1)
    click.add_argument("--x", type=int)
    click.add_argument("--y", type=int)

    key = subparsers.add_parser("key", help="press one or more key names")
    key.add_argument("keys", nargs="+")

    type_cmd = subparsers.add_parser("type", help="type text")
    type_cmd.add_argument("text")

    subparsers.add_parser("location", help="print pointer and active-window metadata")

    docker = subparsers.add_parser("dockerfile", help="render the Anki Xvfb Dockerfile")
    docker.add_argument("--out", required=True)
    docker.add_argument(
        "--workbench-spec",
        help=(
            "package spec installed in the image "
            "(default: docker_workbench_spec config value)"
        ),
    )

    android_docker = subparsers.add_parser(
        "android-dockerfile",
        help="render the opt-in Android emulator smoke Dockerfile",
    )
    android_docker.add_argument("--out", required=True)
    android_docker.add_argument(
        "--workbench-spec",
        help=(
            "package spec installed in the image "
            "(default: android_workbench_spec config value)"
        ),
    )
    android_docker.add_argument(
        "--ankidroid-apk-url",
        help="AnkiDroid full-universal APK URL to download into the image",
    )

    android_smoke = subparsers.add_parser(
        "android-smoke",
        help="run AnkiDroid WebView smoke against configured seed_apkgs",
    )
    android_smoke.add_argument("--ankidroid-apk")
    android_smoke.add_argument("--start-emulator", action="store_true")
    android_smoke.add_argument(
        "--clear-app-data",
        action="store_true",
        help="clear AnkiDroid app data before import; intended for disposable emulators",
    )
    android_smoke.add_argument("--avd-name", default=DEFAULT_ANDROID_AVD)
    android_smoke.add_argument("--adb", default="adb")
    android_smoke.add_argument("--emulator", default="emulator")
    android_smoke.add_argument("--boot-timeout", type=int, default=240)
    android_smoke.add_argument("--cdp-port", type=int, default=DEFAULT_CDP_PORT)
    android_smoke.add_argument(
        "--selector",
        action="append",
        dest="selectors",
        help="CSS selector that must be visible in the live AnkiDroid card WebView",
    )
    android_smoke.add_argument(
        "--render-timeout-ms",
        type=int,
        help="timeout for CDP/WebView inspection",
    )

    local = subparsers.add_parser(
        "docker-smoke-local",
        help="build a local workbench wheel, Docker image, and run smoke",
    )
    local.add_argument(
        "--workbench-source",
        default=".",
        help="local anki-addon-workbench source tree to build into a wheel",
    )
    local.add_argument(
        "--artifact-dir",
        default=DEFAULT_LOCAL_DOCKER_ARTIFACT_DIR,
        help="directory for the wheel build context, Dockerfile, and logs",
    )
    local.add_argument(
        "--image",
        help="Docker image tag (default: configured docker_image with -local suffix)",
    )
    local.add_argument(
        "--uv-command",
        default="uv",
        help='command prefix used to build the wheel, e.g. "sfw uv"',
    )
    local.add_argument(
        "--docker-command",
        default="docker",
        help="command prefix used to invoke Docker",
    )
    local.add_argument(
        "--no-cache",
        action="store_true",
        help="pass --no-cache to docker build",
    )

    probe = subparsers.add_parser(
        "init-probe", help="scaffold a ready-to-edit probe add-on for smoke tests"
    )
    probe.add_argument("--out", required=True, help="directory to create the probe add-on in")
    probe.add_argument(
        "--force", action="store_true", help="overwrite an existing __init__.py"
    )

    return parser


def _load(args: argparse.Namespace) -> WorkbenchConfig:
    return load_config(Path(args.config_root))


def dispatch(args: argparse.Namespace) -> tuple[int, JsonDict]:
    if args.command == "location":
        return 0, _gui_core().location()
    if args.command == "move":
        return 0, _gui_core().move(args.x, args.y)
    if args.command == "drag":
        return 0, _gui_core().drag(
            args.x, args.y, duration=args.duration, button=args.button
        )
    if args.command == "path":
        return 0, _gui_core().path(
            args.points, duration=args.duration, button=args.button
        )
    if args.command == "click":
        return 0, _gui_core().click(args.button, args.x, args.y)
    if args.command == "key":
        return 0, _gui_core().key(args.keys)
    if args.command == "type":
        return 0, _gui_core().type_text(args.text)
    if args.command == "screenshot":
        return 0, _gui_core().screenshot(
            args.out,
            meta=args.meta,
            mark=args.mark,
            label=args.label,
            marker_size=args.marker_size,
            no_marker=args.no_marker,
        )
    if args.command == "record":
        return 0, _gui_core().record(
            args.out,
            meta=args.meta,
            duration=args.duration,
            fps=args.fps,
            region=args.region,
            width=args.width,
            show_pointer=not args.no_pointer,
            gif_out=args.gif_out,
            gif_width=args.gif_width,
            trim_idle=args.trim_idle,
            crf=args.crf,
        )

    if args.command == "init-probe":
        path = scaffold.init_probe(args.out, force=args.force)
        return 0, {
            "ok": True,
            "probe_init": str(path),
            "probe_package": path.parent.name,
            "next": "Point `probe_addon` at this directory in [tool.anki-addon-workbench].",
        }

    config = _load(args)
    if args.command == "doctor":
        return 0, doctor(config)
    if args.command == "dockerfile":
        workbench_spec = args.workbench_spec or config.docker_workbench_spec
        path = dockerfile.write_dockerfile(config, args.out, workbench_spec=workbench_spec)
        return 0, {
            "ok": True,
            "dockerfile": str(path),
            "anki_version": config.anki_version,
            "workbench_spec": workbench_spec,
        }
    if args.command == "android-dockerfile":
        workbench_spec = args.workbench_spec or config.android_workbench_spec
        path = dockerfile.write_android_dockerfile(
            config,
            args.out,
            workbench_spec=workbench_spec,
            ankidroid_apk_url=args.ankidroid_apk_url,
        )
        return 0, {
            "ok": True,
            "dockerfile": str(path),
            "android_image": config.android_image,
            "workbench_spec": workbench_spec,
            "ankidroid_apk_url": args.ankidroid_apk_url or config.android_ankidroid_apk,
        }
    if args.command == "android-smoke":
        selectors = tuple(args.selectors) if args.selectors is not None else None
        return run_android_smoke(
            config,
            ankidroid_apk=args.ankidroid_apk,
            start_emulator=args.start_emulator,
            avd_name=args.avd_name,
            adb=args.adb,
            emulator=args.emulator,
            boot_timeout=args.boot_timeout,
            cdp_port=args.cdp_port,
            clear_app_data=args.clear_app_data,
            selectors=selectors,
            render_timeout_ms=args.render_timeout_ms,
        )
    if args.command == "docker-smoke-local":
        return run_docker_smoke_local(
            config,
            workbench_source=args.workbench_source,
            artifact_dir=args.artifact_dir,
            image=args.image,
            uv_command=args.uv_command,
            docker_command=args.docker_command,
            no_cache=args.no_cache,
        )
    if args.command == "smoke":
        return run_smoke(
            config,
            anki_bin=args.anki_bin,
            anki_python=args.anki_python,
            base=args.base,
            keep=args.keep,
            screenshot=args.screenshot,
            timeout=args.timeout,
            no_direct_python=args.no_direct_python,
            qt_platform=args.qt_platform,
            xvfb=args.xvfb,
            display=args.display,
            screen=args.screen,
            allow_foreground=args.allow_foreground,
        )
    if args.command == "webkit-smoke":
        selectors = tuple(args.selectors) if args.selectors is not None else None
        return run_webkit_smoke(
            config,
            anki_bin=args.anki_bin,
            anki_python=args.anki_python,
            base=args.base,
            keep=args.keep,
            timeout=args.timeout,
            no_direct_python=args.no_direct_python,
            qt_platform=args.qt_platform,
            xvfb=args.xvfb,
            display=args.display,
            screen=args.screen,
            allow_foreground=args.allow_foreground,
            selectors=selectors,
            device=args.device,
            render_timeout_ms=args.render_timeout_ms,
        )
    if args.command == "launch":
        return run_launch(
            config,
            anki_bin=args.anki_bin,
            anki_python=args.anki_python,
            base=args.base,
            keep=args.keep,
            artifact_dir=args.artifact_dir,
            workbench_python=args.workbench_python,
            timeout=args.timeout,
            no_direct_python=args.no_direct_python,
            xvfb=args.xvfb,
            display=args.display,
            screen=args.screen,
            pointer=args.pointer,
            no_screenshot=args.no_screenshot,
            hold=args.hold,
            allow_foreground=args.allow_foreground,
        )
    raise AssertionError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        status, payload = dispatch(args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    if not (args.command == "launch" and getattr(args, "hold", False)):
        print(json.dumps(payload, indent=2, sort_keys=True))
    return status
