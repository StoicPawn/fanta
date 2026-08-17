from __future__ import annotations
from collections import defaultdict
import numpy as np
import pandas as pd
from .models import LeagueRules, AuctionPurchase

class AuctionState:
    def __init__(self,rules:LeagueRules,manager_names:list[str],my_manager:str):
        self.rules=rules; self.manager_names=manager_names; self.my_manager=my_manager; self.purchases:list[AuctionPurchase]=[]
    def add_purchase(self,purchase:AuctionPurchase): self.purchases.append(purchase)
    def spent(self,m): return sum(p.price for p in self.purchases if p.manager==m)
    def remaining(self,m): return self.rules.budget-self.spent(m)
    def roster(self,m): return [p for p in self.purchases if p.manager==m]
    def slots_left(self,m):
        used=defaultdict(int)
        for p in self.roster(m): used[p.role]+=1
        return {r:max(0,n-used[r]) for r,n in self.rules.slots().items()}
    def inflation(self,role:str|None=None):
        ps=[p for p in self.purchases if p.fair_value_before and p.fair_value_before>0 and (role is None or p.role==role)]
        ratios=[p.price/p.fair_value_before for p in ps]
        if len(ratios)<3 and role is not None: return self.inflation(None)
        if len(ratios)<3:return 1.0
        return float(np.clip(np.median(ratios[-16:]),.65,1.85))
    def manager_aggression(self,m,role:str|None=None):
        ps=[p for p in self.purchases if p.manager==m and p.fair_value_before>0 and (role is None or p.role==role)]
        if len(ps)<2:return 1.0
        return float(np.clip(np.median([p.price/p.fair_value_before for p in ps]),.6,2.0))
    def demand_pressure(self,role:str):
        vals=[]
        for m in self.manager_names:
            if m==self.my_manager: continue
            need=self.slots_left(m).get(role,0); total=max(1,sum(self.slots_left(m).values()))
            budget_share=self.remaining(m)/max(1,self.rules.budget)
            vals.append((need/total)*budget_share*self.manager_aggression(m,role))
        return float(np.clip(np.mean(vals)*4 if vals else 0,0,1.5))

def allocate_fair_prices(df:pd.DataFrame,rules:LeagueRules,reserve_per_slot:float=1.0)->pd.DataFrame:
    out=df.copy(); slots_total=sum(rules.slots().values())*rules.managers; money=rules.budget*rules.managers-slots_total*reserve_per_slot
    out['surplus']=0.0
    for role,slots in rules.slots().items():
        g=out[out.role==role].sort_values('independent_points',ascending=False); n=slots*rules.managers
        replacement=float(g.iloc[min(len(g)-1,n-1)]['independent_points']) if len(g) else 0
        out.loc[g.index,'surplus']=(g.independent_points-replacement).clip(lower=0)
    conf=out.get('reliability',pd.Series(1,index=out.index)).clip(.25,1)
    out['auction_surplus']=out.surplus*(.70+.30*conf)
    s=out.auction_surplus.sum(); out['fair_price']=reserve_per_slot+(out.auction_surplus/s*money if s>0 else 0)
    return out

def live_recommendation(player_row:pd.Series,pool:pd.DataFrame,state:AuctionState)->dict:
    role=str(player_row.role); fair=float(player_row.get('fair_price',1)); infl=state.inflation(role); left=state.slots_left(state.my_manager)
    my_budget=state.remaining(state.my_manager); total_left=sum(left.values()); mandatory=max(0,total_left-1); hard_cap=max(0,my_budget-mandatory)
    if left.get(role,0)<=0:return {'max_bid':0,'decision':'SKIP_ROLE_FULL','inflation':infl,'hard_cap':hard_cap,'scarcity':0,'demand':0}
    sold={p.player for p in state.purchases}; avail=pool[(pool.role==role)&(~pool.player.isin(sold))].sort_values('independent_points',ascending=False)
    league_need=sum(state.slots_left(m).get(role,0) for m in state.manager_names)
    ridx=min(len(avail)-1,max(0,league_need-1)) if len(avail) else 0
    repl=float(avail.iloc[ridx].independent_points) if len(avail) else 0; pts=float(player_row.get('independent_points',0))
    scarcity=max(0,(pts-repl)/max(abs(pts),1)); demand=state.demand_pressure(role); confidence=float(player_row.get('reliability',.5))
    strategic=fair*infl*(1+.16*scarcity+.10*demand)*(.88+.12*confidence)
    max_bid=int(min(hard_cap,max(1,round(strategic)))) if hard_cap>=1 else 0
    edge=float(player_row.get('edge_confidence_adjusted',player_row.get('edge_vs_market',0)) or 0)
    decision='TARGET' if edge>=8 and max_bid>=fair else 'BUY_AT_VALUE' if max_bid>=fair*.9 else 'ONLY_IF_CHEAP'
    return {'max_bid':max_bid,'decision':decision,'inflation':infl,'hard_cap':hard_cap,'scarcity':scarcity,'demand':demand,'confidence':confidence,
            'league_need_role':league_need,'replacement_points':repl}
