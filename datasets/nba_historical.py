"""NBA Historical Odds Dataset Generator.

Generates realistic NBA game odds + results for backtesting.
Uses real statistical distributions derived from actual NBA data patterns.
No external API required — deterministic seed for reproducibility.
"""
from __future__ import annotations
import os
import json
import random
import math
from datetime import datetime, timedelta
from typing import List
from dataclasses import dataclass
import pandas as pd


TEAMS = [
    "Cleveland Cavaliers", "Boston Celtics", "Oklahoma City Thunder",
    "New York Knicks", "Houston Rockets", "Denver Nuggets",
    "Los Angeles Lakers", "Golden State Warriors", "Miami Heat",
    "LA Clippers", "Memphis Grizzlies", "Philadelphia 76ers",
    "Milwaukee Bucks", "Phoenix Suns", "Indiana Pacers",
    "Dallas Mavericks", "Minnesota Timberwolves", "Detroit Pistons",
    "Orlando Magic", "Sacramento Kings", "San Antonio Spurs",
    "New Orleans Pelicans", "Atlanta Hawks", "Charlotte Hornets",
    "Portland Trail Blazers", "Washington Wizards", "Brooklyn Nets",
    "Toronto Raptors", "Chicago Bulls", "Utah Jazz",
]

FAVORITE_HOME_PROB = 0.62
HOME_MARGIN_MEAN = 3.2
HOME_MARGIN_STD = 11.5
POINT_DIFF_AVG = 6.4
POINT_DIFF_STD = 10.8


@dataclass
class Game:
    date: str
    season: str
    home_team: str
    away_team: str
    home_line: float
    away_line: float
    total_line: float
    home_score: int
    away_score: int
    home_spread_actual: float
    over_actual: float
    home_ml: float
    away_ml: float
    book: str = "Pinnacle"

    @property
    def home_cover(self) -> bool:
        return self.home_score + self.home_spread_actual > self.away_score

    @property
    def over_hit(self) -> bool:
        return (self.home_score + self.away_score) > self.total_line

    @property
    def home_win(self) -> bool:
        return self.home_score > self.away_score

    @property
    def total_scored(self) -> int:
        return self.home_score + self.away_score


@dataclass
class PlayerProp:
    date: str
    player: str
    team: str
    opponent: str
    market: str
    line: float
    over_odds: float
    under_odds: float
    actual: float
    over_hit: bool
    book: str = "PrizePicks"

    @property
    def over_profit(self) -> float:
        return (100 / abs(self.over_odds)) if self.over_hit else -1

    @property
    def under_profit(self) -> float:
        return (100 / abs(self.under_odds)) if not self.over_hit else -1


def _american_to_prob(odds: float) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def _prob_to_american(prob: float) -> float:
    if prob >= 1.0:
        return -10000
    if prob <= 0.0:
        return 10000
    if prob >= 0.5:
        return round(-100 * prob / (1 - prob), 0)
    return round(100 * (1 - prob) / prob, 0)


def _gaussian(mean: float, std: float) -> float:
    u1 = random.random()
    u2 = random.random()
    z = math.sqrt(-2 * math.log(u1 + 1e-10)) * math.cos(2 * math.pi * u2)
    return mean + z * std


def generate_nba_season(year: int, seed: int = 42) -> List[Game]:
    random.seed(seed + year)
    games = []
    start = datetime(year, 10, 1)
    team_schedule = {t: [] for t in TEAMS}

    for team in TEAMS:
        team_schedule[team] = random.sample([t for t in TEAMS if t != team], len(TEAMS) - 1)

    for team in TEAMS:
        random.shuffle(team_schedule[team])

    for week in range(26):
        week_start = start + timedelta(weeks=week)
        for day_offset in range(3, 7):
            for slot in range(5):
                game_date = week_start + timedelta(days=day_offset)
                if game_date.month > 6:
                    break

                home_pool = [t for t in TEAMS if len([g for g in games if g.home_team == t]) < 1]
                if not home_pool:
                    continue

                home = random.choice(home_pool)
                away_pool = [t for t in TEAMS if t != home and len([g for g in games if g.home_team == t and g.date == game_date.strftime("%Y-%m-%d")]) == 0]
                if not away_pool:
                    continue
                away = random.choice(away_pool)

                p_home_wins = FAVORITE_HOME_PROB + _gaussian(0, 0.15)
                p_home_wins = max(0.30, min(0.75, p_home_wins))

                home_margin = _gaussian(HOME_MARGIN_MEAN + (3 if random.random() < 0.3 else 0), HOME_MARGIN_STD)
                total_points = _gaussian(226, 12)

                home_score = int(total_points / 2 + home_margin / 2 + _gaussian(0, 3))
                away_score = int(total_points / 2 - home_margin / 2 + _gaussian(0, 3))
                home_score = max(70, home_score)
                away_score = max(70, away_score)
                if abs(home_score - away_score) < 1:
                    home_score += random.randint(1, 5)

                spread = round(_gaussian(0, 3) + (3 if home_margin > 0 else -3), 1)
                total = round(220 + _gaussian(0, 8), 1)

                home_implied = p_home_wins
                away_implied = 1 - p_home_wins + 0.02
                home_implied /= (home_implied + away_implied)
                home_ml = _prob_to_american(home_implied)
                away_ml = _prob_to_american(1 - home_implied)

                games.append(Game(
                    date=game_date.strftime("%Y-%m-%d"),
                    season=f"{year}-{year+1}",
                    home_team=home, away_team=away,
                    home_line=spread, away_line=-spread,
                    total_line=total,
                    home_score=home_score, away_score=away_score,
                    home_spread_actual=-spread,
                    over_actual=total,
                    home_ml=home_ml, away_ml=away_ml,
                ))
    return games


def generate_player_props(games: List[Game], seed: int = 42) -> List[PlayerProp]:
    random.seed(seed)
    props = []
    players = {
        "Cleveland Cavaliers": ["Donovan Mitchell", "Darius Garland", "Jarrett Allen", "Evan Mobley"],
        "Boston Celtics": ["Jayson Tatum", "Jaylen Brown", "Derrick White", "Kristaps Porzingis"],
        "Oklahoma City Thunder": ["Shai Gilgeous-Alexander", "Jalen Williams", "Chet Holmgren"],
        "New York Knicks": ["Jalen Brunson", "Karl-Anthony Towns", "OG Anunoby", "Mikal Bridges"],
        "Houston Rockets": ["Alperen Sengun", "Jalen Green", "Fred VanVleet", "Amen Thompson"],
        "Denver Nuggets": ["Nikola Jokic", "Jamal Murray", "Michael Porter Jr.", "Aaron Gordon"],
        "Los Angeles Lakers": ["LeBron James", "Anthony Davis", "Austin Reaves", "Rui Hachimura"],
        "Golden State Warriors": ["Stephen Curry", "Jimmy Butler", "Draymond Green", "Jonathan Kuminga"],
        "Miami Heat": ["Jimmy Butler", "Tyler Herro", "Bam Adebayo", "Nikola Jovic"],
        "LA Clippers": ["Kawhi Leonard", "James Harden", "Norman Powell", "Ivica Zubac"],
        "Milwaukee Bucks": ["Giannis Antetokounmpo", "Damian Lillard", "Khris Middleton", "Brook Lopez"],
        "Phoenix Suns": ["Kevin Durant", "Devin Booker", "Bradley Beal", "Nurkic"],
        "Philadelphia 76ers": ["Tyrese Maxey", "Paul George", "Joel Embiid", "Caleb Martin"],
        "Minnesota Timberwolves": ["Anthony Edwards", "Julius Randle", "Rudy Gobert", "Donte DiVincenzo"],
        "Dallas Mavericks": ["Luka Doncic", "Kyrie Irving", "P.J. Washington", "Daniel Gafford"],
        "Indiana Pacers": ["Tyrese Haliburton", "Pascal Siakam", "Myles Turner", "Andrew Nembhard"],
        "Sacramento Kings": ["DeMar DeRozan", "Domantas Sabonis", "Keegan Murray", "Kevin Huerter"],
    }

    market_configs = [
        ("points", 20.5, 3.5, 1.2),
        ("rebounds", 8.5, 2.5, 1.1),
        ("assists", 7.5, 2.0, 1.1),
        ("points", 24.5, 4.0, 1.2),
        ("rebounds", 10.5, 3.0, 1.1),
        ("assists", 9.5, 2.5, 1.1),
        ("points", 27.5, 4.5, 1.3),
        ("PRA", 35.5, 5.0, 1.2),
    ]

    for game in games:
        team_players = players.get(game.home_team, []) + players.get(game.away_team, [])
        if not team_players:
            continue

        num_props = random.randint(4, 8)
        for _ in range(num_props):
            player = random.choice(team_players)
            team = game.home_team if player in players.get(game.home_team, []) else game.away_team
            opponent = game.away_team if team == game.home_team else game.home_team

            mkt_cfg = random.choice(market_configs)
            market, base_line, std_line, juice = mkt_cfg

            line = round(base_line + _gaussian(0, std_line), 1)
            if line < 4.5:
                line = 4.5

            p_over = 0.48 + _gaussian(0, 0.08)
            p_over = max(0.38, min(0.62, p_over))

            if random.random() < 0.5:
                actual = round(line + _gaussian(0, std_line * 1.2), 1)
            else:
                actual = round(line - _gaussian(0, std_line * 1.2), 1)

            over_odds = _prob_to_american(p_over + 0.01)
            under_odds = _prob_to_american(1 - p_over + 0.01)

            props.append(PlayerProp(
                date=game.date,
                player=player, team=team, opponent=opponent,
                market=market, line=line,
                over_odds=over_odds, under_odds=under_odds,
                actual=actual,
                over_hit=actual > line,
            ))
    return props


def generate_all_seasons(seasons: List[int] = None, seed: int = 42) -> pd.DataFrame:
    if seasons is None:
        seasons = [2021, 2022, 2023, 2024, 2025]
    all_games = []
    for year in seasons:
        all_games.extend(generate_nba_season(year, seed))
    df = pd.DataFrame([{
        "date": g.date, "season": g.season,
        "home_team": g.home_team, "away_team": g.away_team,
        "home_score": g.home_score, "away_score": g.away_score,
        "spread_line": g.home_line, "total_line": g.total_line,
        "home_ml": g.home_ml, "away_ml": g.away_ml,
        "home_spread_actual": g.home_spread_actual, "over_actual": g.over_actual,
        "home_win": g.home_win, "home_cover": g.home_cover, "over_hit": g.over_hit,
        "home_implied_prob": round(_american_to_prob(g.home_ml), 4),
        "away_implied_prob": round(_american_to_prob(g.away_ml), 4),
    } for g in all_games])
    df["actual_total"] = df["home_score"] + df["away_score"]
    df["over_hit"] = df["actual_total"] > df["total_line"]
    return df


def generate_player_props_df(seasons: List[int] = None, seed: int = 42) -> pd.DataFrame:
    if seasons is None:
        seasons = [2021, 2022, 2023, 2024, 2025]
    all_props = []
    for year in seasons:
        games = generate_nba_season(year, seed)
        all_props.extend(generate_player_props(games, seed + year))
    df = pd.DataFrame([{
        "date": p.date, "player": p.player, "team": p.team,
        "opponent": p.opponent, "market": p.market, "line": p.line,
        "over_odds": p.over_odds, "under_odds": p.under_odds,
        "actual": p.actual, "over_hit": p.over_hit,
        "over_profit": p.over_profit, "under_profit": p.under_profit,
        "book": p.book,
    } for p in all_props])
    return df


def save_datasets(path: str = "datasets", seasons: List[int] = None):
    os.makedirs(path, exist_ok=True)
    seed = int(os.getenv("BACKTEST_SEED", "919"))

    print("Generating NBA historical odds dataset...")
    nba_df = generate_all_seasons(seasons, seed)
    nba_path = os.path.join(path, "nba_games.csv")
    nba_df.to_csv(nba_path, index=False)
    print(f"  Saved {len(nba_df)} games to {nba_path}")

    print("Generating player props dataset...")
    props_df = generate_player_props_df(seasons, seed)
    props_path = os.path.join(path, "player_props.csv")
    props_df.to_csv(props_path, index=False)
    print(f"  Saved {len(props_df)} props to {props_path}")

    stats = {
        "total_games": len(nba_df),
        "total_props": len(props_df),
        "seasons": list(nba_df["season"].unique()),
        "date_range": f"{nba_df['date'].min()} to {nba_df['date'].max()}",
        "home_win_rate": round(nba_df["home_win"].mean(), 4),
        "home_cover_rate": round(nba_df["home_cover"].mean(), 4),
        "over_rate": round(nba_df["over_hit"].mean(), 4),
        "avg_total": round(nba_df.apply(lambda r: r["home_score"] + r["away_score"], axis=1).mean(), 1),
    }
    stats_path = os.path.join(path, "dataset_stats.json")
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  Stats: {stats}")
    return stats


if __name__ == "__main__":
    save_datasets()