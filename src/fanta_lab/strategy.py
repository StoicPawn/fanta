from __future__ import annotations

import math
import pandas as pd
import pulp

from .auction import AuctionState, live_recommendation


def expected_price(row: pd.Series, pool: pd.DataFrame, state: AuctionState, risk_tolerance: float=.58) -> float:
    rec = live_recommendation(row, pool, state, risk_tolerance=risk_tolerance)
    return max(1.0, float(rec.get('expected_clearing', row.get('fair_price', 1)) or 1))


def continuation_plan(pool: pd.DataFrame, state: AuctionState, risk_tolerance: float=.58,
                      exclude: set[str] | None=None, forced: tuple[str,float] | None=None) -> dict:
    """Best expected continuation roster from the current room state.

    Prices are expected clearing prices, not static fair values. This makes the plan react
    to room inflation, budgets, remaining demand and scarcity. `forced=(player, price)` can
    be used to evaluate a BUY-NOW scenario against WAIT/SKIP.
    """
    me = state.my_manager
    exclude = exclude or set()
    sold = {p.player for p in state.purchases}
    avail = pool[(~pool.player.isin(sold | exclude))].copy()
    slots = state.slots_left(me).copy()
    budget = float(state.remaining(me))
    forced_points = 0.0
    forced_name = None

    if forced:
        forced_name, forced_price = forced
        hit = avail[avail.player == forced_name]
        if hit.empty:
            return {'feasible': False, 'reason': 'forced player unavailable'}
        rr = hit.iloc[0]
        role = str(rr.role)
        if slots.get(role, 0) <= 0 or forced_price > budget:
            return {'feasible': False, 'reason': 'forced player violates role/budget'}
        slots[role] -= 1
        budget -= float(forced_price)
        forced_points = float(rr.get('independent_points', 0) or 0)
        avail = avail[avail.player != forced_name]

    candidates = []
    for _, row in avail.iterrows():
        role = str(row.role)
        if slots.get(role, 0) <= 0:
            continue
        price = expected_price(row, pool, state, risk_tolerance)
        points = float(row.get('independent_points', 0) or 0)
        edge = float(row.get('edge_confidence_adjusted', 0) or 0)
        reliability = float(row.get('reliability', .5) or .5)
        utility = points + .06 * edge + .02 * points * reliability
        candidates.append((row.player, role, price, points, utility))

    need = sum(slots.values())
    if need == 0:
        return {'feasible': True, 'points': forced_points, 'cost': float(forced[1]) if forced else 0.0,
                'players': [forced_name] if forced_name else []}
    if len(candidates) < need:
        return {'feasible': False, 'reason': 'not enough players'}

    prob = pulp.LpProblem('continuation', pulp.LpMaximize)
    xs = [pulp.LpVariable(f'x{i}', cat='Binary') for i in range(len(candidates))]
    prob += pulp.lpSum(xs[i] * candidates[i][4] for i in range(len(candidates)))
    prob += pulp.lpSum(xs[i] * candidates[i][2] for i in range(len(candidates))) <= budget
    for role, n in slots.items():
        ids = [i for i, c in enumerate(candidates) if c[1] == role]
        prob += pulp.lpSum(xs[i] for i in ids) == n
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[prob.status] != 'Optimal':
        return {'feasible': False, 'reason': pulp.LpStatus[prob.status]}

    picked = [candidates[i] for i in range(len(candidates)) if pulp.value(xs[i]) > .5]
    return {
        'feasible': True,
        'points': forced_points + sum(x[3] for x in picked),
        'cost': (float(forced[1]) if forced else 0.0) + sum(x[2] for x in picked),
        'players': ([forced_name] if forced_name else []) + [x[0] for x in picked],
        'details': [{'player':x[0],'role':x[1],'expected_price':round(x[2],1),'points':round(x[3],1)} for x in picked],
    }


def buy_vs_wait(player_row: pd.Series, pool: pd.DataFrame, state: AuctionState,
                risk_tolerance: float=.58) -> dict:
    """Compare taking the called player now with skipping him and optimising the rest.

    The recommended bid can exceed static fair value when losing the tier creates a larger
    expected roster-value loss than the overpay. This directly addresses the '100 vs 101'
    failure mode of rigid auction sheets.
    """
    rec = live_recommendation(player_row, pool, state, risk_tolerance=risk_tolerance)
    clearing = max(1.0, float(rec.get('expected_clearing', 1)))
    max_bid = float(rec.get('max_bid', 0))
    if max_bid < 1:
        return {'decision': 'SKIP', 'buy_feasible': False, 'wait_feasible': True, 'roster_delta': 0.0}

    buy_price = min(max_bid, max(clearing, 1.0))
    buy = continuation_plan(pool, state, risk_tolerance, forced=(str(player_row.player), buy_price))
    wait = continuation_plan(pool, state, risk_tolerance, exclude={str(player_row.player)})
    if not buy.get('feasible'):
        return {'decision':'SKIP','buy_feasible':False,'wait_feasible':wait.get('feasible',False),'roster_delta':-math.inf}
    if not wait.get('feasible'):
        return {'decision':'MUST_BUY','buy_feasible':True,'wait_feasible':False,'roster_delta':math.inf,
                'buy_price':round(buy_price,1),'buy_points':round(buy['points'],1)}

    delta = float(buy['points']) - float(wait['points'])
    # One projected point of season value is worth roughly the room's average discretionary
    # price per remaining slot. This converts continuation advantage to a practical premium.
    avg_credit = state.discretionary_budget(state.my_manager) / max(1, sum(state.slots_left(state.my_manager).values()))
    premium = max(0.0, delta) * max(.02, avg_credit / max(100.0, abs(float(player_row.get('independent_points',100) or 100))))
    strategic_bid = min(float(rec['hard_cap']), max(max_bid, math.ceil(clearing + premium)))
    decision = 'BUY' if delta > 0 else 'WAIT'
    return {
        'decision': decision,
        'buy_feasible': True,
        'wait_feasible': True,
        'roster_delta': round(delta,2),
        'buy_price': round(buy_price,1),
        'strategic_bid': int(strategic_bid),
        'buy_points': round(float(buy['points']),1),
        'wait_points': round(float(wait['points']),1),
        'buy_plan': buy.get('details',[]),
        'wait_plan': wait.get('details',[]),
    }


def role_budget_envelopes(pool: pd.DataFrame, state: AuctionState, risk_tolerance: float=.58) -> pd.DataFrame:
    """Expected spend required to complete each role at current room prices."""
    me = state.my_manager
    sold = {p.player for p in state.purchases}
    rows=[]
    for role, need in state.slots_left(me).items():
        if need <= 0:
            rows.append({'role':role,'slots_left':0,'minimum_expected':0,'balanced_expected':0,'top_tier_expected':0})
            continue
        g = pool[(pool.role==role)&(~pool.player.isin(sold))].copy()
        vals=[]
        for _,x in g.head(max(need*8,20)).iterrows():
            vals.append((float(x.get('independent_points',0) or 0), expected_price(x,pool,state,risk_tolerance)))
        vals.sort(reverse=True)
        prices=sorted([p for _,p in vals])
        minimum=sum(prices[:need]) if len(prices)>=need else math.inf
        balanced=sum([p for _,p in vals[max(0,need):max(0,need)+need]]) if len(vals)>=2*need else minimum
        top=sum([p for _,p in vals[:need]]) if len(vals)>=need else minimum
        rows.append({'role':role,'slots_left':need,'minimum_expected':round(minimum,1),'balanced_expected':round(balanced,1),'top_tier_expected':round(top,1)})
    return pd.DataFrame(rows)
