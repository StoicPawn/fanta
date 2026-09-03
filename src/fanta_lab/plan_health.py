from __future__ import annotations

import numpy as np
import pandas as pd

from .models import LeagueRules
from .target_engine import TargetPlan


def _n(df: pd.DataFrame, col: str, default=0.0) -> pd.Series:
    if col not in df:
        return pd.Series(default,index=df.index,dtype=float)
    return pd.to_numeric(df[col],errors='coerce').fillna(default)

def _prediction_mask(df:pd.DataFrame)->pd.Series:
    if 'prediction_available' not in df:
        return pd.Series(True,index=df.index,dtype=bool)
    return df['prediction_available'].fillna(False).astype(bool)


def role_spend_envelopes(plan: TargetPlan, rules: LeagueRules, remaining_budget: float | None=None) -> pd.DataFrame:
    """Give soft spend corridors by role around the current optimal portfolio.

    These are guidance, not hard constraints.  Wider corridors are used where the
    role has more uncertainty; the total midpoint remains tied to the current plan.
    """
    if plan is None or plan.squad.empty:
        return pd.DataFrame(columns=['role','target','soft_min','soft_max','share_pct'])
    total=float(plan.spend or rules.budget)
    rows=[]
    for role in ['P','D','C','A']:
        target=float(plan.role_budget.get(role,0.0))
        g=plan.squad[plan.squad.role.astype(str).str.upper().eq(role)]
        rel=float(_n(g,'reliability',.5).mean()) if len(g) else .5
        width=.12 + .13*(1-rel)
        if role in {'P','D'} and rules.defense_modifier:
            width += .05
        rows.append({'role':role,'target':round(target,1),'soft_min':round(max(rules.min_bid*rules.slots().get(role,0),target*(1-width)),1),
                     'soft_max':round(target*(1+width),1),'share_pct':round(100*target/max(1,total),1)})
    return pd.DataFrame(rows)


def plan_resilience(pool: pd.DataFrame, plan: TargetPlan, sold_players: set[str] | None=None,
                    tolerance: float=.92) -> pd.DataFrame:
    """Measure how many near-equivalent alternatives remain for each planned player.

    `tolerance=.92` means an alternative preserving >=92% of the player's expected
    points is considered viable.  Prices are also checked so an apparent substitute
    that is much more expensive does not make the plan look safer than it is.
    """
    sold_players=sold_players or set()
    if plan is None or plan.squad.empty:
        return pd.DataFrame()
    available=pool[_prediction_mask(pool)&~pool.player.isin(sold_players)].copy()
    rows=[]
    for _,p in plan.squad.iterrows():
        role=str(p.role).upper(); pts=float(p.get('independent_points',0) or 0); price=float(p.get('target_price',p.get('independent_fair_price',1)) or 1)
        cand=available[(available.role.astype(str).str.upper()==role)&(available.player!=p.player)].copy()
        cpts=_n(cand,'independent_points',0); cprice=_n(cand,'independent_fair_price',_n(cand,'fair_price',1)).clip(lower=1)
        viable=cand[(cpts>=pts*tolerance)&(cprice<=max(price*1.22,price+8))]
        n=int(len(viable))
        risk='LOW' if n>=5 else 'MEDIUM' if n>=2 else 'HIGH'
        rows.append({'player':p.player,'role':role,'alternatives':n,'fragility':risk,'target_points':round(pts,1),'target_price':round(price,1)})
    return pd.DataFrame(rows).sort_values(['fragility','alternatives'],ascending=[False,True])


def role_risk_summary(resilience: pd.DataFrame, plan: TargetPlan) -> pd.DataFrame:
    if resilience is None or resilience.empty:
        return pd.DataFrame(columns=['role','high_risk_targets','median_alternatives','risk_score'])
    rows=[]
    for role,g in resilience.groupby('role'):
        high=int((g.fragility=='HIGH').sum()); med=float(g.alternatives.median())
        score=float(np.clip(.55*high/max(1,len(g)) + .45*(1-min(1,med/5)),0,1))
        rows.append({'role':role,'high_risk_targets':high,'median_alternatives':round(med,1),'risk_score':round(score,2)})
    return pd.DataFrame(rows).sort_values('risk_score',ascending=False)


def alternative_buckets(called: pd.Series, candidates: pd.DataFrame) -> dict[str,pd.DataFrame]:
    """Split live alternatives into human-readable tactical buckets."""
    if candidates is None or candidates.empty:
        return {'same_tier':pd.DataFrame(),'value':pd.DataFrame(),'emergency':pd.DataFrame()}
    x=candidates.copy()
    called_score=float(called.get('independent_score_v1',50) or 50)
    score=_n(x,'independent_score_v1',50)
    saved=_n(x,'price_saved',0)
    same=x[(score>=called_score-6)].sort_values('replacement_fit',ascending=False).head(5)
    value=x[(saved>=3)&(score>=called_score-14)].sort_values(['replacement_fit','price_saved'],ascending=False).head(5)
    emergency=x.sort_values(['reliability','replacement_fit'] if 'reliability' in x else ['replacement_fit'],ascending=False).head(5)
    return {'same_tier':same.reset_index(drop=True),'value':value.reset_index(drop=True),'emergency':emergency.reset_index(drop=True)}
