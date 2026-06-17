from __future__ import annotations

import fetch_results as fr


def test_money_to_int():
    assert fr.money_to_int("$190,274,328") == 190274328


def test_parse_domestic_box_office():
    page = (
        '<div><span>Domestic (100%)</span><span class="money">$190,274,328</span></div>'
    )
    assert fr.parse_domestic_box_office(page) == 190274328


def test_parse_domestic_box_office_missing():
    assert fr.parse_domestic_box_office("<div>no money here</div>") is None


def test_parse_metacritic_score():
    # JSON-LD as Metacritic ships it: the Metascore nested in aggregateRating.
    page = """
    <html><head>
    <script type="application/ld+json">
    {
      "@type": "Movie",
      "name": "Some Movie",
      "aggregateRating": {
        "@type": "AggregateRating",
        "name": "Metascore",
        "ratingValue": 68,
        "bestRating": 100
      }
    }
    </script>
    </head></html>
    """
    assert fr.parse_metacritic_score(page) == 68


def test_parse_metacritic_score_field_order_independent():
    # ratingValue before name (the old regex window assumed name came first).
    page = (
        '<script type="application/ld+json">'
        '{"ratingValue": "72", "name": "Metascore"}'
        "</script>"
    )
    assert fr.parse_metacritic_score(page) == 72


def test_parse_metacritic_score_rendered_fallback():
    # No JSON-LD; fall back to the rendered score snippet.
    page = '<div>Metascore <div class="c-siteReviewScore"><span>54</span></div></div>'
    assert fr.parse_metacritic_score(page) == 54


def test_parse_metacritic_score_ignores_invalid_json_ld():
    page = (
        '<script type="application/ld+json">{ not valid json </script>'
        '<script type="application/ld+json">'
        '{"name": "Metascore", "ratingValue": "61"}'
        "</script>"
    )
    assert fr.parse_metacritic_score(page) == 61


def test_parse_metacritic_score_missing():
    assert fr.parse_metacritic_score("nothing relevant") is None


def test_write_results_blank_errors_are_bare(tmp_path):
    """Successful rows write empty (not quoted) error fields; failures write text."""
    rows = [
        {
            "title": "A",
            "box_office": 100,
            "metacritic": 60,
            "box_office_error": None,
            "metacritic_error": None,
        },
        {
            "title": "B",
            "box_office": None,
            "metacritic": None,
            "box_office_error": "domestic gross not found",
            "metacritic_error": "Metascore not found",
        },
    ]
    out = tmp_path / "results.csv"
    fr.write_results(rows, out)
    assert out.read_text() == (
        "title,box_office,metacritic,box_office_error,metacritic_error\n"
        "A,100,60,,\n"
        "B,,,domestic gross not found,Metascore not found\n"
    )
