from __future__ import annotations

from anki_addon_workbench.cli import build_parser


def test_parser_accepts_public_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["doctor"]).command == "doctor"
    assert parser.parse_args(["smoke"]).command == "smoke"
    assert parser.parse_args(["smoke", "--allow-foreground"]).allow_foreground is True
    assert parser.parse_args(["smoke", "--foreground"]).allow_foreground is True
    webkit_args = parser.parse_args(
        ["webkit-smoke", "--selector", "#answer svg", "--device", "iPhone 14"]
    )
    assert webkit_args.command == "webkit-smoke"
    assert webkit_args.selectors == ["#answer svg"]
    assert webkit_args.device == "iPhone 14"
    assert parser.parse_args(["launch"]).command == "launch"
    assert parser.parse_args(["location"]).command == "location"
    assert parser.parse_args(["move", "1", "2"]).command == "move"
    assert parser.parse_args(["drag", "3", "4"]).duration == 0.5
    assert parser.parse_args(["path", "1,2", "3,4"]).points == [(1, 2), (3, 4)]
    assert parser.parse_args(["click"]).button == 1
    assert parser.parse_args(["key", "Escape"]).keys == ["Escape"]
    assert parser.parse_args(["type", "hello"]).text == "hello"
    record_args = parser.parse_args(
        [
            "record",
            "--out",
            "demo.mp4",
            "--duration",
            "4",
            "--region",
            "10,20,640,480",
            "--gif-out",
            "demo.gif",
            "--trim-idle",
            "--crf",
            "18",
        ]
    )
    assert record_args.duration == 4.0
    assert record_args.region == (10, 20, 640, 480)
    assert record_args.width is None
    assert record_args.gif_out == "demo.gif"
    assert record_args.trim_idle is True
    assert record_args.crf == 18
    docker_args = parser.parse_args(
        ["dockerfile", "--out", "Dockerfile", "--workbench-spec", "local.whl"]
    )
    assert docker_args.out == "Dockerfile"
    assert docker_args.workbench_spec == "local.whl"
    android_docker_args = parser.parse_args(
        [
            "android-dockerfile",
            "--out",
            "Android.Dockerfile",
            "--ankidroid-apk-url",
            "https://example.test/AnkiDroid.apk",
        ]
    )
    assert android_docker_args.out == "Android.Dockerfile"
    assert android_docker_args.ankidroid_apk_url == "https://example.test/AnkiDroid.apk"
    android_smoke_args = parser.parse_args(
        ["android-smoke", "--start-emulator", "--clear-app-data", "--selector", "#answer svg"]
    )
    assert android_smoke_args.command == "android-smoke"
    assert android_smoke_args.start_emulator is True
    assert android_smoke_args.clear_app_data is True
    assert android_smoke_args.selectors == ["#answer svg"]
    local_args = parser.parse_args(
        [
            "docker-smoke-local",
            "--workbench-source",
            ".",
            "--artifact-dir",
            ".tmp/local",
            "--uv-command",
            "sfw uv",
        ]
    )
    assert local_args.workbench_source == "."
    assert local_args.artifact_dir == ".tmp/local"
    assert local_args.uv_command == "sfw uv"
    assert parser.parse_args(["init-probe", "--out", "probe"]).out == "probe"
