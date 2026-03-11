"""
Master strategy engine.
Evaluates all Natenberg-inspired strategies and returns a ranked list.

Core Natenberg principle:
  - IV > HV → options overpriced → favor volatility-selling strategies
  - IV < HV → options underpriced → favor volatility-buying strategies

Scoring (0–100) factors:
  1. IV Rank alignment with strategy type (40 pts)
  2. Risk/Reward ratio (20 pts)
  3. Probability of profit via delta (15 pts)
  4. Capital efficiency (10 pts)
  5. Theta decay optimization (DTE sweet spot 30–45) (10 pts)
  6. Delta-neutral bonus (5 pts)
"""
import logging
from strategies.spreads import evaluate_spreads
from strategies.volatility_plays import evaluate_volatility_plays
from strategies.income import evaluate_income_strategies
from strategies.synthetic import evaluate_synthetics

logger = logging.getLogger(__name__)


def score_strategy(strategy: dict, vol_summary: dict) -> float:
    """
    Applies Natenberg scoring model to a candidate strategy dict.
    Returns a float 0–100.
    """
    score = 0.0
    iv_rank = vol_summary.get("iv_rank") or 50.0
    vol_regime = vol_summary.get("vol_regime", "fair")
    strategy_type = strategy.get("type", "neutral")  # "sell_vol", "buy_vol", "directional", "neutral"

    # 1. IV Rank alignment (40 pts)
    if strategy_type == "sell_vol":
        score += iv_rank * 0.40  # High IV rank → better to sell vol
    elif strategy_type == "buy_vol":
        score += (100 - iv_rank) * 0.40  # Low IV rank → better to buy vol
    else:
        score += 20.0  # Neutral strategies get half points

    # 2. Risk/Reward ratio (20 pts) — higher reward vs risk → higher score
    max_profit = strategy.get("max_profit")
    max_loss = strategy.get("max_loss")
    if max_profit and max_loss and max_loss > 0:
        rr = min(max_profit / max_loss, 5.0)  # Cap at 5:1
        score += (rr / 5.0) * 20.0
    elif max_loss is None:  # Unlimited profit
        score += 15.0
    else:
        score += 5.0

    # 3. Probability of profit via delta (15 pts)
    pop = strategy.get("prob_of_profit", 50.0)
    score += (pop / 100.0) * 15.0

    # 4. Capital efficiency (10 pts) — lower margin relative to max profit
    capital_required = strategy.get("capital_required", 0)
    if capital_required and max_profit:
        efficiency = min(max_profit / capital_required, 1.0)
        score += efficiency * 10.0
    else:
        score += 5.0

    # 5. DTE theta optimization (10 pts) — sweet spot 30–45 DTE
    dte = strategy.get("dte", 0)
    if 30 <= dte <= 45:
        score += 10.0
    elif 15 <= dte < 30 or 45 < dte <= 60:
        score += 6.0
    elif 0 < dte < 15:
        score += 2.0
    else:
        score += 4.0

    # 6. Delta-neutral bonus (5 pts)
    net_delta = abs(strategy.get("net_delta", 1.0))
    if net_delta < 0.10:
        score += 5.0
    elif net_delta < 0.25:
        score += 3.0

    return round(min(score, 100.0), 1)


def run_engine(enriched_chain: list[dict], S: float, vol_summary: dict) -> list[dict]:
    """
    Evaluates all strategy categories and returns a ranked list.

    Args:
        enriched_chain: Options with IV and Greeks from blackscholes.enrich_option()
        S: Current GGAL stock price
        vol_summary: Output from volatility.get_volatility_summary()

    Returns:
        List of strategy dicts sorted by score descending.
    """
    if not enriched_chain or S <= 0:
        return []

    candidates: list[dict] = []

    try:
        candidates += evaluate_volatility_plays(enriched_chain, S, vol_summary)
    except Exception as e:
        logger.error(f"volatility_plays error: {e}")

    try:
        candidates += evaluate_spreads(enriched_chain, S, vol_summary)
    except Exception as e:
        logger.error(f"spreads error: {e}")

    try:
        candidates += evaluate_income_strategies(enriched_chain, S, vol_summary)
    except Exception as e:
        logger.error(f"income_strategies error: {e}")

    try:
        candidates += evaluate_synthetics(enriched_chain, S, vol_summary)
    except Exception as e:
        logger.error(f"synthetics error: {e}")

    # Score and rank
    for strat in candidates:
        strat["score"] = score_strategy(strat, vol_summary)

    ranked = sorted(candidates, key=lambda s: s["score"], reverse=True)
    return ranked[:10]  # Return top 10
