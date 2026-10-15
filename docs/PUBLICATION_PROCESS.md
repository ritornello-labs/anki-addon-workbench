# Publication process

Use the shared local hooks and quiet required GitHub Actions publication check.
Both workflow and checker are pinned to reviewed commit `f8743b1d193d7f40cbe7877e1871b45730994d1a`.
Follow the [shared publication process](https://github.com/ritornello-labs/anki-addon-release/blob/f8743b1d193d7f40cbe7877e1871b45730994d1a/docs/PUBLICATION_PROCESS.md).

Install frozen hooks on each publishing machine. They inspect staged objects and
all outgoing commits/tags against the real destination. Preserve other hook
integrations; failed checks and unsupported formats block publication. Keep live
Anki data, credentials, recovery packages and detailed audit reports outside Git.
Public CI prints generic pass/fail only, without matched findings or artifacts.

Before a release, check exact final artifact bytes and produce a fixed-schema
hash receipt. Rebuilding invalidates the receipt; confirm the uploaded digest.
Use disposable profiles and synthetic fixtures for public demonstrations. Native
Anki listing images require explicit approval before upload.

Current-tree checks do not certify historical refs, logs or release assets.
On an exposure, stop, preserve private evidence and prepare a scoped cleanup plan.
Do not rewrite history or delete public evidence automatically.
