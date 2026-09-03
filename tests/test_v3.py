import pandas as pd
from src.fanta_lab.reconcile import build_master_roster
from src.fanta_lab.models import LeagueRules,AuctionPurchase
from src.fanta_lab.projection import add_projections
from src.fanta_lab.auction import AuctionState,live_recommendation

def test_official_listone_is_lossless_and_excludes_roster_only_players():
    roster=pd.DataFrame([{'player':f'P{i}','team':f'T{i%20}','role':'C'} for i in range(400)] + [{'player':'Fuori Listone','team':'T1','role':'A'}])
    fanta=pd.DataFrame([{'player':f'P{i}','team_fanta':f'T{i%20}','role_fanta':'C','fvm_1000':10} for i in range(400)] + [{'player':'Nuovo Colpo','team_fanta':'T1','role_fanta':'A','fvm_1000':80}])
    master,rep=build_master_roster(roster,fanta)
    assert 'Nuovo Colpo' in set(master.player)
    assert 'Fuori Listone' not in set(master.player)
    assert len(master)==len(fanta)
    assert master.official_listone.all()
    assert rep.certified

def test_newcomer_without_observed_history_is_explicitly_not_predicted():
    rules=LeagueRules(); df=pd.DataFrame([{'player':'X','team':'T','role':'A','minutes':0,'fvm_1000':100,'data_confidence':.7}])
    out=add_projections(df,rules)
    assert not bool(out.loc[0,'prediction_available'])
    assert out.loc[0,'prediction_status']=='NON DISPONIBILE'
    assert 'Dati insufficienti' in out.loc[0,'prediction_reason']
    assert pd.isna(out.loc[0,'projected_minutes'])
    assert pd.isna(out.loc[0,'pred_goal90'])

def test_rival_demand_affects_recommendation():
    rules=LeagueRules(budget=500,managers=3,slots_gk=1,slots_def=1,slots_mid=1,slots_fwd=1)
    pool=pd.DataFrame([{'player':f'A{i}','role':'A','independent_points':100-i*5,'fair_price':30,'reliability':.8,'edge_vs_market':5} for i in range(6)])
    state=AuctionState(rules,['Me','R1','R2'],'Me')
    for j in range(3): state.add_purchase(AuctionPurchase('R1',f'X{j}','C',30,20))
    rec=live_recommendation(pool.iloc[0],pool,state)
    assert rec['max_bid']<=state.remaining('Me')-3
    assert rec['demand']>=0
