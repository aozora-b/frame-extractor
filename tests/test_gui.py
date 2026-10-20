from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.gui
@pytest.mark.integration
def test_gui_loads_extracts_and_shows_gallery(test_video: Path, tmp_path: Path) -> None:
    from tools.gui_smoke import run

    out = tmp_path / "hasil-gui"
    gallery_items, files = run(test_video, out)
    assert gallery_items == 10
    assert files == 10
    assert sorted(path.suffix for path in out.iterdir()) == [".png"] * 10
