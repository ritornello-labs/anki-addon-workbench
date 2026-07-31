# Changelog

## Unreleased

- Include Noto CJK fonts and mpv in the Docker/Xvfb image so real-Anki
  screenshots and recordings render CJK text and exercise card audio instead
  of showing missing-runtime warnings.
- Add `record` for cropped/resized animated GIF and H.264 MP4 screen capture,
  with optional pointer display and JSON metadata.
- Keep recordings at their native cropped resolution by default and never
  upscale when `--width` is larger than the source region.
- Add `--gif-out` so one capture produces matching MP4 and GIF derivatives,
  `--trim-idle` to remove static lead-in/tail frames, and a higher-quality
  default H.264 encode.
- Add `record --actions` so timed GUI interactions run inside the capture
  process and remain visible in Qt WebEngine/Xvfb recordings.
- Add `drag` and multi-point `path` commands for repeatable map, drawing,
  handwriting, and other gesture-driven Anki demos.
- Include ffmpeg and Tk in the Docker/Xvfb image so recording and PyAutoGUI
  work out of the box in disposable Linux captures.

## 0.5.4

- Add `android_ui_dump_timeout` to `WorkbenchConfig` (default 30, matching
  `dump_ui_tree()`'s own default) and thread it through the whole Android UI
  automation call chain (`onboard_ankidroid`, `import_apkg`, `open_reviewer`,
  `accept_scheduler_upgrade`, `tap_text`, `tap_first_deck_row`,
  `find_ui_node`) so it's configurable via `[tool.anki-addon-workbench]`
  instead of only overridable by editing source.

## 0.5.3

- Widen `dump_ui_tree()`'s internal retry window from 5s to 30s, and surface
  `uiautomator dump`'s own return code/stderr plus the raw unparsed content in
  the `TimeoutError` when it's exhausted. 0.5.2's retry fixed the crash but a
  real environment (GCE-hosted Cloud Batch) still failed for the entire 5s
  window with no way to tell why; this gives both more headroom and, if it's
  still not enough, an actual root cause instead of a bare `ParseError`.

## 0.5.2

- Retry `uiautomator dump` internally until it produces parseable XML instead of
  letting a transient empty/truncated dump raise `ElementTree.ParseError` straight
  through `tap_text`/`tap_first_deck_row`/`accept_scheduler_upgrade`'s own polling
  loops. This was causing `android-smoke` to fail immediately after AnkiDroid
  launched on slower/first-boot emulators (observed on GCE-hosted Batch runs)
  even though the emulator and app were otherwise healthy.

## 0.5.1

- Poll AnkiDroid's forwarded CDP endpoint until the reviewer WebView target is
  registered instead of failing when the first `/json` response is still empty.
- Accept AnkiDroid's required V2 scheduler upgrade for directly seeded legacy
  collections, and restrict fallback deck taps to actual deck rows so modal help
  links cannot divert the smoke run into Chrome.
- Make `android-smoke --clear-app-data` seed a disposable AnkiDroid collection
  directly from a single configured APKG. This avoids brittle shell-driven
  Android import intents while still testing the real AnkiDroid WebView.
- Give AnkiDroid external-storage cleanup enough time for media-heavy deck
  fixtures.
- Launch AnkiDroid through its exported intent handler instead of its
  non-exported deck picker activity.

## 0.5.0

- Add `webkit-smoke` for iOS/AnkiMobile-engine card rendering through Playwright
  WebKit, using Anki-style HTML injection and built-in deck probe card samples.
- Add opt-in `android-smoke` and `android-dockerfile` surfaces for AnkiDroid
  emulator smoke tests over adb and raw Chrome DevTools Protocol. Android SDK,
  emulator, and APK installation stay explicit environment/CI responsibilities.
- Add cross-engine card smoke config keys for WebKit/Android selectors, device,
  timeout, Android image/spec, and AnkiDroid APK source.
