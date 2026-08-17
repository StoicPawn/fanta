import pandas as pd
from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.projection import project_player
from src.fanta_lab.auction import AuctionState

def test_projection_rewards_xg():
    r=LeagueRules()
    a=pd.Series({'role':'A','minutes':1800,'goals':5,'xg':6,'assists':2,'xa':2,'yellow_cards':1,'red_cards':0})
    b=a.copy(); b['xg']=12
    assert project_player(b,r)['independent_points'] > project_player(a,r)['independent_points']

def test_auction_budget_reserve():
    r=LeagueRules(budget=100, managers=2, slots_gk=1, slots_def=1, slots_mid=1, slots_fwd=1)
    s=AuctionState(r,['me','x'],'me')
    s.add_purchase(AuctionPurchase('me','A','A',90,50))
    assert s.remaining('me') == 10
    assert s.slots_left('me')['A'] == 0
