# Fanta Auction Lab V7

Decision-support system for a Serie A fantasy-football auction. It keeps observed market information separate from an independent statistical valuation, converts both into league-specific expected fantasy points, and adapts bidding to the actual auction room.

## Core principle

A static fair price is insufficient. The system therefore separates sporting value, uncertainty, portfolio fair value, expected market clearing price and strategic MAX BID. If a top striker has fair value 100 but comparable players are disappearing and the room consistently clears above the model, the system can rationally recommend more than 100 rather than mechanically leaving the manager with unused cash and no elite supply.

## V7 capabilities

1. **League configuration** — budget, roster slots, scoring, defence modifier, goalkeeper rules, penalties, own goals and minimum bid.
2. **Lossless Serie A master** — current roster backbone plus fantasy-list reconciliation, with explicit certification.
3. **Maximal real-data pipeline** — combines multiple free/optional-free sources instead of relying on one provider.
4. **Independent player projection** — expected minutes, vote points, xG/xA shrinkage, external-league history, team context and uncertainty P10/P50/P90.
5. **Market comparison** — quotations/FVM and real-auction aggregate priors remain separate from the sporting model.
6. **Auction Copilot** — budgets, slots, inflation, opponent aggressiveness, scarcity, liquidity and Monte Carlo clearing prices.
7. **Self-calibration** — actual sale prices continuously correct later clearing forecasts with shrinkage.
8. **Strategy Lab** — BUY NOW versus WAIT/SKIP optimises the entire remaining roster.
9. **Persistence and notes** — auction state can be exported/restored and each opponent has a notebook.
10. **Health dashboards** — dataset and auction-state consistency checks plus source-by-source coverage.

## Real-data sources now wired into the engine

- **football-data.org** — current Serie A teams and squads; roster authority layer. Free API token.
- **Fantacalcio.it / user Listone** — fantasy eligibility, Classic/Mantra role, quotation and FVM. This remains the market layer rather than sporting truth.
- **Understat** — recency-weighted Serie A player history: minutes, goals, assists, shots, key passes, xG, xA, npxG, xGChain and xGBuildup.
- **fantacalcio.dev** — public multi-season fantasy archive (2017-18 onward on the site): fantamedia, average vote, goals, assists and appearances. Used as an independent fantasy-history cross-check and vote prior.
- **football-data.co.uk** — free historical Serie A/Serie B match CSVs: results, shots, shots on target, corners and cards. The engine derives team attack/defence and match-environment priors.
- **Fantacalcio-Online** — public historical quotation/stat tables used as a second fantasy cross-check.
- **Fantacalcio-Online real-auction averages** — public prices actually paid, bucketed by league size/budget. Used only as auction-market prior.
- **Big Balls Sports Data** — optional free API key. Big-five xG leaderboards expose xG, xA, npxG, xGChain, xGBuildup, goals, assists, shots, key passes, matches and minutes, with historical coverage documented back to 2014. This is especially valuable for new Serie A arrivals from England, Spain, Germany or France.

Open **Data Sources** from the Streamlit sidebar to build the richest master and see exactly how many players are covered by each layer.

## Provenance and failure policy

Roster authority and enrichment are deliberately separated. Optional web sources fail softly and are logged in the coverage report; a failed enrichment never silently deletes a player. Name-keyed sources are fuzzy-matched with conservative thresholds and remain lower-confidence than roster authority. Missing injury, penalty-taker or starting-probability information is never fabricated.

No claim is made that a public downloadable dataset of millions of raw Italian fantasy-auction transactions exists. The live market model therefore uses public aggregate real-auction prices, the current room's observed sales and simulated heterogeneous bidders. If a licensed raw-auction corpus becomes available it can be added without changing the architecture.

## Important fields

`independent_points`, `projected_points_p10/p50/p90`, `independent_score`, `market_score`, `edge_confidence_adjusted`, `fair_price`, `expected_clearing`, `MAX BID`, `strategic_bid`, `data_confidence`, `has_history`, `has_external_history`, `has_team_context`, `has_fantasy_history`.

Optional factual enrichment accepted by the model includes `starting_probability`, `injury_risk`, `penalty_share`, `set_piece_share`, `goals_conceded_per90`, `penalties_faced`, `penalty_save_rate` and `external_league_factor`.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

Open **Strategy Lab**, **Advanced Settings & Health** and **Data Sources** from the Streamlit sidebar.

## Tests

GitHub Actions compiles the main app, source package and all Streamlit pages, then runs the complete pytest suite on every push and pull request.
