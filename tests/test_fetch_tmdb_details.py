from __future__ import annotations

import fetch_tmdb_details as ft
import pytest
from schemas import MOVIES_SCHEMA, PREDICTIONS_SCHEMA, RESULTS_SCHEMA


def test_rename_titles_movies(tmp_path):
    path = tmp_path / "movies.csv"
    path.write_text(
        "title,wikidata_id,tmdb_id,box_office_mojo_id,metacritic_id,letterboxd_id\n"
        "Thunderbolts*,Q1,1,a,b,c\n"
    )
    changed = ft.rename_titles(path, MOVIES_SCHEMA, {"Thunderbolts*": "Thunderbolts"})
    assert changed == 1
    text = path.read_text()
    assert "Thunderbolts," in text
    assert "Thunderbolts*" not in text


def test_rename_titles_predictions_renames_every_row(tmp_path):
    path = tmp_path / "predictions.csv"
    path.write_text(
        "title,host,box_office_pred_millions,metacritic_pred\n"
        "Thunderbolts*,sean,199,64\n"
        "Thunderbolts*,amanda,250,61\n"
    )
    assert ft.rename_titles(path, PREDICTIONS_SCHEMA, {"Thunderbolts*": "X"}) == 2


def test_rename_titles_noop_when_no_match(tmp_path):
    path = tmp_path / "results.csv"
    original = (
        "title,box_office,metacritic,box_office_error,metacritic_error\n"
        "Friendship,16252948,72,,\n"
    )
    path.write_text(original)
    assert ft.rename_titles(path, RESULTS_SCHEMA, {"Other": "Y"}) == 0
    assert path.read_text() == original


def test_rename_titles_missing_file(tmp_path):
    assert ft.rename_titles(tmp_path / "nope.csv", RESULTS_SCHEMA, {"a": "b"}) == 0


def test_load_api_key_prefers_exported_env(monkeypatch):
    # Stub load_dotenv so the real .env never participates in the test.
    monkeypatch.setattr(ft, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("TMDB_API_KEY", "exported")
    assert ft.load_api_key() == "exported"


def test_load_api_key_missing_exits(monkeypatch):
    monkeypatch.setattr(ft, "load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        ft.load_api_key()
