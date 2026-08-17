# Fanta Auction Lab V8

Decision-support system for a Serie A fantasy-football auction. It keeps observed market information separate from an independent statistical valuation, converts both into league-specific expected fantasy points, and adapts bidding to the actual auction room.

## V8 focus

V8 moves from simply adding sources to **gap-driven data collection**. The system now measures, player by player, which information layers are missing and ranks the next source to add by expected value rather than collecting redundant data blindly.

### Core capabilities

- exact league scoring and roster configuration;
- lossless current Serie A roster + current fantasy-list reconciliation;
- independent expected-points model with P10/P50/P90 uncertainty;
- market/FVM comparison kept separate from sporting valuation;
- replacement-level fair prices and whole-roster optimisation;
- live Auction Copilot with budgets, slots, inflation, opponent aggression, scarcity, liquidity and Monte Carlo clearing prices;
- self-calibration from forecast-versus-actual auction prices;
- BUY NOW vs WAIT/SKIP Strategy Lab;
- persistence, notes, source health and player-level gap analysis.

## Real-data sources wired into the engine

- **football-data.org** — current Serie A teams and squads; roster authority. Free token.
- **Fantacalcio.it / user Listone** — fantasy role, quotation and FVM; market layer.
- **Understat** — historical minutes, goals, assists, shots, key passes, xG, xA, npxG, xGChain and xGBuildup.
- **fantacalcio.dev** — public multi-season fantasy history: fantamedia, average vote, goals, assists and appearances.
- **football-data.co.uk** — free historical Serie A/Serie B match CSVs used for team attack/defence context.
- **ClubElo** — current/historical club Elo strength.
- **OpenFootball Italy** — CC0 Serie A 2026/27 schedule/results. V8 parses the full 380-match schedule and combines upcoming opponents with ClubElo into a short-horizon schedule-strength factor.
- **Fantacalcio-Online** — historical fantasy/stat cross-check and separate real-auction aggregate price prior.
- **API-Football / API-Sports** — optional free key: detailed individual stats plus current injury/suspension feed when coverage is enabled.
- **Big Balls Sports Data** — optional free key: big-five xG history, especially useful for new arrivals from abroad.

API keys can be passed in the UI or configured once as environment variables:

```bash
export FOOTBALL_DATA_TOKEN='...'
export API_FOOTBALL_TOKEN='...'
export BIGBALLS_TOKEN='...'
```

## Gap Analyzer

Open **Gap Analyzer** from the Streamlit sidebar. It measures coverage of:

- identity/roster;
- fantasy market;
- minutes;
- goals/assists;
- xG/xA;
- discipline;
- fantasy vote history;
- team context;
- availability/titolarità;
- penalties/set pieces.

For every player it produces `gap_count`, `gap_severity` and `missing_layers`, plus a source-priority table such as `availability -> API-Football`, `expected_stats -> Understat/BigBalls` or `fantasy_history -> fantacalcio.dev/Fantacalcio-Online`.

## Schedule model

The current 2026/27 schedule is fetched from the CC0 `openfootball/italy` repository. For each Serie A club the engine looks at the next configurable horizon (currently six matches), evaluates opponent Elo, home share and derives a bounded `schedule_ease_factor`. This is deliberately a smaller adjustment than underlying team/player quality.

## Provenance and failure policy

Roster authority and enrichment remain separate. Optional sources fail softly and are logged; a broken enrichment never deletes a player. Missing facts are not fabricated. Priors are explicitly treated as priors and lower `data_confidence`/reliability.

No public downloadable corpus of millions of raw Italian fantasy-auction transactions is assumed. Auction behaviour is therefore learned from public aggregate real-auction prices, the current room's observed sales, self-calibration and simulated heterogeneous bidders.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

Use **Data Sources** to build the master, **Gap Analyzer** to see what is still missing, **Player Intelligence** for valuation, **Auction LIVE** during the auction, and **Strategy Lab** for whole-roster BUY-vs-WAIT decisions.

## Tests

GitHub Actions compiles the main app, source package and all Streamlit pages, then runs the complete pytest suite on every push and pull request.
