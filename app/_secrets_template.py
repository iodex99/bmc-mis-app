"""Template for the build-time secrets file.

`app/_secrets.py` (gitignored) is created at build time by `build.py` from the
``BMC_MIS_GH_TOKEN`` and ``BMC_MIS_GH_REPO`` environment variables. CI fills
these from GitHub Actions secrets; locally, you can set them in your shell
before running ``python build.py``.

When `_secrets.py` is missing (e.g. running from source in development), the
auto-updater silently disables itself.
"""

GITHUB_TOKEN = ""           # fine-grained PAT, read-only Contents
GITHUB_REPO = ""            # e.g. "yourname/bmc-mis"
