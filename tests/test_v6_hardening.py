import pandas as pd

from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.projection import project_player
from src.fanta_lab.auction import AuctionState, simulated_clearing_price
from src.fanta_lab.health import dataset_health, auction_health


def test_expected_minutes_add_value_to_total_points():
    r=LeagueRules()
    starter=pd.Series({'role':'C','minutes':3000,'goals':0,'assists':0,'xg':0,'xa':0,'avg_vote':6.0,'data_confidence':1.0})
    reserve=pd.Series({'role':'C','minutes':600,'goals':0,'assists':0,'xg':0,'xa':0,'avg_vote':6.0,'data_confidence':1.0})
    assert project_player(starter,r)['independent_points'] > project_player(reserve,r)['independent_points']


def test_goalkeeper_rule_changes_projection():
    row=pd.Series({'role':'P','minutes':3000,'avg_vote':6.2,'goals_conceded_per90':1.2,'data_confidence':1.0})
    a=project_player(row,LeagueRules(goal_conceded_gk=-1.0))['independent_points']
    b=project_player(row,LeagueRules(goal_conceded_gk=0.0))['independent_points']
    assert b>a


def test_simulation_is_cached_for_same_state():
    r=LeagueRules(budget=100,managers=3,slots_gk=1,slots_def=1,slots_mid=1,slots_fwd=1)
    state=AuctionState(r,['Me','A','B'],'Me')
    pool=pd.DataFrame([{'player':'Star','role':'A','fair_price':25,'market_auction_price':26,'independent_points':200}])
    first=simulated_clearing_price(pool.iloc[0],pool,state,n=50)
    size=len(state._sim_cache)
    second=simulated_clearing_price(pool.iloc[0],pool,state,n=50)
    assert first==second and len(state._sim_cache)==size==1


def test_forecast_calibration_learns_systematic_underprediction():
    r=LeagueRules(budget=500,managers=4,slots_gk=1,slots_def=1,slots_mid=1,slots_fwd=4)
    s=AuctionState(r,['Me','A','B','C'],'Me')
    for i in range(5):
        s.add_purchase(AuctionPurchase('A',f'P{i}','A',120,100,100,100))
    assert s.forecast_calibration('A')>1.0


def test_dataset_health_detects_duplicate_and_team_gap():
    df=pd.DataFrame([{'player':'X','team':'A','role':'A','fvm_1000':10,'minutes':100},{'player':'X','team':'A','role':'A','fvm_1000':10,'minutes':100}])
    h=dataset_health(df)
    assert h['status']=='NOT_READY'
    assert h['metrics']['duplicates']==1


def test_auction_health_detects_duplicate_sale():
    r=LeagueRules(budget=100,managers=2,slots_gk=1,slots_def=1,slots_mid=1,slots_fwd=1)
    s=AuctionState(r,['Me','A'],'Me')
    s.add_purchase(AuctionPurchase('Me','X','A',10))
    s.add_purchase(AuctionPurchase('A','X','A',10))
    assert auction_health(s)['status']=='INVALID'
