from __future__ import annotations

import types

import fetch_movie_ids as fm


def test_qid_from_item_extracts_bare_id():
    assert fm.qid_from_item("http://www.wikidata.org/entity/Q42") == "Q42"
    assert fm.qid_from_item("Q42") == "Q42"
    assert fm.qid_from_item("") == ""


def test_sparql_literal_escapes_quotes_and_backslashes():
    assert fm.sparql_literal('a"b\\c') == '"a\\"b\\\\c"@en'


def test_year_from_date():
    assert fm.year_from_date("2025-05-02T00:00:00Z") == 2025
    assert fm.year_from_date("") is None
    assert fm.year_from_date(None) is None


def test_build_query_routes_qid_vs_label():
    query = fm.build_query({"Thunderbolts*": "Q112322474", "Friendship": "Friendship"})
    assert "wd:Q112322474" in query  # explicit Q-id -> item block
    assert '"Friendship"@en' in query  # plain title -> label block


def test_needs_fetch():
    full = {
        "wikidata_id": "Q1",
        "tmdb_id": "1",
        "box_office_mojo_id": "tt1",
        "metacritic_id": "m",
        "letterboxd_id": "l",
    }
    assert not fm.needs_fetch(full)
    assert fm.needs_fetch({**full, "tmdb_id": ""})
    assert fm.needs_fetch({**full, "wikidata_id": ""})


def _fake_sparql(payload):
    class FakeSparql:
        def __init__(self, *a, **k):
            pass

        def setMethod(self, *a):
            pass

        def setReturnFormat(self, *a):
            pass

        def setTimeout(self, *a):
            pass

        def setQuery(self, *a):
            pass

        def query(self):
            return types.SimpleNamespace(convert=lambda: payload)

    return FakeSparql


def test_query_wikidata_flattens_bindings(monkeypatch):
    payload = {
        "results": {
            "bindings": [
                {
                    "sourceTitle": {"value": "Thunderbolts*"},
                    "item": {"value": "http://www.wikidata.org/entity/Q1"},
                    "tmdb": {"value": "986056"},
                },
            ]
        }
    }
    monkeypatch.setattr(fm, "SPARQLWrapper", _fake_sparql(payload))
    df = fm.query_wikidata({"Thunderbolts*": "Thunderbolts*"})
    assert df.columns == list(fm.empty_candidates().schema)
    assert df["tmdb"].to_list() == ["986056"]
    # Fields the binding omitted default to empty string, not null.
    assert df["metacritic"].to_list() == [""]


def test_query_wikidata_empty_input_skips_network(monkeypatch):
    def explode(*a, **k):
        raise AssertionError("should not query for empty input")

    monkeypatch.setattr(fm, "SPARQLWrapper", explode)
    assert fm.query_wikidata({}).shape == (0, len(fm.empty_candidates().schema))


def test_titles_from_predictions_dedupes_in_first_seen_order(tmp_path):
    path = tmp_path / "predictions.csv"
    path.write_text(
        "title,host,box_office_pred_millions,metacritic_pred\n"
        "Thunderbolts*,sean,199,64\n"
        "Friendship,amanda,30,70\n"
        "Thunderbolts*,amanda,250,61\n"
    )
    assert fm.titles_from_predictions(path) == ["Thunderbolts*", "Friendship"]


def test_movies_roundtrip(tmp_path):
    path = tmp_path / "movies.csv"
    original = (
        "title,wikidata_id,tmdb_id,box_office_mojo_id,metacritic_id,letterboxd_id\n"
        "Thunderbolts*,Q112322474,986056,tt20969586,movie/thunderbolts,thunderbolts\n"
    )
    path.write_text(original)
    fm.write_movies(fm.read_movies(path), path)
    assert path.read_text() == original


def test_write_movies_seed_keeps_all_columns(tmp_path):
    path = tmp_path / "movies.csv"
    fm.write_movies([{"title": "A"}, {"title": "B"}], path)
    header, *body = path.read_text().splitlines()
    assert (
        header
        == "title,wikidata_id,tmdb_id,box_office_mojo_id,metacritic_id,letterboxd_id"
    )
    assert body == ["A,,,,,", "B,,,,,"]
