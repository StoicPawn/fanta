import pandas as pd

from fanta_lab.models import LeagueRules
from fanta_lab.target_engine import TargetPlan
from fanta_lab.plan_health import role_spend_envelopes, plan_resilience, role_risk_summary, alternative_buckets


def _plan():
    squad=pd.DataFrame([
        {'player':'P1','role':'P','independent_points':200,'target_price':20,'reliability':.9},
        {'player':'D1','role':'D','independent_points':190,'target_price':30,'reliability':.8},
        {'player':'C1','role':'C','independent_points':210,'target_price':60,'reliability':.85},
        {'player':'A1','role':'A','independent_points':240,'target_price':100,'reliability':.9},
    ])
    return TargetPlan(squad,210,840,0,840,{'P':20,'D':30,'C':60,'A':100})


def test_spend_envelopes_contain_target():
    r=LeagueRules(slots_gk=1,slots_def=1,slots_mid=1,slots_fwd=1)
    x=role_spend_envelopes(_plan(),r)
    assert ((x.soft_min<=x.target)&(x.target<=x.soft_max)).all()


def test_resilience_detects_alternatives():
    pool=pd.DataFrame([
        {'player':'P1','role':'P','independent_points':200,'independent_fair_price':20},
        {'player':'P2','role':'P','independent_points':195,'independent_fair_price':21},
        {'player':'D1','role':'D','independent_points':190,'independent_fair_price':30},
        {'player':'C1','role':'C','independent_points':210,'independent_fair_price':60},
        {'player':'A1','role':'A','independent_points':240,'independent_fair_price':100},
    ])
    x=plan_resilience(pool,_plan())
    assert int(x.loc[x.player=='P1','alternatives'].iloc[0])==1
    assert not role_risk_summary(x,_plan()).empty


def test_alternative_buckets_returns_keys():
    called=pd.Series({'independent_score_v1':90})
    cand=pd.DataFrame([{'player':'x','independent_score_v1':87,'price_saved':5,'replacement_fit':90,'reliability':.8}])
    b=alternative_buckets(called,cand)
    assert set(b)=={'same_tier','value','emergency'}
