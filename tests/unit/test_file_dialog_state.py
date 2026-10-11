from __future__ import annotations

import json

from fish_morphometry.ui.file_dialog_state import load_last_directory, save_last_directory


def test_last_directory_round_trip(tmp_path):
    state_path = tmp_path / "state" / "ui.json"
    selected_directory = tmp_path / "images"
    selected_directory.mkdir()

    assert save_last_directory(selected_directory, state_path) is True
    assert load_last_directory(state_path) == selected_directory.resolve()


def test_last_directory_ignores_missing_directory(tmp_path):
    state_path = tmp_path / "ui.json"
    state_path.write_text(
        json.dumps({"last_dialog_directory": str(tmp_path / "removed")}),
        encoding="utf-8",
    )

    assert load_last_directory(state_path) is None
    assert save_last_directory(tmp_path / "removed", state_path) is False


def test_last_directory_tolerates_corrupt_state(tmp_path):
    state_path = tmp_path / "ui.json"
    state_path.write_text("{no es json", encoding="utf-8")

    assert load_last_directory(state_path) is None
