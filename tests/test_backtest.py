import pandas as pd

from fanta_lab.backtest import season_slug, _spearman, _top_fraction_overlap
from fanta_lab.models import LeagueRules
from fanta_lab.projection import estimate_minutes
from fanta_lab.independent_model import build_independent_valuation


def test_season_slug():
    assert season_slug(2024)=='2024-25'
    assert season_slug(2019)=='2019-20'


def test_minutes_do_not_use_market_fields():
    base=pd.Series({'role':'A','minutes':1800,'goals':10,'assists':3})
    a=base.copy(); a['fvm_1000']=1; a['quotation']=1
    b=base.copy(); b['fvm_1000']=900; b['quotation']=80
    assert estimate_minutes(a)==estimate_minutes(b)


def test_no_history_minutes_do_not_use_market_fields():
    a=pd.Series({'role':'C','minutes':0,'fvm_1000':1,'quotation':1})
    b=pd.Series({'role':'C','minutes':0,'fvm_1000':999,'quotation':99})
    assert estimate_minutes(a)==estimate_minutes(b)


def test_independent_fair_price_market_isolation():
    rows=[
        {'player':'A','role':'A','minutes':2500,'goals':15,'assists':5,'xg':14,'xa':5,'avg_vote':6.5,'data_confidence':.9,'fvm_1000':10},
        {'player':'B','role':'A','minutes':2200,'goals':9,'assists':4,'xg':10,'xa':4,'avg_vote':6.2,'data_confidence':.85,'fvm_1000':200},
        {'player':'C','role':'A','minutes':1200,'goals':4,'assists':2,'xg':4,'xa':2,'avg_vote':6.0,'data_confidence':.8,'fvm_1000':500},
    ]
    rules=LeagueRules(managers=1,slots_gk=0,slots_def=0,slots_mid=0,slots_fwd=1)
    x=pd.DataFrame(rows); y=x.copy(); y['fvm_1000']=[900,1,2]
    a=build_independent_valuation(x,rules).set_index('player')
    b=build_independent_valuation(y,rules).set_index('player')
    pd.testing.assert_series_equal(a.independent_score_v1.sort_index(),b.independent_score_v1.sort_index())
    pd.testing.assert_series_equal(a.independent_fair_price.sort_index(),b.independent_fair_price.sort_index())


def test_backtest_metrics_helpers():
    assert _spearman(pd.Series([1,2,3]),pd.Series([10,20,30])) > .99
    rows=[]
    for role in ['P','D','C','A']:
        for i in range(10): rows.append({'player':f'{role}{i}','role':role,'pred':i,'actual':i})
    frame=pd.DataFrame(rows)
    assert _top_fraction_overlap(frame,'pred','actual')==1.0
