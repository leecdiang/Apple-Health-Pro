"""Apple Health Pro: local, streaming Apple Health export."""

from pathlib import Path

__version__ = (Path(__file__).parent / "version.txt").read_text(encoding="utf-8").strip()
IS_PREVIEW = "rc" in __version__
