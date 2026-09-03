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

The independent model is deliberately isolated from FVM/quotation/auction prices. Sporting score is built first from expected fantasy points, minutes/availability, expected production, replacement scarcity, context and data confidence. Market information is attached afterwards only to calculate disagreement/edge. Historical minutes are preferred; fantasy history and official current-season appearances can provide additional individual evidence. Very small current-season samples are strongly shrunk and explicitly labelled **low confidence**. If no supported individual evidence exists, the model does not fabricate a prediction: score, points, fair price and MAX BID remain unavailable and the UI shows the reason explicitly. The official Listone valuation is still reported separately: FVM is scaled from 1,000 credits to the configured league budget, with the official quotation shown as a fallback when FVM is unavailable.

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

- **Fantacalcio.it / official user Listone** — the only canonical auction universe, plus official role, quotation and FVM.
- **Fantacalcio.it current statistics** — official current-season appearances, average/fantasy vote, goals, assists and discipline; opening-match samples are down-weighted and labelled low confidence.
- **football-data.org** — optional current Serie A squad enrichment. It cannot add players outside the Listone. Free token.
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

The official Fantacalcio Listone and enrichment remain strictly separate. Every pipeline merge is left-anchored to the Listone: external sources can add fields to its players but can never expand the auction universe. Optional sources fail softly and are logged; a broken enrichment never deletes a Listone player. Missing facts are not fabricated; when individual evidence is insufficient, `prediction_available=False` and model outputs stay null.

**Gap Analyzer** measures missing layers player by player. **Source Control** maps those gaps to source priority and freshness policy. Rate-limited or fragile responses can be cached under `.cache/fanta_lab/`; stale fallback is explicit rather than silently presented as fresh data.

No public downloadable corpus of millions of raw Italian fantasy-auction transactions is assumed. Auction behaviour is therefore learned from public aggregate real-auction prices, the current room's observed sales, self-calibration and simulated heterogeneous bidders.

## Windows: download and start

1. Open <https://github.com/StoicPawn/fanta> and select **Code → Download ZIP**.
2. Extract the ZIP completely, for example into `C:\FantaAuctionLab`. Do not run it from inside the compressed folder.
3. Install **Python 3.12 (64-bit)** from <https://www.python.org/downloads/windows/>. During setup enable **Add python.exe to PATH**.
4. Double-click `install_windows.bat` once and wait for the completion message.
5. Double-click `run_windows.bat`. Streamlit opens the app in the default browser, normally at `http://localhost:8501`.

On first use, configure the league on the home page, then open **Data Sources**. Choose **Rapido** to test the application immediately with the official Listone and current-season statistics, or **Completo** to add all enabled historical/context sources. The current official Listone is downloaded automatically; alternatively upload the current official CSV/XLSX. Continue with **Ranking giocatori** and finally **Command Center**.

### Persistent save slots

The sidebar exposes five local save slots. **Salva ora** writes league rules, the built player dataset, purchases, manager names and opponent notes to the selected slot. Loading or saving a slot makes it the active slot; with **Autosave slot attivo** enabled, subsequent changes are persisted automatically. The last active slot is automatically restored when the app is started again. **Nuovo / pulisci lavoro corrente** starts from an empty session without deleting existing slots; slots can be deleted individually or all together from the sidebar.

Save files live under `.fanta_saves/` in the local application folder and are excluded from Git. Runtime API tokens and widget/password values are not included in snapshots.

To stop the local app, return to its black terminal window and press `Ctrl+C`. Subsequent starts require only `run_windows.bat`.

## Run from a terminal

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

Recommended workflow: **Data Sources → Formazione consigliata → Ranking giocatori → Command Center**. Use Strategy Lab when a decision requires deeper scenario analysis; Gap Analyzer, Source Control and Health are supporting tools.

## Tests

GitHub Actions compiles the main app, source package and all Streamlit pages, then runs the complete pytest suite on every push and pull request.
