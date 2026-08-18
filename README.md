# Fanta Auction Lab

Decision-support system for a Serie A fantasy-football auction. It keeps observed market information separate from an independent statistical valuation, converts sporting projections into the exact scoring rules of the league, optimises a complete target squad and adapts bidding to the actual auction room.

## Product modules

The Streamlit interface now follows a clear workflow rather than exposing overlapping tools:

1. **Data Sources** — build and certify the current Serie A player master.
2. **Formazione consigliata** — dynamic target squad; it changes with rules, budget, purchases and players already sold.
3. **Ranking giocatori** — complete independent ranking, uncertainty, VORP, fair price and downstream market comparison.
4. **Command Center** — the live-auction screen: MAX BID, expected clearing price, shortage risk, immediate replacements, room state and opponent notes.
5. **Strategy Lab** — whole-roster BUY-vs-WAIT scenario analysis and continuation plans.
6. **Gap Analyzer** — player-level missing-data analysis.
7. **Source Control** — source registry, coverage/freshness policy and cache controls.
8. **Advanced settings & health** — uncommon scoring rules, dataset readiness and auction consistency checks.

A shared UI design system (`src/fanta_lab/ui.py`) keeps headers, metrics, tables, empty states and sidebar status consistent across the application. The previous duplicate Copilot page was removed so there is one authoritative live-auction interface: **Command Center**.

## Independent valuation

The independent model is deliberately isolated from FVM/quotation/auction prices. Sporting score is built first from expected fantasy points, minutes/availability, expected production, replacement scarcity, context and data confidence. Market information is attached afterwards only to calculate disagreement/edge.

The ranking is league-specific. Changing clean-sheet points, goals conceded, cards, penalty rules, roster slots, budget or defence modifier changes projected points, replacement levels, fair prices and the recommended target squad.

The defence modifier is treated as a portfolio property of the fieldable goalkeeper/defender unit rather than as a fake fixed individual bonus.

## Auction engine

The live engine combines:

- independent fair value;
- remaining budget and mandatory reserve;
- remaining roster slots;
- role supply and replacement level;
- room liquidity;
- overall and role-specific inflation;
- opponent aggression learned from observed purchases;
- public aggregate auction-price priors when available;
- Monte Carlo clearing-price simulations;
- self-calibration from predicted versus realised prices;
- target-plan fragility and remaining same-tier alternatives.

Therefore MAX BID is not a static ceiling. It can rise above model fair value when waiting has a measurable whole-roster opportunity cost, while remaining constrained by the ability to complete the squad.

## Real-data sources wired into the engine

- **football-data.org** — current Serie A teams and squads; roster authority. Free token.
- **Fantacalcio.it / user Listone** — role, quotation and FVM; market layer.
- **Kickest public Serie A statistics** — detailed player production such as appearances, starts, minutes, goals, shots, shots on target, penalties, assists, key passes, discipline, recoveries, tackles, clean sheets and saves when publicly exposed.
- **Understat** — historical minutes, goals, assists, shots, key passes, xG, xA, npxG, xGChain and xGBuildup.
- **fantacalcio.dev** — multi-season fantasy history: fantamedia, average vote, goals, assists and appearances.
- **football-data.co.uk** — historical Serie A/Serie B match CSVs used for team attack/defence context.
- **ClubElo** — current/historical club strength.
- **OpenFootball Italy** — CC0 schedule/results and upcoming-opponent context.
- **Fantacalcio-Online** — historical fantasy/stat cross-check and aggregate real-auction price prior.
- **StatsBomb Open Data** — historical event-level training/calibration where open competitions are available; not treated as current Serie A coverage.
- **API-Football / API-Sports** — optional free key for detailed individual stats and injury/suspension feeds where coverage permits.
- **Big Balls Sports Data** — optional free key for big-five xG history, especially useful for newcomers from abroad.

API keys can be supplied via UI, Streamlit secrets or environment variables. Secret files and the local cache are ignored by Git.

```bash
export FOOTBALL_DATA_TOKEN='...'
export API_FOOTBALL_TOKEN='...'
export BIGBALLS_TOKEN='...'
```

## Data quality and refresh policy

Roster authority and enrichment remain separate. Optional sources fail softly and are logged; a broken enrichment never deletes a player. Missing facts are not fabricated and lower `data_confidence`/reliability.

**Gap Analyzer** measures missing layers player by player. **Source Control** maps those gaps to source priority and freshness policy. Rate-limited or fragile responses can be cached under `.cache/fanta_lab/`; stale fallback is explicit rather than silently presented as fresh data.

No public downloadable corpus of millions of raw Italian fantasy-auction transactions is assumed. Auction behaviour is therefore learned from public aggregate real-auction prices, the current room's observed sales, self-calibration and simulated heterogeneous bidders.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

Recommended workflow: **Data Sources → Formazione consigliata → Ranking giocatori → Command Center**. Use Strategy Lab when a decision requires deeper scenario analysis; Gap Analyzer, Source Control and Health are supporting tools.

## Tests

GitHub Actions compiles the main app, source package and all Streamlit pages, then runs the complete pytest suite on every push and pull request.
