"""
Briscola - clipboard helper (v0.5.0)

Write-only, Windows-only auto-copy. Puts text on the clipboard using the
built-in `clip` command, so there is no third-party dependency and it bundles
into the portable .exe unchanged.

By design this module NEVER reads the clipboard (no peeking): it exposes only
copy_to_clipboard(). On non-Windows systems, or if the copy fails for any
reason, it returns False and the caller falls back to showing the token.
"""

import os
import subprocess


def copy_to_clipboard(text):
    """Best-effort copy of `text` to the Windows clipboard. Returns True on
    success, False otherwise (non-Windows, clip unavailable, etc.)."""
    if os.name != "nt":
        return False
    try:
        # tokens are ASCII base64; encode plainly and pipe to clip.exe
        subprocess.run(["clip"], input=text.encode("utf-8"), check=True)
        return True
    except Exception:
        return False
