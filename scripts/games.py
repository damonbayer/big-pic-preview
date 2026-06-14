"""Shared access to the multi-game manifest (games/games.json).

Each game (edition) lives in games/<id>/ with its own movies.csv,
predictions.csv, results.csv, and tmdb_details.json. By default the update
scripts only touch games marked ``live`` in the manifest, but each accepts game
ids or ``--all`` to update finished editions too (see ``parse_game_selection``).
"""

from __future__ import annotations

import argparse
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


def add_game_selection_args(parser: argparse.ArgumentParser) -> None:
    """Add the shared ``--all`` / game-id selection options to a parser."""
    parser.add_argument(
        "game_ids",
        nargs="*",
        metavar="GAME_ID",
        help="specific game ids to update (default: all live games)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="update every game in the manifest, not just the live ones",
    )


def selected_games(args: argparse.Namespace) -> list[Game]:
    """Resolve a parsed argparse namespace to the games to update.

    Precedence: explicit game ids, then ``--all``, otherwise live games.
    """
    games = load_games()
    if args.game_ids:
        if args.all:
            raise SystemExit("pass either game ids or --all, not both")
        by_id = {game.id: game for game in games}
        unknown = [game_id for game_id in args.game_ids if game_id not in by_id]
        if unknown:
            known = ", ".join(game.id for game in games)
            raise SystemExit(
                f"unknown game id(s): {', '.join(unknown)} (known: {known})"
            )
        return [by_id[game_id] for game_id in args.game_ids]
    if args.all:
        return games
    return [game for game in games if game.live]


def parse_game_selection(description: str) -> list[Game]:
    """Build a parser with the standard selection options and resolve it."""
    parser = argparse.ArgumentParser(description=description)
    add_game_selection_args(parser)
    return selected_games(parser.parse_args())
