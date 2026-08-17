# Fanta Auction Lab V9

Decision-support system for a Serie A fantasy-football auction. It keeps observed market information separate from an independent statistical valuation, converts both into league-specific expected fantasy points, and adapts bidding to the actual auction room.

## V9 focus

V9 adds a **source-control layer** on top of the V8 gap-driven pipeline. The system now knows not only which player-data layers are missing, but also how fresh each source should be, which layers are critical, when a refresh is worth spending API quota and when cached/stale data are safer than repeatedly hitting a provider.

### Core capabilities

- exact league scoring and roster configuration;
- lossless current Serie A roster + current fantasy-list reconciliation;
- independent expected-points model with P10/P50/P90 uncertainty;
- market/FVM comparison kept separate from sporting valuation;
- replacement-level fair prices and whole-roster optimisation;
- live Auction Copilot with budgets, slots, inflation, opponent aggression, scarcity, liquidity and Monte Carlo clearing prices;
- self-calibration from forecast-versus-actual auction prices;
- BUY NOW vs WAIT/SKIP Strategy Lab;
- persistence, notes, source health and player-level gap analysis;
- persistent local source cache with TTL and stale-if-error fallback;
- central source registry with priority, criticality, fields and freshness policy;
- smart refresh plan driven by actual coverage rather than blind refetching.

## Real-data sources wired into the engine

- **football-data.org** — current Serie A teams and squads; roster authority. Free token. Roster calls are cached for 6 hours to protect the free quota.
- **Fantacalcio.it / user Listone** — fantasy role, quotation and FVM; market layer.
- **Understat** — historical minutes, goals, assists, shots, key passes, xG, xA, npxG, xGChain and xGBuildup.
- **fantacalcio.dev** — public multi-season fantasy history: fantamedia, average vote, goals, assists and appearances.
- **football-data.co.uk** — free historical Serie A/Serie B match CSVs used for team attack/defence context.
- **ClubElo** — current/historical club Elo strength.
- **OpenFootball Italy** — CC0 Serie A 2026/27 schedule/results; upcoming opponents are combined with club strength into a bounded schedule factor.
- **Fantacalcio-Online** — historical fantasy/stat cross-check and separate real-auction aggregate price prior.
- **API-Football / API-Sports** — optional free key: detailed individual stats plus current injury/suspension feed when coverage is enabled.
- **Big Balls Sports Data** — optional free key: big-five xG history, especially useful for new arrivals from abroad.

API keys can be passed in the UI, Streamlit secrets, or environment variables. Real secret files and the local data cache are ignored by Git.

```bash
export FOOTBALL_DATA_TOKEN='...'
export API_FOOTBALL_TOKEN='...'
export BIGBALLS_TOKEN='...'
```

## Gap Analyzer

**Gap Analyzer** measures, player by player, missing identity/roster, fantasy market, minutes, production, xG/xA, discipline, vote history, team context, availability and set pieces. It produces `gap_count`, `gap_severity`, `missing_layers` and a recommended next source.

## Source Control

Open **Source Control** from the Streamlit sidebar. The page exposes the central registry and calculates a refresh plan on the current master:

- `required` — critical roster/market layer is below the required coverage;
- `fill-gaps` — enrichment source is worth querying because too many players are uncovered;
- `refresh-if-stale` — coverage is already high; update only when the TTL expires.

Default freshness policy is intentionally conservative: roster/FVM about 6h, ClubElo/calendar 12h, auction/fantasy cross-check 24h, historical xG/fantasy layers 7 days.

## Cache behavior

Rate-limited or fragile sources can be cached under `.cache/fanta_lab/`, which is never committed. A fresh cache avoids repeated calls. If an upstream source is temporarily down after the TTL expires, the loader may use the last cached copy as an explicitly stale fallback instead of destroying an otherwise usable auction dataset.

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

Use **Data Sources** to build the master, **Gap Analyzer** to see what is missing, **Source Control** to decide what deserves a refresh, **Player Intelligence** for valuation, **Auction LIVE** during the auction, and **Strategy Lab** for whole-roster BUY-vs-WAIT decisions.

## Tests

GitHub Actions compiles the main app, source package and all Streamlit pages, then runs the complete pytest suite on every push and pull request.
