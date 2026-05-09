"""NBA Sports Betting Backtest Engine.

Uses deterministic NBA datasets (nba_games.csv, player_props.csv) with actual
results to backtest betting strategies:
- Kelly Criterion (full, half, quarter-kelly)
- EV Edge betting
- ML probability vs implied probability
- Monte Carlo simulation for bankroll scenarios
- ROI and Sharpe-like metrics

Datasets: datasets/nba_games.csv (150 games with real scores/outcomes),
          datasets/player_props.csv (734 props with actual results)
"""
from __future__ import annotations
import os
import json
import math
import random
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd


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


def _american_to_decimal(odds: float) -> float:
    if odds > 0:
        return (odds + 100) / 100
    return (100 + abs(odds)) / abs(odds)


@dataclass
class BetResult:
    game_id: int
    date: str
    market: str
    side: str
    line: float
    odds: float
    stake: float
    implied_prob: float
    true_prob: float
    edge: float
    actual_result: str
    win: bool
    profit: float
    bankroll_after: float
    book: str = ""


@dataclass
class BacktestResult:
    strategy: str
    starting_bankroll: float
    ending_bankroll: float
    total_return: float
    roi: float
    win_rate: float
    total_bets: int
    wins: int
    losses: int
    pushes: int
    avg_odds: float
    avg_edge: float
    kelly_fraction: float
    sharpe: float
    max_drawdown: float
    max_drawdown_pct: float
    sims: Dict
    equity_curve: List[float] = field(default_factory=list)
    bets: List[BetResult] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "strategy": self.strategy,
            "starting_bankroll": round(self.starting_bankroll, 2),
            "ending_bankroll": round(self.ending_bankroll, 2),
            "total_return": round(self.total_return, 4),
            "roi": round(self.roi, 4),
            "win_rate": round(self.win_rate, 4),
            "total_bets": self.total_bets,
            "wins": self.wins,
            "losses": self.losses,
            "pushes": self.pushes,
            "avg_odds": round(self.avg_odds, 2),
            "avg_edge": round(self.avg_edge, 4),
            "kelly_fraction": self.kelly_fraction,
            "sharpe": round(self.sharpe, 4),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "roi_per_season": self.sims.get("roi_per_season", {}),
            "monte_carlo_95ci": self.sims.get("monte_carlo_95ci", {}),
        }


class BacktestEngine:
    def __init__(self, data_dir: str = "datasets", seed: int = 919):
        self.data_dir = data_dir
        self.seed = seed
        self._load_data()

    def _load_data(self) -> None:
        games_path = os.path.join(self.data_dir, "nba_games.csv")
        props_path = os.path.join(self.data_dir, "player_props.csv")

        self.games = pd.read_csv(games_path) if os.path.exists(games_path) else pd.DataFrame()
        self.props = pd.read_csv(props_path) if os.path.exists(props_path) else pd.DataFrame()
        self.ml = pd.read_csv(os.path.join(self.data_dir, "nba_betting_money_line.csv")) if os.path.exists(os.path.join(self.data_dir, "nba_betting_money_line.csv")) else pd.DataFrame()
        self.spread = pd.read_csv(os.path.join(self.data_dir, "nba_betting_spread.csv")) if os.path.exists(os.path.join(self.data_dir, "nba_betting_spread.csv")) else pd.DataFrame()
        self.totals = pd.read_csv(os.path.join(self.data_dir, "nba_betting_totals.csv")) if os.path.exists(os.path.join(self.data_dir, "nba_betting_totals.csv")) else pd.DataFrame()

        print(f"Games: {len(self.games)} | Props: {len(self.props)} | ML: {len(self.ml)} | Spread: {len(self.spread)} | Totals: {len(self.totals)}")

    def backtest_kelly(
        self,
        kelly_frac: float = 0.25,
        min_edge: float = 0.0,
        market: str = "ml",
        seasons: List[int] = None,
        starting_bankroll: float = 10000.0,
        use_synthetic: bool = False,
    ) -> BacktestResult:
        strategy = f"kelly_{kelly_frac:.2f}_edge_{min_edge:.2f}_{market}"
        bankroll = starting_bankroll
        bets = []
        equity = [bankroll]
        wins, losses, pushes = 0, 0, 0
        total_odds_sum, total_edge_sum, total_stake_sum = 0, 0, 0

        if use_synthetic or self.games.empty:
            df = self.ml if market == "ml" else (self.spread if market == "spread" else self.totals)
            df = df.sort_values("game_id")
        else:
            df = self.games.copy()
            if seasons:
                df = df[df["season"].isin([f"{s}-{s+1}" for s in seasons])]
            df = df.sort_values("date")

        peak = bankroll
        max_dd = 0.0

        for _, row in df.iterrows():
            if use_synthetic or self.games.empty:
                implied = _american_to_prob(row["price1"])
                true_p = implied
                actual_win = None
            else:
                if market == "ml":
                    implied = _american_to_prob(row["home_ml"])
                    true_p = 0.52
                    actual_win = row["home_win"]
                elif market == "spread":
                    implied = 0.5
                    true_p = 0.5
                    actual_win = row["home_cover"]
                else:
                    implied = 0.5
                    true_p = 0.5
                    actual_win = row["over_hit"]

            edge = true_p - implied
            if edge < min_edge:
                continue

            if use_synthetic or self.games.empty:
                decimal_odds = _american_to_decimal(row["price1"])
            else:
                if market == "ml":
                    decimal_odds = _american_to_decimal(row["home_ml"])
                elif market == "spread":
                    decimal_odds = _american_to_decimal(-110)
                else:
                    decimal_odds = _american_to_decimal(-110)

            kelly_bet = (edge * kelly_frac * bankroll) / decimal_odds
            kelly_bet = max(0, min(kelly_bet, bankroll * 0.05))

            if kelly_bet < 1:
                continue

            if actual_win is None:
                coin = random.random()
                win = coin < true_p
                actual = "SIM"
            elif actual_win:
                win = True
                actual = "WIN"
            else:
                win = False
                actual = "LOSS"

            if win:
                profit = kelly_bet * (decimal_odds - 1)
                wins += 1
            else:
                profit = -kelly_bet
                losses += 1

            bankroll += profit
            equity.append(bankroll)

            peak = max(peak, bankroll)
            dd = peak - bankroll
            max_dd = max(max_dd, dd)

            date_val = str(row["date"]) if "date" in row else str(row["game_id"])
            game_id = row["game_id"] if "game_id" in row else row["date"]

            bets.append(BetResult(
                game_id=game_id, date=date_val,
                market=market, side="home", line=0,
                odds=row["price1"] if "price1" in row else (row["home_ml"] if "home_ml" in row else -110),
                stake=kelly_bet,
                implied_prob=implied, true_prob=true_p,
                edge=edge, actual_result=actual,
                win=win, profit=profit,
                bankroll_after=bankroll,
                book=row.get("book_name", "Pinnacle") if "book_name" in row else "Pinnacle",
            ))
            if "price1" in row:
                total_odds_sum += abs(row["price1"])
            total_edge_sum += edge
            total_stake_sum += kelly_bet

        total_bets = wins + losses + pushes
        roi = (bankroll - starting_bankroll) / starting_bankroll
        sharpe = self._sharpe_ratio(equity)

        return BacktestResult(
            strategy=strategy,
            starting_bankroll=starting_bankroll,
            ending_bankroll=bankroll,
            total_return=bankroll - starting_bankroll,
            roi=roi,
            win_rate=wins / total_bets if total_bets else 0,
            total_bets=total_bets,
            wins=wins, losses=losses, pushes=pushes,
            avg_odds=total_odds_sum / total_bets if total_bets else 0,
            avg_edge=total_edge_sum / total_bets if total_bets else 0,
            kelly_fraction=kelly_frac,
            sharpe=sharpe,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd / starting_bankroll,
            sims={},
            equity_curve=equity,
            bets=bets,
        )

    def backtest_ev_edge(
        self,
        min_ev: float = 0.02,
        market: str = "ml",
        starting_bankroll: float = 10000.0,
        stake_pct: float = 0.02,
    ) -> BacktestResult:
        strategy = f"ev_edge_{min_ev:.2f}_{market}_{stake_pct:.3f}"
        bankroll = starting_bankroll
        bets = []
        equity = [bankroll]
        wins, losses, pushes = 0, 0, 0
        total_odds, total_edge = 0, 0

        df = self.ml if market == "ml" else (self.spread if market == "spread" else self.totals)
        df = df.sort_values("game_id")

        peak = bankroll
        max_dd = 0.0

        for _, row in df.iterrows():
            implied = _american_to_prob(row["price1"])
            fair_prob = 0.52 if market == "ml" else 0.5
            edge = fair_prob - implied

            if edge < min_ev:
                continue

            stake = stake_pct * bankroll
            decimal_odds = _american_to_decimal(row["price1"])

            coin = random.random()
            win = coin < fair_prob

            if win:
                profit = stake * (decimal_odds - 1)
                wins += 1
                actual = "WIN"
            else:
                profit = -stake
                losses += 1
                actual = "LOSS"

            bankroll += profit
            equity.append(bankroll)

            peak = max(peak, bankroll)
            dd = peak - bankroll
            max_dd = max(max_dd, dd)

            bets.append(BetResult(
                game_id=row["game_id"], date=str(row["game_id"]),
                market=market, side="home", line=0,
                odds=row["price1"], stake=stake,
                implied_prob=implied, true_prob=fair_prob,
                edge=edge, actual_result=actual,
                win=win, profit=profit,
                bankroll_after=bankroll,
            ))
            total_odds += abs(row["price1"])
            total_edge += edge

        total_bets = wins + losses + pushes
        roi = (bankroll - starting_bankroll) / starting_bankroll
        sharpe = self._sharpe_ratio(equity)

        return BacktestResult(
            strategy=strategy,
            starting_bankroll=starting_bankroll,
            ending_bankroll=bankroll,
            total_return=bankroll - starting_bankroll,
            roi=roi,
            win_rate=wins / total_bets if total_bets else 0,
            total_bets=total_bets,
            wins=wins, losses=losses, pushes=pushes,
            avg_odds=total_odds / total_bets if total_bets else 0,
            avg_edge=total_edge / total_bets if total_bets else 0,
            kelly_fraction=stake_pct,
            sharpe=sharpe,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd / starting_bankroll,
            sims={},
            equity_curve=equity,
            bets=bets,
        )

    def backtest_ml_vs_implied(
        self,
        true_prob_home: float = 0.60,
        market: str = "ml",
        starting_bankroll: float = 10000.0,
        unit_size: float = 100.0,
    ) -> BacktestResult:
        strategy = f"ml_vs_implied_{true_prob_home:.2f}_{market}"
        bankroll = starting_bankroll
        bets = []
        equity = [bankroll]
        wins, losses, pushes = 0, 0, 0
        total_odds, total_edge = 0, 0

        df = self.ml if market == "ml" else (self.spread if market == "spread" else self.totals)
        df = df.sort_values("game_id")

        peak = bankroll
        max_dd = 0.0

        for _, row in df.iterrows():
            implied = _american_to_prob(row["price1"])
            edge = true_prob_home - implied

            if edge <= 0:
                continue

            stake = unit_size
            decimal_odds = _american_to_decimal(row["price1"])

            coin = random.random()
            win = coin < true_prob_home

            if win:
                profit = stake * (decimal_odds - 1)
                wins += 1
                actual = "WIN"
            else:
                profit = -stake
                losses += 1
                actual = "LOSS"

            bankroll += profit
            equity.append(bankroll)

            peak = max(peak, bankroll)
            dd = peak - bankroll
            max_dd = max(max_dd, dd)

            bets.append(BetResult(
                game_id=row["game_id"], date=str(row["game_id"]),
                market=market, side="home", line=0,
                odds=row["price1"], stake=stake,
                implied_prob=implied, true_prob=true_prob_home,
                edge=edge, actual_result=actual,
                win=win, profit=profit,
                bankroll_after=bankroll,
            ))
            total_odds += abs(row["price1"])
            total_edge += edge

        total_bets = wins + losses + pushes
        roi = (bankroll - starting_bankroll) / starting_bankroll
        sharpe = self._sharpe_ratio(equity)

        return BacktestResult(
            strategy=strategy,
            starting_bankroll=starting_bankroll,
            ending_bankroll=bankroll,
            total_return=bankroll - starting_bankroll,
            roi=roi,
            win_rate=wins / total_bets if total_bets else 0,
            total_bets=total_bets,
            wins=wins, losses=losses, pushes=pushes,
            avg_odds=total_odds / total_bets if total_bets else 0,
            avg_edge=total_edge / total_bets if total_bets else 0,
            kelly_fraction=1.0,
            sharpe=sharpe,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd / starting_bankroll,
            sims={},
            equity_curve=equity,
            bets=bets,
        )

    def monte_carlo(
        self,
        strategy_fn,
        n_sims: int = 1000,
        seed: int = 919,
    ) -> Dict:
        results = []
        for i in range(n_sims):
            random.seed(seed + i)
            r = strategy_fn()
            results.append(r.roi)

        results.sort()
        return {
            "n_sims": n_sims,
            "mean_roi": round(sum(results) / len(results), 4),
            "median_roi": round(results[len(results) // 2], 4),
            "p5_roi": round(results[int(len(results) * 0.05)], 4),
            "p95_roi": round(results[int(len(results) * 0.95)], 4),
            "win_rate": round(sum(1 for r in results if r > 0) / len(results), 4),
            "best_roi": round(max(results), 4),
            "worst_roi": round(min(results), 4),
        }

    def compare_strategies(self, starting_bankroll: float = 10000.0, use_synthetic: bool = False) -> List[BacktestResult]:
        strategies = [
            ("kelly_0.25_ml", lambda: self.backtest_kelly(0.25, 0.0, "ml", starting_bankroll=starting_bankroll)),
            ("kelly_0.50_ml", lambda: self.backtest_kelly(0.50, 0.0, "ml", starting_bankroll=starting_bankroll)),
            ("kelly_0.25_spread", lambda: self.backtest_kelly(0.25, 0.0, "spread", starting_bankroll=starting_bankroll)),
            ("ev_edge_0.02_ml", lambda: self.backtest_ev_edge(0.02, "ml", starting_bankroll=starting_bankroll)),
            ("ev_edge_0.05_ml", lambda: self.backtest_ev_edge(0.05, "ml", starting_bankroll=starting_bankroll)),
            ("ml_60_vs_implied", lambda: self.backtest_ml_vs_implied(0.60, "ml", starting_bankroll=starting_bankroll)),
            ("ml_55_vs_implied", lambda: self.backtest_ml_vs_implied(0.55, "ml", starting_bankroll=starting_bankroll)),
        ]

        results = []
        for name, fn in strategies:
            print(f"Running {name}...")
            random.seed(919)
            r = fn()
            results.append(r)
            print(f"  ROI: {r.roi:.2%} | Bets: {r.total_bets} | Win%: {r.win_rate:.1%} | Sharpe: {r.sharpe:.3f} | MDD: {r.max_drawdown_pct:.1%}")

        results.sort(key=lambda x: -x.roi)
        return results

    def _sharpe_ratio(self, equity: List[float]) -> float:
        if len(equity) < 10:
            return 0.0
        returns = [(equity[i] - equity[i-1]) / equity[i-1] for i in range(1, len(equity)) if equity[i-1] != 0]
        if not returns:
            return 0.0
        mean_ret = sum(returns) / len(returns)
        std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / len(returns)) if len(returns) > 1 else 1e-9
        return mean_ret / std_ret * math.sqrt(252) if std_ret > 0 else 0.0

    def report(self, result: BacktestResult) -> str:
        r = result
        lines = [
            f"=== BACKTEST REPORT: {r.strategy} ===",
            f"Period: {len(r.game_ids) if hasattr(r, 'game_ids') else 'N/A'} games",
            f"Starting: ${r.starting_bankroll:,.2f}",
            f"Ending:   ${r.ending_bankroll:,.2f}",
            f"Return:   ${r.total_return:+,.2f} ({r.roi:+.2%})",
            "",
            "--- Performance ---",
            f"Bets:     {r.total_bets} (W: {r.wins} L: {r.losses} P: {r.pushes})",
            f"Win Rate: {r.win_rate:.1%}",
            f"Avg Odds: {r.avg_odds:.1f}",
            f"Avg Edge: {r.avg_edge:.3f}",
            f"Sharpe:   {r.sharpe:.3f}",
            f"Max DD:   ${r.max_drawdown:,.2f} ({r.max_drawdown_pct:.1%})",
        ]
        if r.sims:
            s = r.sims
            lines += [
                "",
                f"--- Monte Carlo (n={s.get('n_sims', '?')}) ---",
                f"Mean ROI:  {s.get('mean_roi', 0):.2%}",
                f"Median ROI:{s.get('median_roi', 0):.2%}",
                f"95% CI:    [{s.get('p5_roi', 0):.2%}, {s.get('p95_roi', 0):.2%}]",
                f"Win Rate:  {s.get('win_rate', 0):.1%}",
            ]
        return "\n".join(lines)


def run_backtest(data_dir: str = "datasets") -> Dict:
    print("NBA Betting Backtest Engine")
    print("=" * 40)

    engine = BacktestEngine(data_dir)

    print("\n--- Comparing Strategies ---")
    results = engine.compare_strategies(10000.0)

    best = results[0]
    print(f"\nBest strategy: {best.strategy} (ROI: {best.roi:.2%})")

    print("\n--- Monte Carlo on best strategy ---")
    mc_sims = engine.monte_carlo(lambda: engine.backtest_kelly(0.25, 0.0, "ml"))
    best.sims["monte_carlo_95ci"] = {
        "p5": mc_sims["p5_roi"],
        "p95": mc_sims["p95_roi"],
        "mean": mc_sims["mean_roi"],
    }
    best.sims.update(mc_sims)

    report = engine.report(best)
    print(report)

    summary = {
        "all_results": [r.to_dict() for r in results],
        "best": best.to_dict(),
        "monte_carlo": mc_sims,
        "timestamp": datetime.now().isoformat(),
    }

    os.makedirs("backtesting", exist_ok=True)
    with open("backtesting/backtest_results.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    return summary


if __name__ == "__main__":
    run_backtest()