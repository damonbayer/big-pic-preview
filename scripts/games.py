"""Shared access to the multi-game manifest (games/games.json).

Each game (edition) lives in games/<id>/ with its own movies.csv,
predictions.csv, results.csv, and tmdb_details.json. The update
scripts only ever touch games marked ``live`` in the manifest; finished editions
are frozen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAMES_DIR = ROOT / "games"
MANIFEST = GAMES_DIR / "games.json"


@dataclass(frozen=True)
class Game:
    id: str
    season: str
    year: int
    title: str
    live: bool

    @property
    def dir(self) -> Path:
        return GAMES_DIR / self.id

    @property
    def movies_csv(self) -> Path:
        return self.dir / "movies.csv"

    @property
    def predictions_csv(self) -> Path:
        return self.dir / "predictions.csv"

    @property
    def results_csv(self) -> Path:
        return self.dir / "results.csv"

    @property
    def tmdb_json(self) -> Path:
        return self.dir / "tmdb_details.json"


def load_games() -> list[Game]:
    """Every game in the manifest, in chronological (oldest-first) order."""
    data = json.loads(MANIFEST.read_text())
    return [
        Game(
            id=game["id"],
            season=game["season"],
            year=game["year"],
            title=game["title"],
            live=bool(game["live"]),
        )
        for game in data["games"]
    ]


def live_games() -> list[Game]:
    """Only the games the update scripts should refresh."""
    return [game for game in load_games() if game.live]
