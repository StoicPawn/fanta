from __future__ import annotations

import numpy as np
import pandas as pd

from .models import LeagueRules
from .projection import add_projections


def _num(s: pd.Series, name: str, default=np.nan) -> pd.Series:
    if name not in s:
        return pd.Series(default, index=s.index, dtype=float)
    return pd.to_numeric(s[name], errors='coerce')


def _role_percentile(df: pd.DataFrame, col: str, higher=True) -> pd.Series:
    x = _num(df, col)
    pct = x.groupby(df['role']).rank(pct=True, method='average')
    if not higher:
        pct = 1 - pct
    return pct.fillna(.5).clip(0, 1)


def _shrink_rate(events: pd.Series, minutes: pd.Series, role: pd.Series, prior: dict[str, float], prior_minutes=900.0):
    mins = pd.to_numeric(minutes, errors='coerce').fillna(0).clip(lower=0)
    ev = pd.to_numeric(events, errors='coerce').fillna(0).clip(lower=0)
    raw = ev * 90 / mins.replace(0, np.nan)
    p = role.map(prior).fillna(np.mean(list(prior.values())))
    w = mins / (mins + prior_minutes)
    return (w * raw.fillna(p) + (1-w) * p).clip(lower=0)


def build_independent_valuation(df: pd.DataFrame, rules: LeagueRules) -> pd.DataFrame:
    """Independent valuation V1.

    No FVM/quotation/auction-price field is used to construct the sporting score.
    Market fields are only attached afterwards for comparison.  The model combines
    rule-specific projected fantasy points, replacement value, expected production,
    availability, team/schedule context and uncertainty.
    """
    out = add_projections(df.copy(), rules)
    role = out['role'].astype(str).str.upper()
    mins = _num(out, 'minutes', 0).fillna(0)

    # Bayesian-shrunk underlying production: resistant to one-season finishing luck.
    xg = _num(out, 'xg', np.nan)
    xa = _num(out, 'xa', np.nan)
    goals = _num(out, 'goals', 0)
    assists = _num(out, 'assists', 0)
    goal_signal = xg.where(xg.notna(), goals)
    assist_signal = xa.where(xa.notna(), assists)
    out['model_xg90'] = _shrink_rate(goal_signal, mins, role, {'P':0.0,'D':.045,'C':.12,'A':.30})
    out['model_xa90'] = _shrink_rate(assist_signal, mins, role, {'P':0.0,'D':.045,'C':.11,'A':.11})

    # Replacement is league-specific: enough players to fill every roster, plus a
    # small safety buffer.  Value above replacement is what scarce auction budget buys.
    total_slots = {r: rules.slots()[r] * rules.managers for r in rules.slots()}
    replacement = {}
    for r, n in total_slots.items():
        vals = pd.to_numeric(out.loc[role.eq(r), 'independent_points'], errors='coerce').dropna().sort_values(ascending=False)
        idx = min(len(vals)-1, max(0, int(np.ceil(n*1.08))-1)) if len(vals) else 0
        replacement[r] = float(vals.iloc[idx]) if len(vals) else 0.0
    out['replacement_points'] = role.map(replacement).fillna(0)
    out['vorp'] = (pd.to_numeric(out['independent_points'], errors='coerce') - out['replacement_points']).clip(lower=0)

    # Orthogonal components, all independent from fantasy market prices.
    out['production_component'] = .62*_role_percentile(out, 'independent_points') + .23*_role_percentile(out, 'model_xg90') + .15*_role_percentile(out, 'model_xa90')
    out['availability_component'] = (.65*_role_percentile(out, 'projected_minutes') + .35*_num(out, 'minutes_confidence', .35).fillna(.35).clip(0,1))
    team_attack = _num(out, 'team_context_factor', 1).fillna(1)
    team_def = _num(out, 'team_defense_factor', 1).fillna(1)
    sched = _num(out, 'schedule_factor_used', 1).fillna(1)
    team_raw = np.where(role.isin(['P','D']), .70*team_def+.30*sched, .70*team_attack+.30*sched)
    out['context_component'] = pd.Series(team_raw,index=out.index).groupby(role).rank(pct=True).fillna(.5)
    out['scarcity_component'] = _role_percentile(out, 'vorp')
    out['certainty_component'] = _num(out, 'reliability', .35).fillna(.35).clip(0,1)

    raw = (0.48*out['production_component'] + 0.18*out['availability_component'] +
           0.14*out['scarcity_component'] + 0.08*out['context_component'] +
           0.12*out['certainty_component'])
    # Confidence shrinkage prevents poorly observed newcomers from looking certain.
    conf = out['certainty_component']
    out['independent_score_v1'] = (100*(.50 + (raw-.50)*(.55+.45*conf))).clip(0,100)
    out['independent_score_floor'] = (out['independent_score_v1'] - 18*(1-conf)).clip(0,100)
    out['independent_score_ceiling'] = (out['independent_score_v1'] + 18*(1-conf)).clip(0,100)

    # Allocate the league's discretionary auction budget only on positive VORP.
    min_spend = rules.min_bid * sum(rules.slots().values())
    discretionary_per_manager = max(0, rules.budget-min_spend)
    pool_budget = discretionary_per_manager * rules.managers
    weights = out['vorp'].pow(1.18) * (.70+.30*conf)
    denom = float(weights.sum())
    out['independent_fair_price'] = rules.min_bid + (pool_budget*weights/denom if denom>0 else 0)
    out['independent_fair_price'] = out['independent_fair_price'].clip(lower=rules.min_bid)

    # Market comparison is deliberately downstream and cannot leak into the model.
    if 'fvm_1000' in out:
        market = _num(out, 'fvm_1000') * rules.budget / 1000.0
        out['market_price_from_fvm'] = market
        out['independent_price_edge'] = out['independent_fair_price'] - market
        out['independent_price_edge_conf_adj'] = out['independent_price_edge'] * conf
    return out.sort_values(['role','independent_score_v1'], ascending=[True,False]).reset_index(drop=True)
