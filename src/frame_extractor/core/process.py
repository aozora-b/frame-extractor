"""Utilitas subprocess lintas platform."""

from __future__ import annotations

import os
import subprocess


def hidden_process_kwargs() -> dict:
    """Cegah jendela konsol muncul saat ffmpeg dijalankan dari aplikasi GUI Windows."""

    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}
