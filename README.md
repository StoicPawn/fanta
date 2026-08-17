# Fanta Auction Lab V6

Decision-support system for a Serie A fantasy-football auction. It keeps observed market information separate from an independent statistical valuation, converts both into league-specific expected fantasy points, and adapts bidding to the actual auction room.

## Core principle

A static fair price is insufficient. The system therefore separates:

- sporting value under the exact league rules;
- uncertainty and data quality;
- portfolio fair value versus replacement level;
- expected market clearing price;
- strategic MAX BID given the current room and future alternatives.

If a top striker has fair value 100 but comparable players are disappearing and the room consistently clears above the model, the system can rationally recommend more than 100 rather than mechanically leaving the manager with unused cash and no elite supply.

## V6 capabilities

1. **League configuration** — budget, roster slots, goals/assists/cards, clean sheets, defence modifier, goalkeeper goals conceded, penalties saved/missed, own goals and minimum bid.
2. **Lossless Serie A master** — roster backbone plus fantasy list reconciliation, with explicit coverage status.
3. **Independent player projection** — expected minutes, vote points, xG/xA shrinkage, optional external-league history, team attack/defence context, injury/start probability, penalty/set-piece share and uncertainty bands P10/P50/P90.
4. **Market comparison** — Fantacalcio quotation/FVM and optional aggregate real-auction market priors remain separate from the model.
5. **Auction Copilot** — budgets, slots, global/role inflation, learned opponent aggressiveness, supply scarcity, room liquidity and Monte Carlo clearing prices.
6. **Self-calibration** — actual sale prices are compared with the clearing price predicted before the sale. Persistent under/over-prediction automatically adjusts later clearing forecasts with shrinkage.
7. **Strategy Lab** — BUY NOW versus WAIT/SKIP optimises the entire remaining roster, so opportunity cost is evaluated at portfolio level rather than player level.
8. **Persistence** — purchases, managers and notes can be exported to JSON and restored.
9. **Health dashboard** — structural dataset checks, duplicate detection, role validity, coverage metrics, auction-state consistency and pre-auction readiness checklist.
10. **Performance hardening** — repeated Monte Carlo forecasts are cached within an unchanged auction state and invalidated immediately after each purchase.

## Optional enrichment fields

The model never invents unavailable facts. If reliable data are available, a master CSV can provide:

`starting_probability`, `injury_risk`, `team_attack_strength`, `team_defense_strength`, `penalty_share`, `set_piece_share`, `goals_conceded_per90`, `penalties_faced`, `penalty_save_rate`, `external_minutes`, `external_goals`, `external_assists`, `external_xg`, `external_xa`, `external_league_factor`.

When these fields are missing the model uses explicit conservative priors and lowers reliability.

## Data sources and provenance

Current adapters support the public Fantacalcio list/quotation surface or a user-provided current list, football-data.org for competition squads, Understat-style historical enrichment, and an optional public aggregate real-auction price prior. A public downloadable dataset containing millions of raw Italian fantasy-auction transactions is **not assumed to exist**. If a licensed raw-auction dataset becomes available it can be plugged into the market layer without changing the auction architecture.

Third-party HTML/API contracts can change. The software therefore supports user files, exposes data quality, and should not silently treat a partial/stale source as complete.

## Interpretation

- `independent_points`: expected total fantasy points under the configured rules.
- `projected_points_p10/p50/p90`: uncertainty band around the projection.
- `independent_score`: role-normalised sporting score.
- `market_score`: role-normalised market/FVM score.
- `edge_confidence_adjusted`: model-market disagreement discounted by reliability.
- `fair_price`: replacement-level portfolio value before room dynamics.
- `expected_clearing`: current simulated auction clearing price.
- `calibration`: live multiplier learned from previous forecast errors in this room.
- `MAX BID`: current tactical ceiling.
- `strategic_bid`: portfolio-aware ceiling from BUY versus WAIT analysis.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the multipage entries for **Strategy Lab** and **Advanced Settings & Health** from the Streamlit sidebar.

## Tests

GitHub Actions compiles the main app, source package and all Streamlit pages, then runs the complete pytest suite on every push and pull request.
