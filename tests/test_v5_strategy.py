import pandas as pd

from src.fanta_lab.models import LeagueRules
from src.fanta_lab.auction import AuctionState
from src.fanta_lab.strategy import continuation_plan, buy_vs_wait, role_budget_envelopes


def make_pool():
    rows=[]
    for role,n in [('P',8),('D',12),('C',12),('A',12)]:
        for i in range(n):
            rows.append({'player':f'{role}{i}','team':'X','role':role,'independent_points':100-i*3,'fair_price':max(1,30-i),'reliability':.9,'edge_confidence_adjusted':4,'market_auction_price':max(1,31-i)})
    return pd.DataFrame(rows)


def state():
    rules=LeagueRules(budget=100,managers=4,slots_gk=1,slots_def=1,slots_mid=1,slots_fwd=1)
    return AuctionState(rules,['Me','A','B','C'],'Me')


def test_continuation_plan_fills_all_roles():
    pool=make_pool(); s=state()
    plan=continuation_plan(pool,s,.5)
    assert plan['feasible']
    assert len(plan['players'])==4


def test_buy_vs_wait_returns_strategic_comparison():
    pool=make_pool(); s=state(); row=pool[pool.player=='A0'].iloc[0]
    out=buy_vs_wait(row,pool,s,.5)
    assert out['decision'] in {'BUY','WAIT','MUST_BUY','SKIP'}
    assert 'roster_delta' in out


def test_role_budget_envelopes_cover_roles():
    env=role_budget_envelopes(make_pool(),state(),.5)
    assert set(env.role)=={'P','D','C','A'}
