import pandas as pd

from src.fanta_lab.auction import AuctionState, live_recommendation
from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.sources.auction_market import attach_market_prior


def rules4():
    return LeagueRules(budget=100, managers=4, slots_gk=1, slots_def=1, slots_mid=1, slots_fwd=2)


def row(name='Star', pts=100, fair=28):
    return {'player':name,'team':'X','role':'A','independent_points':pts,'fair_price':fair,'reliability':.9,'edge_confidence_adjusted':8,'market_auction_price':30}


def test_short_top_supply_never_reduces_strategic_bid():
    r=rules4(); state=AuctionState(r,['Me','A','B','C'],'Me')
    shortage=pd.DataFrame([row()]+[row(f'Low{i}',70-i,8) for i in range(8)])
    ample=pd.DataFrame([row()]+[row(f'Peer{i}',98-i*.3,25) for i in range(10)])
    a=live_recommendation(shortage.iloc[0],shortage,state)
    b=live_recommendation(ample.iloc[0],ample,state)
    assert a['shortage_risk'] >= b['shortage_risk']
    assert a['max_bid'] >= b['max_bid']


def test_hard_cap_preserves_one_credit_per_remaining_slot():
    r=rules4(); state=AuctionState(r,['Me','A','B','C'],'Me')
    state.add_purchase(AuctionPurchase('Me','Bought','D',95,10))
    pool=pd.DataFrame([row()]+[row(f'Low{i}',60-i,4) for i in range(8)])
    rec=live_recommendation(pool.iloc[0],pool,state)
    assert rec['max_bid'] <= rec['hard_cap']
    assert rec['hard_cap'] == 2  # 5 left; buying this player must reserve 3 credits for the other 3 slots


def test_real_market_bucket_scales_to_exact_budget():
    players=pd.DataFrame([{'player':'Lautaro Martinez','role':'A'}])
    market=pd.DataFrame([{'player_key':'LAUTAROMARTINEZ','market_8_500':100.0}])
    out=attach_market_prior(players,market,managers=8,budget=600)
    assert out.loc[0,'market_auction_price'] == 120.0
