# AGENTS.md

## Scope

These instructions apply to the `anki-addon-workbench` repository.

## Project Intent

`anki-addon-workbench` provides reusable disposable-profile, add-on install,
Docker/Xvfb, smoke-test, and GUI workbench tooling for Anki add-on and deck
development. The generic pointer/keyboard/screenshot primitives live in the
`anki_addon_workbench.gui` subpackage (pyautogui + Pillow), exposed through the
optional `[gui]` extra. This absorbs the former standalone `gui-agent-workbench`
project, which is now deprecated.

## Development

- Keep the `gui` subpackage Anki-agnostic and behind the optional `[gui]` extra;
  import pyautogui/Pillow lazily so the core tooling and tests need no display.
- Keep environment-specific paths (e.g. the Docker launcher bin) out of Python;
  drive them via env vars (`ANKI_BIN`, `ANKI_PYTHON`) and the Dockerfile.
- Treat real Anki profiles and collections as out of scope. Tests should use
  disposable base folders and fixture add-ons.
- Use `uv` for dependency management and keep the lockfile current.
- Run `make check` before committing meaningful changes.

## Publication safety

Follow `docs/PUBLICATION_PROCESS.md`. Install the shared frozen local hooks before
public pushes and keep the pinned quiet publication check required on main.
Keep detailed audit findings outside Git; unsupported formats block publication.
