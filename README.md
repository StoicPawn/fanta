# Fanta Auction Lab V3

Decision-support system for a Serie A fantasy-football auction. It deliberately keeps **observed market information** separate from an **independent statistical valuation**, then converts both into league-specific scores and a live maximum bid.

## What V3 changes

1. **Lossless roster master.** football-data.org supplies the 20 Serie A squad backbone; the current Fantacalcio Listone supplies fantasy eligibility, roles, quotation and FVM. A player present only in the fresher Listone is appended rather than silently dropped.
2. **Coverage gate.** The UI exposes reconciliation status and never treats an incomplete/stale list as certified.
3. **Independent projection.** Recent Serie A production and Understat xG/xA are recency-weighted. Expected minutes are a transparent prior with explicit confidence; newcomers receive a cautious role/market prior rather than fake zero production.
4. **League-specific scoring.** Goal/assist/cards/clean-sheet/defence-modifier settings change player rankings and fair prices.
5. **Auction Copilot.** Live max bid respects the cash needed to fill the roster, role scarcity, role-level auction inflation, league-wide outstanding demand and learned manager aggressiveness.
6. **Uncertainty is visible.** `reliability`, `minutes_source`, `data_confidence` and `edge_confidence_adjusted` distinguish strong evidence from speculative upside.

## Sources and policy

- Fantacalcio public Listone/quotation page or a user-downloaded Listone file. The adapter validates the requested season and refuses stale content.
- football-data.org v4 (free API token) for competition teams and squads.
- Understat public league pages for historical xG-style enrichment. It is enrichment only, never roster authority.

Adapters may break when third-party markup changes. The design therefore supports user files and surfaces provenance. Check each provider's current terms before redistribution or commercial use.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

For automatic roster construction, create a free football-data.org token and paste it in the Data tab. For maximum robustness around auction day, download the current Listone and upload it in the same tab: the pipeline then uses that file as the fantasy source while still reconciling it against the roster backbone.

## Important interpretation

`market_score` answers "how expensive/highly rated is he in the fantasy market?". `independent_score` answers "how many league-specific points/upside does our model estimate?". `edge_confidence_adjusted` asks "how large is the disagreement after discounting weak evidence?". `fair_price` is a portfolio allocation value, not a prediction of the room's final price. `MAX BID` is dynamic and changes as the auction unfolds.
