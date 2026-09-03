from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pulp

from .models import LeagueRules, AuctionPurchase


@dataclass
class TargetPlan:
    squad: pd.DataFrame
    spend: float
    expected_points: float
    expected_modifier_points: float
    objective: float
    role_budget: dict[str, float]


def _num(df: pd.DataFrame, col: str, default=0.0) -> pd.Series:
    if col not in df:
        return pd.Series(default, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors='coerce').fillna(default)

def _prediction_mask(df:pd.DataFrame)->pd.Series:
    if 'prediction_available' not in df:
        return pd.Series(True,index=df.index,dtype=bool)
    return df['prediction_available'].fillna(False).astype(bool)


def _modifier_quality(df: pd.DataFrame) -> pd.Series:
    vote = _num(df, 'avg_vote', 6.0).clip(5.0, 7.5)
    rel = _num(df, 'reliability', .35).clip(0,1)
    mins = _num(df, 'projected_minutes', 0).clip(0,3420) / 3420.0
    # Expected lineup-grade quality, not a direct fantasy bonus.
    return (vote - 5.7).clip(lower=0) * (.55 + .25*rel + .20*mins)


def expected_defence_modifier(squad: pd.DataFrame, rules: LeagueRules) -> float:
    if not rules.defense_modifier or squad.empty:
        return 0.0
    gk = squad[squad.role.astype(str).str.upper().eq('P')].copy()
    de = squad[squad.role.astype(str).str.upper().eq('D')].copy()
    need = max(3, int(rules.modifier_defenders_required))
    if gk.empty or len(de) < need:
        return 0.0
    gk['q'] = _modifier_quality(gk)
    de['q'] = _modifier_quality(de)
    # Proxy for the best commonly fielded modifier unit: best keeper + best N defenders.
    unit = pd.concat([gk.nlargest(1,'q'), de.nlargest(need,'q')])
    avg_vote = float(_num(unit,'avg_vote',6.0).mean())
    reliability = float(_num(unit,'reliability',.35).mean())
    # Smooth probability of crossing each threshold to avoid discontinuous valuations.
    expected = 0.0
    sigma = max(.11, .28*(1-reliability))
    previous_bonus = 0.0
    for threshold, bonus in rules.modifier_bands():
        z = (avg_vote-threshold)/sigma
        p = 1/(1+math.exp(-1.7*z))
        incremental = max(0.0, bonus-previous_bonus)
        expected += p*incremental
        previous_bonus = bonus
    return float(expected * rules.defense_modifier_strength)


def _candidate_price(df: pd.DataFrame) -> pd.Series:
    for c in ['expected_clearing','independent_fair_price','fair_price','market_auction_price']:
        if c in df and pd.to_numeric(df[c],errors='coerce').notna().any():
            x = pd.to_numeric(df[c],errors='coerce')
            fallback = pd.to_numeric(df.get('independent_fair_price',1),errors='coerce').fillna(1)
            return x.fillna(fallback).clip(lower=1)
    return pd.Series(1.0,index=df.index)


def build_target_plan(df: pd.DataFrame, rules: LeagueRules, budget: float | None=None,
                      locked: list[AuctionPurchase] | None=None, sold_players: set[str] | None=None) -> TargetPlan:
    """Optimise the squad to target before/during an auction.

    The base MILP maximises rule-specific expected points + VORP/certainty value under
    role and budget constraints. Defence-modifier synergy is handled by a second
    portfolio pass that rewards a strong, reliable P+D unit rather than assigning a
    fake individual modifier bonus to every defender.
    """
    budget=float(rules.budget if budget is None else budget)
    sold_players=sold_players or set()
    locked=locked or []
    locked_names={p.player for p in locked}
    eligible=_prediction_mask(df) | df.player.isin(locked_names)
    d=df[eligible & ~df.player.isin(sold_players-locked_names)].copy().reset_index(drop=True)
    d['role']=d.role.astype(str).str.upper()
    d['plan_price']=_candidate_price(d).clip(lower=rules.min_bid)
    d['points']=_num(d,'independent_points',0)
    d['vorp_plan']=_num(d,'vorp',0)
    d['certainty']=_num(d,'reliability',.35).clip(0,1)
    d['mod_q']=_modifier_quality(d)

    # Modifier-aware portfolio incentive only for P/D and only when enabled.
    mod_weight = 0.0
    if rules.defense_modifier:
        max_bonus=max((b for _,b in rules.modifier_bands()),default=0.0)
        mod_weight=max_bonus*rules.defense_modifier_strength*2.2
    d['objective_value']=d['points'] + .18*d['vorp_plan'] + 4.0*d['certainty']
    d.loc[d.role.isin(['P','D']),'objective_value'] += mod_weight*d.loc[d.role.isin(['P','D']),'mod_q']

    prob=pulp.LpProblem('target_squad',pulp.LpMaximize)
    xs=[pulp.LpVariable(f'x{i}',cat='Binary') for i in d.index]
    prob += pulp.lpSum(xs[i]*float(d.loc[i,'objective_value']) for i in d.index)

    locked_spend=sum(float(p.price) for p in locked)
    remaining_budget=max(0.0,budget-locked_spend)
    unlocked=[i for i in d.index if d.loc[i,'player'] not in locked_names]
    prob += pulp.lpSum(xs[i]*float(d.loc[i,'plan_price']) for i in unlocked) <= remaining_budget

    for i in d.index:
        if d.loc[i,'player'] in locked_names:
            prob += xs[i] == 1
    for r,n in rules.slots().items():
        ids=[i for i in d.index if d.loc[i,'role']==r]
        prob += pulp.lpSum(xs[i] for i in ids) == int(n)

    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    picked=d[[pulp.value(xs[i]) is not None and pulp.value(xs[i])>.5 for i in d.index]].copy()
    if len(picked) != sum(rules.slots().values()):
        return TargetPlan(pd.DataFrame(),0,0,0,float('-inf'),{})

    # Real locked prices replace projected prices in reporting.
    actual_price=dict((p.player,float(p.price)) for p in locked)
    picked['target_price']=picked.apply(lambda x: actual_price.get(x.player,float(x.plan_price)),axis=1)
    mod=expected_defence_modifier(picked,rules)
    spend=float(picked.target_price.sum())
    pts=float(picked.points.sum())
    role_budget=picked.groupby('role').target_price.sum().round(1).to_dict()
    picked['target_tier']=picked.groupby('role')['independent_score_v1'].transform(
        lambda s: pd.qcut(s.rank(method='first'),q=min(4,len(s)),labels=False,duplicates='drop') if len(s)>1 else 0
    ) if 'independent_score_v1' in picked else 0
    picked=picked.sort_values(['role','objective_value'],ascending=[True,False])
    return TargetPlan(picked,spend,pts,mod,pts+mod,role_budget)


def replacement_candidates(called: pd.Series, pool: pd.DataFrame, plan: TargetPlan,
                           rules: LeagueRules, sold_players:set[str]|None=None, top_n:int=8) -> pd.DataFrame:
    """Return substitutes that preserve the target plan when the called player is lost."""
    sold_players=sold_players or set()
    role=str(called.get('role','')).upper()
    target_names=set(plan.squad.player) if plan and not plan.squad.empty else set()
    candidates=pool[(pool.role.astype(str).str.upper()==role) & _prediction_mask(pool) & ~pool.player.isin(sold_players) & (pool.player!=called.get('player'))].copy()
    if candidates.empty:return candidates
    candidates['points']=_num(candidates,'independent_points',0)
    candidates['score']=_num(candidates,'independent_score_v1',50)
    candidates['fair']=_num(candidates,'independent_fair_price',_num(candidates,'fair_price',1))
    candidates['reliability_v']=_num(candidates,'reliability',.35)
    called_points=float(called.get('independent_points',0) or 0)
    called_score=float(called.get('independent_score_v1',50) or 50)
    called_price=float(called.get('independent_fair_price',called.get('fair_price',1)) or 1)
    candidates['points_retained']=candidates.points/max(1e-6,called_points) if called_points>0 else 1
    candidates['score_gap']=called_score-candidates.score
    candidates['price_saved']=called_price-candidates.fair
    candidates['already_in_target_plan']=candidates.player.isin(target_names)
    # Preference = preserve sporting output, save budget, maintain reliability, and stay inside the original portfolio.
    candidates['replacement_fit']=(
        55*candidates['points_retained'].clip(0,1.25)
        - .45*candidates['score_gap'].clip(lower=-20,upper=40)
        + .20*candidates['price_saved'].clip(-50,80)
        + 12*candidates['reliability_v']
        + 8*candidates['already_in_target_plan'].astype(float)
    )
    show=[c for c in ['player','team','role','independent_score_v1','independent_points','independent_fair_price','fair_price','reliability','points_retained','price_saved','already_in_target_plan','replacement_fit'] if c in candidates]
    return candidates.sort_values(['replacement_fit','independent_score_v1'],ascending=False)[show].head(top_n).reset_index(drop=True)
