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


def add_canonical_valuation(df:pd.DataFrame,rules:LeagueRules)->pd.DataFrame:
    """Attach the official Listone valuation without treating it as model output.

    FVM is expressed by Fantacalcio on a 1,000-credit budget, so it is scaled to the
    configured league budget.  If FVM is absent, the official quotation is still
    exposed as a reference, with a different unit and never used as an auction price.
    """
    out=df.copy()
    fvm=_num(out,'fvm_1000',np.nan)
    quotation=_num(out,'quotation',np.nan)
    scaled=fvm*float(rules.budget)/1000.0
    out['market_price_from_fvm']=scaled
    out['canonical_value']=scaled.where(fvm.notna(),quotation)
    out['canonical_value_source']=np.select(
        [fvm.notna(),quotation.notna()],
        [f'Listone Fantacalcio · FVM scalato su budget {rules.budget}','Listone Fantacalcio · quotazione ufficiale'],
        default='Listone Fantacalcio · valutazione non disponibile',
    )
    out['canonical_value_unit']=np.select(
        [fvm.notna(),quotation.notna()],
        [f'crediti su {rules.budget}','quotazione ufficiale'],
        default='',
    )
    return out


def build_independent_valuation(df: pd.DataFrame, rules: LeagueRules) -> pd.DataFrame:
    """Independent valuation V1, fully rule-aware and market-isolated."""
    out = add_projections(df.copy(), rules)
    role = out['role'].astype(str).str.upper()
    available = out['prediction_available'].fillna(False).astype(bool)
    mins = _num(out, 'minutes', 0).fillna(0)

    xg = _num(out, 'xg', np.nan); xa = _num(out, 'xa', np.nan)
    goals = _num(out, 'goals', 0); assists = _num(out, 'assists', 0)
    goal_signal = xg.where(xg.notna(), goals); assist_signal = xa.where(xa.notna(), assists)
    out['model_xg90'] = _shrink_rate(goal_signal, mins, role, {'P':0.0,'D':.045,'C':.12,'A':.30})
    out['model_xa90'] = _shrink_rate(assist_signal, mins, role, {'P':0.0,'D':.045,'C':.11,'A':.11})
    # ``project_player`` already performs conservative current-form and fantasy-history
    # shrinkage. Reuse those rates when exact historical minutes are unavailable.
    out['model_xg90'] = out['model_xg90'].where(mins.gt(0), _num(out,'pred_goal90',np.nan))
    out['model_xa90'] = out['model_xa90'].where(mins.gt(0), _num(out,'pred_assist90',np.nan))
    out.loc[~available,['model_xg90','model_xa90']]=np.nan

    total_slots = {r: rules.slots()[r] * rules.managers for r in rules.slots()}
    replacement = {}
    for r, n in total_slots.items():
        vals = pd.to_numeric(out.loc[role.eq(r)&available, 'independent_points'], errors='coerce').dropna().sort_values(ascending=False)
        idx = min(len(vals)-1, max(0, int(np.ceil(n*1.08))-1)) if len(vals) else 0
        replacement[r] = float(vals.iloc[idx]) if len(vals) else 0.0
    out['replacement_points'] = role.map(replacement).fillna(0)
    out['vorp'] = (pd.to_numeric(out['independent_points'], errors='coerce') - out['replacement_points']).clip(lower=0)

    out['production_component'] = .62*_role_percentile(out, 'independent_points') + .23*_role_percentile(out, 'model_xg90') + .15*_role_percentile(out, 'model_xa90')
    out['availability_component'] = .65*_role_percentile(out, 'projected_minutes') + .35*_num(out, 'minutes_confidence', .35).fillna(.35).clip(0,1)
    team_attack = _num(out, 'team_context_factor', 1).fillna(1); team_def = _num(out, 'team_defense_factor', 1).fillna(1); sched = _num(out, 'schedule_factor_used', 1).fillna(1)
    team_raw = np.where(role.isin(['P','D']), .70*team_def+.30*sched, .70*team_attack+.30*sched)
    out['context_component'] = pd.Series(team_raw,index=out.index).groupby(role).rank(pct=True).fillna(.5)
    out['scarcity_component'] = _role_percentile(out, 'vorp')
    out['certainty_component'] = _num(out, 'reliability', .35).fillna(.35).clip(0,1)

    # Modifier readiness affects ranking only when the league actually enables it.
    # This is a selection-quality signal; actual modifier points remain portfolio-level.
    avg_vote=_num(out,'avg_vote',6.0).fillna(6.0)
    mod_base=(avg_vote-5.6).clip(lower=0) * (.55+.45*out['certainty_component']) * (_num(out,'projected_minutes',0).fillna(0)/3420).clip(0,1)
    out['modifier_readiness']=mod_base.groupby(role).rank(pct=True).fillna(.5)
    mod_active=role.isin(['P','D']) & bool(rules.defense_modifier)

    raw = (0.48*out['production_component'] + 0.18*out['availability_component'] +
           0.14*out['scarcity_component'] + 0.08*out['context_component'] +
           0.12*out['certainty_component'])
    if rules.defense_modifier:
        # Reweight P/D toward reliable average-vote profiles without inventing an individual bonus.
        raw = raw.where(~mod_active, .88*raw + .12*out['modifier_readiness'])

    conf = out['certainty_component']
    out['independent_score_v1'] = (100*(.50 + (raw-.50)*(.55+.45*conf))).clip(0,100)
    out['independent_score_floor'] = (out['independent_score_v1'] - 18*(1-conf)).clip(0,100)
    out['independent_score_ceiling'] = (out['independent_score_v1'] + 18*(1-conf)).clip(0,100)

    min_spend = rules.min_bid * sum(rules.slots().values()); discretionary_per_manager = max(0, rules.budget-min_spend); pool_budget = discretionary_per_manager * rules.managers
    value_weight = out['vorp'].pow(1.18) * (.70+.30*conf)
    if rules.defense_modifier:
        value_weight = value_weight * np.where(mod_active, .90+.20*out['modifier_readiness'], 1.0)
    value_weight=value_weight.where(available,0.0)
    denom = float(value_weight.sum())
    out['independent_fair_price'] = rules.min_bid + (pool_budget*value_weight/denom if denom>0 else 0)
    out['independent_fair_price'] = out['independent_fair_price'].clip(lower=rules.min_bid).where(available,np.nan)

    out=add_canonical_valuation(out,rules)
    if 'fvm_1000' in out:
        market = out['market_price_from_fvm']
        out['independent_price_edge'] = out['independent_fair_price'] - market
        out['independent_price_edge_conf_adj'] = out['independent_price_edge'] * conf
    unavailable_outputs=['replacement_points','vorp','production_component','availability_component','context_component',
                         'scarcity_component','certainty_component','modifier_readiness','independent_score_v1',
                         'independent_score_floor','independent_score_ceiling']
    out.loc[~available,[c for c in unavailable_outputs if c in out]]=np.nan
    return out.sort_values(['prediction_available','role','independent_score_v1'],ascending=[False,True,False],na_position='last').reset_index(drop=True)
