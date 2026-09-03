import pandas as pd
from fanta_lab.models import LeagueRules
from fanta_lab.independent_model import build_independent_valuation


def sample():
    return pd.DataFrame([
        {'player':'Elite','team':'A','role':'A','minutes':2800,'goals':18,'assists':7,'xg':17,'xa':6,'avg_vote':6.5,'data_confidence':.9,'team_attack_strength':1.15,'team_defense_strength':1.0,'fvm_1000':300},
        {'player':'Solid','team':'B','role':'A','minutes':2600,'goals':10,'assists':5,'xg':11,'xa':5,'avg_vote':6.2,'data_confidence':.85,'team_attack_strength':1.0,'team_defense_strength':1.0,'fvm_1000':200},
        {'player':'Bench','team':'C','role':'A','minutes':800,'goals':2,'assists':1,'xg':2.5,'xa':1.5,'avg_vote':6.0,'data_confidence':.8,'team_attack_strength':.9,'team_defense_strength':1.0,'fvm_1000':50},
    ])


def test_elite_ranks_above_bench():
    out=build_independent_valuation(sample(),LeagueRules(managers=1,slots_fwd=1,slots_gk=0,slots_def=0,slots_mid=0))
    s=out.set_index('player').independent_score_v1
    assert s['Elite'] > s['Bench']


def test_market_fvm_does_not_change_independent_score():
    rules=LeagueRules(managers=1,slots_fwd=1,slots_gk=0,slots_def=0,slots_mid=0)
    a=sample(); b=sample(); b['fvm_1000']=[1,999,500]
    sa=build_independent_valuation(a,rules).set_index('player').independent_score_v1.sort_index()
    sb=build_independent_valuation(b,rules).set_index('player').independent_score_v1.sort_index()
    pd.testing.assert_series_equal(sa,sb)


def test_fair_prices_respect_min_bid():
    out=build_independent_valuation(sample(),LeagueRules(managers=1,slots_fwd=1,slots_gk=0,slots_def=0,slots_mid=0,min_bid=1))
    assert (out.independent_fair_price >= 1).all()


def test_insufficient_data_never_creates_model_outputs_from_fvm():
    players=sample()
    players.loc[len(players)]={'player':'New','team':'D','role':'A','minutes':0,'goals':0,'assists':0,'xg':None,'xa':None,'avg_vote':None,'data_confidence':.8,'team_attack_strength':1.2,'team_defense_strength':1.0,'fvm_1000':400}
    out=build_independent_valuation(players,LeagueRules(managers=1,slots_fwd=1,slots_gk=0,slots_def=0,slots_mid=0)).set_index('player')
    row=out.loc['New']
    assert not bool(row.prediction_available)
    assert pd.isna(row.independent_points)
    assert pd.isna(row.independent_score_v1)
    assert pd.isna(row.independent_fair_price)
    assert pd.notna(row.market_price_from_fvm)
    assert row.canonical_value == 200
    assert 'FVM scalato' in row.canonical_value_source


def test_official_quotation_is_reported_if_fvm_is_missing():
    players=pd.DataFrame([{'player':'New','team':'D','role':'A','minutes':0,'quotation':17,'fvm_1000':None}])
    row=build_independent_valuation(players,LeagueRules(budget=500)).iloc[0]
    assert not bool(row.prediction_available)
    assert row.canonical_value == 17
    assert row.canonical_value_unit == 'quotazione ufficiale'
    assert pd.isna(row.independent_fair_price)
