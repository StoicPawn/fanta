# Fanta Auction Lab V4

Decision-support system for a Serie A fantasy-football auction. It keeps **observed market information** separate from an **independent statistical valuation**, converts both into league-specific scores, and then adapts the recommended maximum bid to the actual auction room.

## Core idea

A static fair price is not enough. If the model says 100 for a top striker but all comparable elite strikers are clearing above 100, refusing 101 mechanically can leave the manager with cash and no elite player. V4 therefore models both **player value** and **market clearing risk**.

The live recommendation uses:

- independent projected fantasy points under the exact league rules;
- replacement level and scarcity by role;
- optional Fantacalcio quotation/FVM market information;
- optional public averages of prices actually paid in real fantasy auctions;
- observed inflation in the current room, globally and by role;
- each opponent's learned aggressiveness by role;
- every manager's remaining cash and required slots;
- number of comparable players still available versus solvent demand;
- a synthetic Monte Carlo market of heterogeneous human bidders;
- a hard financial cap that preserves enough credits to complete the roster.

`MAX BID` is therefore dynamic. It can rise above the pre-auction fair price when the opportunity cost of waiting becomes high, but it cannot exceed the amount that leaves the roster completable.

## V4 interface

1. **League** — budget, participants, roster slots, scoring and defence modifier; real manager/team names are stored.
2. **Data** — builds/certifies the Serie A master and can attach a real-auction market prior.
3. **Player Intelligence** — market score, independent score, confidence-adjusted edge, expected minutes and fair portfolio price.
4. **Auction LIVE** — called-player cockpit with MAX BID, expected clearing price, room P80, shortage risk, urgency and live decision; records every purchase and immediately recalibrates the room.
5. **Teams & notes** — complete opponent rosters, residual budgets, missing slots, learned aggressiveness and free-form notes per team plus global auction notes.

The entire auction state can be exported to JSON and restored later.

## Data sources and provenance

- Fantacalcio public Listone/quotation page or a user-downloaded Listone file. The adapter validates the requested season and refuses stale content.
- football-data.org v4 (free API token) for competition teams and squads.
- Understat public league pages for historical xG-style enrichment. It is enrichment only, never roster authority.
- Fantacalcio-Online public real-auction averages, when available, as an **aggregate market prior**. These are not treated as raw individual-auction training records.

No public downloadable dataset containing millions of raw Italian fantasy-auction transactions is assumed. If such a licensed dataset becomes available it can replace/improve the market-prior layer without changing the live-auction architecture.

Adapters may break when third-party markup changes. The design therefore fails loudly, supports user files, and surfaces provenance. Check each provider's current terms before redistribution or commercial use.

## Interpretation

- `market_score`: what the fantasy market/list values.
- `independent_score`: our league-specific sporting projection.
- `edge_confidence_adjusted`: disagreement with the market discounted for weak evidence.
- `fair_price`: portfolio value before room dynamics.
- `market_auction_price`: optional external real-auction aggregate prior.
- `expected_clearing`: simulated price around which the current opponents are likely to clear the player.
- `MAX BID`: strategic ceiling **right now**, after scarcity, opponents, room inflation, opportunity cost and financial constraints.

## Run

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

For automatic roster construction, create a free football-data.org token and paste it in the Data tab. Around auction day, uploading the current Listone is the most robust way to lock fantasy eligibility/roles while the pipeline reconciles against the roster backbone.
