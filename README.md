<h1 align="center">🔬 anki-addon-workbench</h1>

<p align="center">
  <em>Headless, disposable-profile testing &amp; cross-platform GUI tooling for Anki add-on and deck development.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/anki-addon-workbench/"><img alt="PyPI" src="https://img.shields.io/pypi/v/anki-addon-workbench?color=blue&logo=pypi&logoColor=white"></a>
  <a href="https://pypi.org/project/anki-addon-workbench/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/anki-addon-workbench?logo=python&logoColor=white"></a>
  <a href="https://github.com/ritornello-labs/anki-addon-workbench/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/ritornello-labs/anki-addon-workbench/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/ritornello-labs/anki-addon-workbench/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/pypi/l/anki-addon-workbench?color=green"></a>
  <img alt="Platforms" src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Xvfb-lightgrey">
</p>

Disposable Anki profile, add-on install, Docker/Xvfb, smoke-test, and GUI
workbench tooling for Anki add-on **and deck** development.

It helps an agent or developer launch Anki away from a real profile, install the
add-on under test, run a probe add-on, capture marked screenshots, and send
mouse or keyboard input — locally on macOS/Linux or inside a virtual display.

The first target users are add-on authors who want to make GUI work less manual
without risking their daily Anki profile, and deck authors who need to see how
cards actually render inside Anki (where JavaScript and styling can behave
differently than in a browser) without manually closing and reopening Anki —
which triggers a sync round-trip each time.

## How it works

```text
        ┌──────────────────┐                        ┌──────────────────┐
        │    live Anki     │  move · click · type   │    screenshot    │
        │    disposable    │ ─────────────────────▶ │  cursor-marked   │
        │     profile      │      (pyautogui)       │   .png + .json   │
        └──────────────────┘                        └─────────┬────────┘
                  ▲                                           │
                  │           agent reads & decides           │
                  └───────────────────────────────────────────┘
```

A disposable Anki the agent drives, screenshots, and adjusts — no profile risk, no sync churn.

## Install

From PyPI:

```sh
# core smoke/profile/Docker tooling only (dependency-light)
uv add anki-addon-workbench

# include the GUI primitives (pyautogui + Pillow) for screenshot/move/click/type
uv add 'anki-addon-workbench[gui]'

# include Playwright for iOS/AnkiMobile-engine card smoke tests
uv add 'anki-addon-workbench[webkit]'
python -m playwright install webkit
```

(`pip install 'anki-addon-workbench[gui]'` works too.)

The GUI extra is optional: the core `smoke`, `launch` (without screenshots),
`profile`, and `dockerfile` tooling has no heavy dependencies. The
screenshot/pointer/keyboard commands lazy-load pyautogui + Pillow and fail with
a clear install hint if the `[gui]` extra is missing.

The WebKit extra is also optional. It installs Playwright's Python package; run
`python -m playwright install webkit` once in the same environment to download
the browser engine used by `webkit-smoke`.

**Platform notes.** GUI primitives are cross-platform via pyautogui:

- **macOS** — works against your local `/Applications/Anki.app`; grant Terminal
  (or your runner) *Screen Recording* and *Accessibility* permission once.
  Host `smoke` and `launch` run in **stealth mode by default**: the workbench
  injects a helper add-on that shows the disposable Anki window without
  activating it (no focus steal), lowers it, and parks it so only a 2px sliver
  stays on screen (fully off-screen windows get occlusion-throttled, which
  would break webview rendering and `mw.grab()` probes). Opt out with
  `--allow-foreground`/`--foreground` for an intentionally visible run, or set
  `ANKI_ADDON_WORKBENCH_STEALTH=0` at runtime. `launch` waits for readiness by
  watching Anki's stdout for its startup marker (xdotool cannot see native
  macOS windows). Docker/Xvfb remains the truly headless route.
- **Linux/Xvfb** — works headless; pyautogui uses `scrot` + `python-xlib`
  (installed by the bundled Docker image).

## Configure An Add-On

Add this to the add-on project's `pyproject.toml`:

```toml
[tool.anki-addon-workbench]
project_name = "My Add-on"
addon_package = "my_addon"
source_root = "."
include = ["__init__.py", "manifest.json", "README.md"]
exclude = ["tests", "user_files", ".git", "__pycache__"]
seed_apkgs = []
probe_addon = "tests/gui_smoke/probe_addon"
anki_version = "25.09"
profile = "User 1"
docker_image = "my-addon-anki-gui"
# Optional. Override when dogfooding an unreleased workbench build.
docker_workbench_spec = "anki-addon-workbench[gui]"
```

If the project does not have a `pyproject.toml`, place the same keys in
`anki-workbench.toml`.

For deck-only projects, omit `addon_package` and point `seed_apkgs` at one or
more generated `.apkg` files:

```toml
[tool.anki-addon-workbench]
project_name = "My Deck"
seed_apkgs = ["out/my-deck.apkg"]
anki_version = "25.09"
docker_image = "my-deck-anki-gui"
webkit_selectors = ["#answer svg"]
android_selectors = ["#answer svg"]
```

The workbench imports those packages into the disposable profile before Anki's
GUI starts. If `seed_apkgs` is configured and no custom `probe_addon` is set,
`smoke` automatically installs a built-in deck probe that verifies the
collection has cards, lists the imported decks and note types, and renders a
small card sample. Use a custom probe only when the deck needs project-specific
assertions.

## CLI

```sh
anki-workbench doctor
anki-workbench smoke
anki-workbench webkit-smoke
anki-workbench webkit-smoke --selector "#answer svg"
anki-workbench smoke --allow-foreground
anki-workbench launch --xvfb --pointer 500,180 --keep
anki-workbench screenshot --out .tmp/shot.png --meta .tmp/shot.json
anki-workbench record --out .tmp/demo.gif --duration 8 --fps 8
anki-workbench record --out .tmp/demo.mp4 --duration 12 --fps 24
anki-workbench record --out .tmp/demo.mp4 --gif-out .tmp/demo.gif \
  --duration 6 --fps 24 --region 120,160,1280,720 --no-pointer --trim-idle
anki-workbench move 500 180
anki-workbench click
anki-workbench drag 800 450 --duration 1.2
anki-workbench path 300,400 340,380 390,410 430,360 --duration 2
anki-workbench key Escape
anki-workbench type "search text"
anki-workbench dockerfile --out tests/gui_smoke/Dockerfile
anki-workbench android-dockerfile --out tests/android_smoke/Dockerfile
anki-workbench docker-smoke-local --uv-command "sfw uv"
anki-workbench android-smoke --start-emulator
anki-workbench init-probe --out tests/gui_smoke/probe_addon
```

`smoke` installs the configured add-on and optional probe add-on into a
disposable base folder, seeds the profile so the first-run language dialog does
not appear, imports any configured APKGs, launches Anki, waits for the probe to
write JSON, prints the JSON, and removes the base folder unless `--keep` is
passed. Deck-only projects with `seed_apkgs` get the built-in deck smoke probe
automatically when no custom probe is configured.

`launch` starts disposable Anki without the probe add-on so an agent can inspect
and interact with the live GUI. It can start Xvfb, wait for the Anki window,
move the pointer, and capture a cursor-marked screenshot.

All commands print JSON. The screenshot command draws a high-contrast synthetic
marker at the pointer (headless screenshots do not include the real cursor),
which is far more reliable than depending on the display server to render it.

`record` captures the same live display as a looping GIF or H.264 MP4. GIF
encoding uses Pillow from the `[gui]` extra; MP4 encoding additionally requires
`ffmpeg` on `PATH` (the generated Xvfb Docker image includes it). Use `--region`
to crop to `x,y,width,height`, `--width` to constrain output size without ever
upscaling, and `--no-pointer` when the interaction is self-explanatory.
Recordings stay at their native cropped resolution by default. `--gif-out`
derives a GIF from the exact same captured frames as an MP4, and `--trim-idle`
removes static lead-in and tail time around the interaction. `drag` covers
straight drags, while `path` holds the mouse button through a sequence of points
for drawing and tracing demos.

## Testing Cards On iOS And Android Engines

Anki card JavaScript runs in different engines depending on platform:

- Anki Desktop uses Qt WebEngine.
- AnkiMobile on iOS uses WebKit/WKWebView.
- AnkiDroid uses Android System WebView.

`smoke` still tests the real Anki Desktop path. `webkit-smoke` adds the iOS
engine path by first running the built-in deck probe in disposable Anki, then
serving the imported collection media directory locally and injecting each
rendered front/back HTML sample into Playwright WebKit the way Anki does:
`innerHTML` first, then re-created `<script>` nodes. That matters because
external scripts created this way load asynchronously while trailing inline
scripts run immediately, which catches load-order races that `page.setContent()`
can miss.

Use it for deck projects with `seed_apkgs` and the built-in probe:

```sh
anki-workbench webkit-smoke --selector "#answer svg"
```

Selectors may also live in config:

```toml
[tool.anki-addon-workbench]
seed_apkgs = ["out/my-deck.apkg"]
webkit_selectors = ["#answer svg"]
webkit_device = "iPhone 14"
card_smoke_timeout_ms = 8000
```

The JSON output includes the desktop probe result plus per-card WebKit checks,
including console errors, uncaught page errors, card error events, failed media
requests, and selector visibility results.

`android-smoke` is intentionally heavier. It is meant to run against a real
AnkiDroid install in an emulator, opens a reviewer card, and inspects the live
AnkiDroid WebView over adb-forwarded Chrome DevTools Protocol using a raw CDP
client. By default it imports configured APKGs through Android's MediaStore
`content://` flow. With `--clear-app-data` or `android_clear_app_data = true`,
it instead clears the disposable AnkiDroid app/storage state and seeds
`/sdcard/AnkiDroid` directly from the single configured APKG before launch. Use
that mode only for disposable emulators; it is designed for repeatable CI/card
smoke tests, not for a real personal AnkiDroid profile.

There is no `[android]` Python extra; Android SDK, emulator, AVD, and AnkiDroid
APK setup are explicit host or CI responsibilities. Generate the opt-in image
with:

```sh
anki-workbench android-dockerfile \
  --out tests/android_smoke/Dockerfile \
  --ankidroid-apk-url "https://github.com/ankidroid/Anki-Android/releases/download/<version>/AnkiDroid-<version>-full-universal.apk"
```

Then build and run it with KVM access on Linux CI or a local Linux host:

```sh
docker build -f tests/android_smoke/Dockerfile -t my-deck-android .
docker run --rm --device /dev/kvm -v "$PWD":/workspace -w /workspace my-deck-android
```

The Android image is slow and large, roughly 7 GB once the SDK, emulator image,
AVD, and AnkiDroid APK are present. It verifies that a card renders in
AnkiDroid's actual WebView and that configured selectors are visible, but it is
not a guarantee for every physical-device quirk. In particular, emulator smoke
may not reproduce all freshly-imported-media serving failures or AnkiDroid's
known false-positive "Card Content Error" toast from its own JS bridge.

Useful Android config keys:

```toml
[tool.anki-addon-workbench]
seed_apkgs = ["out/my-deck-offline.apkg"]
android_ankidroid_apk = "out/workbench/AnkiDroid.apk"
android_clear_app_data = true
android_selectors = ["#answer svg", ".review-toolbar"]
```

> **`type` is ASCII-oriented.** It uses pyautogui's keystroke synthesis, which
> reliably types ASCII and common keys but **cannot reliably type non-ASCII text
> (e.g. CJK, accented characters)** — those need an input method the synthetic
> keystrokes bypass. For non-Latin search/input, set the field value through
> Anki/AnkiConnect rather than `type`. (This is a regression from the old
> `xdotool type` backend, traded for cross-platform support.)

## The Probe Contract

`smoke` works by installing a small **probe add-on** alongside the add-on under
test. When Anki finishes starting, the probe writes a JSON result to the path in
the `ANKI_ADDON_WORKBENCH_RESULT` environment variable and then exits Anki. The
runner reads that file, prints it, and uses `ok` for its exit status.

For deck-only projects, the built-in APKG probe is usually enough. It is enabled
automatically when `seed_apkgs` is non-empty and `probe_addon` is omitted. Set
`deck_smoke_render_limit = 10` if you want it to render more than the default
five sample cards.

**Scaffold one in one command** — you rarely need to write a probe by hand:

```sh
anki-workbench init-probe --out tests/gui_smoke/probe_addon
```

This writes a documented, self-contained `__init__.py` with a `run_checks()`
function to edit. Then point `probe_addon` at that directory in your config.

The result contract:

| Field         | Type | Meaning                                                          |
| ------------- | ---- | ---------------------------------------------------------------- |
| `ok`          | bool | **Required.** Whether the probe's checks passed.                 |
| `checks`      | list | Optional. `[{"name": str, "ok": bool, ...}]` per-check detail.   |
| anything else | json | Optional. Echoed back verbatim in the smoke output.             |

The runner validates that `ok` is present and boolean; if a probe forgets it (or
never writes / never exits, which times out), the smoke output says exactly what
went wrong and points you back to `init-probe`. A probe may also read
`ANKI_ADDON_WORKBENCH_SCREENSHOT` for a path to capture a screenshot to.

## Docker/Xvfb

Render the reusable Anki launcher image template in the add-on project:

```sh
anki-workbench dockerfile --out tests/gui_smoke/Dockerfile
```

Then build it and run it with the add-on project mounted:

```sh
docker build -f my-addon/tests/gui_smoke/Dockerfile -t my-addon-anki-gui my-addon
docker run --rm -v "$PWD":/workspace -w /workspace/my-addon my-addon-anki-gui
```

The image installs the Anki Linux launcher, Xvfb, `xdotool`, `scrot`,
QtWebEngine runtime libraries, Python, and the configured workbench package spec
(`anki-addon-workbench[gui]` by default). The Anki binary path is provided via
the `ANKI_BIN` environment variable (set in the image), not hardcoded in the
library. The workbench itself is installed into the image, so generated
Dockerfiles are standalone and do not require a sibling source checkout.

When dogfooding an unreleased workbench build, either set
`docker_workbench_spec` in `[tool.anki-addon-workbench]` or pass an override:

```sh
anki-workbench dockerfile \
  --out tests/gui_smoke/Dockerfile \
  --workbench-spec "anki-addon-workbench[gui] @ https://github.com/ritornello-labs/anki-addon-workbench/archive/<commit>.zip"
```

For workbench maintainers, the higher-level local-wheel path avoids publishing
or pushing before testing:

```sh
anki-workbench docker-smoke-local --uv-command "sfw uv"
```

It builds a wheel from `--workbench-source` (default: `.`), creates a small
Docker build context containing that wheel, renders a Dockerfile that installs
the wheel with `[gui]`, builds the configured image with a `-local` suffix, and
runs the configured smoke test with the project mounted at `/workspace`.
Artifacts and command logs are written under `.tmp/anki-workbench-local`.

## Development

```sh
make check
make docker-smoke-local
```

Tests run on `pytest` (`make test`) and cover config loading, add-on copy
filtering, profile seeding, command construction, Dockerfile rendering, probe
scaffolding, and the GUI marker rendering. Docker GUI smoke tests are kept behind
explicit CI commands because Anki launcher downloads and QtWebEngine startup are
comparatively slow. `make docker-smoke-local` is the maintainer confidence check
for unreleased workbench changes: it installs the local wheel into the generated
Docker image instead of pulling the published PyPI package.

## Releasing

Releases publish to PyPI via GitHub Actions using **Trusted Publishing** (OIDC) —
no API token is stored. To cut a release:

```sh
# 1. bump `version` in pyproject.toml, commit
# 2. tag and push — the tag must match the version
git tag v0.3.1
git push origin v0.3.1
```

The [`release.yml`](.github/workflows/release.yml) workflow checks that the tag
matches `pyproject.toml`, builds the sdist + wheel with `uv build`, and publishes.

One-time setup on PyPI (Account → Publishing → Add a pending publisher):

- **PyPI Project Name:** `anki-addon-workbench`
- **Owner / Repository:** your GitHub org/repo
- **Workflow name:** `release.yml`
- **Environment name:** `pypi`
