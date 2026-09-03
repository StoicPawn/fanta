import pandas as pd

from fanta_lab.models import LeagueRules
from fanta_lab.target_engine import build_target_plan, expected_defence_modifier, replacement_candidates


def pool():
    rows=[]
    for role,n in [('P',3),('D',7),('C',5),('A',4)]:
        for i in range(n):
            score=95-i*5
            rows.append({'player':f'{role}{i}','team':'X','role':role,'independent_score_v1':score,'independent_points':200-i*8,
                         'independent_fair_price':20+i,'reliability':.9-i*.03,'vorp':60-i*5,'avg_vote':6.7-i*.08,'projected_minutes':3000-i*100})
    return pd.DataFrame(rows)


def test_target_plan_respects_slots_and_budget():
    rules=LeagueRules(budget=200,managers=1,slots_gk=1,slots_def=3,slots_mid=2,slots_fwd=2,min_bid=1)
    plan=build_target_plan(pool(),rules)
    assert len(plan.squad)==8
    assert plan.spend <= rules.budget
    assert plan.squad.role.value_counts().to_dict()=={'D':3,'C':2,'A':2,'P':1}


def test_modifier_is_portfolio_level_and_positive_for_good_unit():
    rules=LeagueRules(budget=200,managers=1,slots_gk=1,slots_def=4,slots_mid=1,slots_fwd=1,defense_modifier=True,modifier_defenders_required=4)
    plan=build_target_plan(pool(),rules)
    assert expected_defence_modifier(plan.squad,rules) > 0


def test_replacements_exclude_called_and_sold():
    rules=LeagueRules(budget=200,managers=1,slots_gk=1,slots_def=3,slots_mid=2,slots_fwd=2)
    p=pool(); plan=build_target_plan(p,rules)
    called=p[p.role=='A'].iloc[0]
    out=replacement_candidates(called,p,plan,rules,sold_players={'A1'},top_n=5)
    assert called.player not in set(out.player)
    assert 'A1' not in set(out.player)


def test_target_plan_never_selects_unpredicted_player():
    rules=LeagueRules(budget=200,managers=1,slots_gk=1,slots_def=3,slots_mid=2,slots_fwd=2,min_bid=1)
    p=pool()
    p['prediction_available']=True
    ghost=p.iloc[0].copy()
    ghost['player']='NoData'
    ghost['role']='A'
    ghost['prediction_available']=False
    ghost['independent_score_v1']=1000
    ghost['independent_points']=1000
    ghost['independent_fair_price']=1
    plan=build_target_plan(pd.concat([p,pd.DataFrame([ghost])],ignore_index=True),rules)
    assert 'NoData' not in set(plan.squad.player)
