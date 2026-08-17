from __future__ import annotations
from collections import defaultdict
import hashlib
import math
import numpy as np
import pandas as pd
from .models import LeagueRules, AuctionPurchase

class AuctionState:
    def __init__(self,rules:LeagueRules,manager_names:list[str],my_manager:str):
        self.rules=rules; self.manager_names=manager_names; self.my_manager=my_manager; self.purchases:list[AuctionPurchase]=[]
    def add_purchase(self,purchase:AuctionPurchase): self.purchases.append(purchase)
    def spent(self,m): return sum(float(p.price) for p in self.purchases if p.manager==m)
    def remaining(self,m): return max(0.0,self.rules.budget-self.spent(m))
    def roster(self,m): return [p for p in self.purchases if p.manager==m]
    def slots_left(self,m):
        used=defaultdict(int)
        for p in self.roster(m): used[p.role]+=1
        return {r:max(0,n-used[r]) for r,n in self.rules.slots().items()}
    def min_reserve(self,m): return float(sum(self.slots_left(m).values()))
    def discretionary_budget(self,m): return max(0.0,self.remaining(m)-self.min_reserve(m))
    def inflation(self,role:str|None=None):
        ps=[p for p in self.purchases if p.fair_value_before and p.fair_value_before>0 and (role is None or p.role==role)]
        ratios=[float(p.price)/float(p.fair_value_before) for p in ps]
        if len(ratios)<3 and role is not None: return self.inflation(None)
        if len(ratios)<3:return 1.0
        # recent sales matter more, but median prevents one irrational purchase from dominating
        recent=ratios[-20:]
        med=float(np.median(recent)); q=float(np.quantile(recent,.65)) if len(recent)>=5 else med
        return float(np.clip(.7*med+.3*q,.65,2.20))
    def market_inflation(self,role:str|None=None):
        ps=[p for p in self.purchases if p.market_value_before and p.market_value_before>0 and (role is None or p.role==role)]
        ratios=[float(p.price)/float(p.market_value_before) for p in ps]
        if len(ratios)<3 and role is not None:return self.market_inflation(None)
        return float(np.clip(np.median(ratios[-20:]),.65,2.2)) if len(ratios)>=3 else 1.0
    def manager_aggression(self,m,role:str|None=None):
        ps=[p for p in self.purchases if p.manager==m and p.fair_value_before and p.fair_value_before>0 and (role is None or p.role==role)]
        if len(ps)<2:return 1.0
        return float(np.clip(np.median([p.price/p.fair_value_before for p in ps]),.60,2.20))
    def manager_role_need(self,m,role): return self.slots_left(m).get(role,0)
    def competing_managers(self,role,min_discretionary:float=1.0):
        return [m for m in self.manager_names if m!=self.my_manager and self.manager_role_need(m,role)>0 and self.discretionary_budget(m)>=min_discretionary]
    def room_liquidity(self):
        discretionary=sum(self.discretionary_budget(m) for m in self.manager_names)
        slots=sum(sum(self.slots_left(m).values()) for m in self.manager_names)
        return discretionary/max(1,slots)
    def demand_pressure(self,role:str):
        vals=[]
        for m in self.manager_names:
            if m==self.my_manager: continue
            need=self.slots_left(m).get(role,0); total=max(1,sum(self.slots_left(m).values()))
            budget_share=self.discretionary_budget(m)/max(1,self.rules.budget)
            vals.append((need/total)*budget_share*self.manager_aggression(m,role))
        return float(np.clip(np.mean(vals)*5 if vals else 0,0,2.0))


def allocate_fair_prices(df:pd.DataFrame,rules:LeagueRules,reserve_per_slot:float=1.0)->pd.DataFrame:
    out=df.copy(); slots_total=sum(rules.slots().values())*rules.managers; money=max(0,rules.budget*rules.managers-slots_total*reserve_per_slot)
    out['surplus']=0.0
    for role,slots in rules.slots().items():
        g=out[out.role==role].sort_values('independent_points',ascending=False); n=slots*rules.managers
        replacement=float(g.iloc[min(len(g)-1,n-1)]['independent_points']) if len(g) else 0
        out.loc[g.index,'surplus']=(g.independent_points-replacement).clip(lower=0)
    conf=pd.to_numeric(out.get('reliability',pd.Series(1,index=out.index)),errors='coerce').fillna(.5).clip(.25,1)
    out['auction_surplus']=out.surplus*(.70+.30*conf)
    s=out.auction_surplus.sum(); out['fair_price']=reserve_per_slot+(out.auction_surplus/s*money if s>0 else 0)
    return out


def _top_supply(pool:pd.DataFrame,state:AuctionState,role:str,player_points:float)->dict:
    sold={p.player for p in state.purchases}
    avail=pool[(pool.role==role)&(~pool.player.isin(sold))].copy()
    if avail.empty:return {'better_or_equal':0,'league_need':0,'scarcity':1.0,'replacement':0.0,'tier_pressure':2.0}
    avail=avail.sort_values('independent_points',ascending=False)
    league_need=sum(state.slots_left(m).get(role,0) for m in state.manager_names)
    ridx=min(len(avail)-1,max(0,league_need-1))
    repl=float(avail.iloc[ridx].independent_points)
    better=int((pd.to_numeric(avail.independent_points,errors='coerce')>=player_points*.94).sum())
    competitors=len(state.competing_managers(role)) + (1 if state.slots_left(state.my_manager).get(role,0)>0 else 0)
    tier_pressure=float(np.clip((competitors+1)/max(1,better),.5,3.0))
    scarcity=max(0,(player_points-repl)/max(abs(player_points),1))
    return {'better_or_equal':better,'league_need':league_need,'scarcity':scarcity,'replacement':repl,'tier_pressure':tier_pressure}


def simulated_clearing_price(player_row:pd.Series,pool:pd.DataFrame,state:AuctionState,n:int=1200)->dict:
    """Synthetic skilled-human market: each rival gets a noisy reservation value.

    It is calibrated by observed room inflation, optional public real-auction averages,
    individual aggressiveness, remaining budget, role need and top-tier scarcity.
    """
    role=str(player_row.role); fair=max(1.0,float(player_row.get('fair_price',1) or 1))
    market_raw=player_row.get('market_auction_price',np.nan)
    market=float(market_raw) if pd.notna(market_raw) and float(market_raw)>0 else fair
    pts=float(player_row.get('independent_points',0) or 0)
    supply=_top_supply(pool,state,role,pts)
    observed=.60*state.inflation(role)+.40*state.market_inflation(role)
    anchor=(.58*fair+.42*market)*observed
    demand=state.demand_pressure(role)
    tier=supply['tier_pressure']
    urgency=1+.10*demand+.09*max(0,tier-1)
    anchor*=urgency
    seed=int(hashlib.sha256(str(player_row.get('player','x')).encode()).hexdigest()[:8],16)+len(state.purchases)
    rng=np.random.default_rng(seed)
    clears=[]
    rivals=state.competing_managers(role)
    for _ in range(n):
        bids=[]
        for m in rivals:
            hard=max(0,state.remaining(m)-max(0,sum(state.slots_left(m).values())-1))
            if hard<1: continue
            aggr=state.manager_aggression(m,role)
            # heterogeneous humans: lognormal around rational reservation value
            shock=float(rng.lognormal(mean=-.5*.16**2,sigma=.16))
            reservation=anchor*aggr*shock
            bids.append(min(hard,reservation))
        if bids:
            bids.sort(reverse=True)
            clears.append(min(max(1,bids[0]+1),max(bids)))
        else: clears.append(1.0)
    a=np.asarray(clears,dtype=float)
    return {'p50':float(np.quantile(a,.50)),'p65':float(np.quantile(a,.65)),'p80':float(np.quantile(a,.80)),
            'anchor':anchor,'demand':demand,'tier_pressure':tier,'better_or_equal':supply['better_or_equal'],
            'replacement_points':supply['replacement'],'league_need_role':supply['league_need']}


def live_recommendation(player_row:pd.Series,pool:pd.DataFrame,state:AuctionState,risk_tolerance:float=.58)->dict:
    role=str(player_row.role); fair=max(1.0,float(player_row.get('fair_price',1) or 1)); left=state.slots_left(state.my_manager)
    my_budget=state.remaining(state.my_manager); total_left=sum(left.values()); mandatory=max(0,total_left-1); hard_cap=max(0,my_budget-mandatory)
    if left.get(role,0)<=0:return {'max_bid':0,'decision':'SKIP_ROLE_FULL','inflation':state.inflation(role),'hard_cap':hard_cap,'scarcity':0,'demand':0,'expected_clearing':0,'urgency':0}
    sim=simulated_clearing_price(player_row,pool,state)
    pts=float(player_row.get('independent_points',0) or 0); supply=_top_supply(pool,state,role,pts)
    confidence=float(player_row.get('reliability',.5) or .5)
    edge=float(player_row.get('edge_confidence_adjusted',player_row.get('edge_vs_market',0)) or 0)
    market=player_row.get('market_auction_price',np.nan); market=float(market) if pd.notna(market) else fair
    # opportunity cost of waiting: when comparable top supply is thinner than solvent demand, pay a survival premium
    solvent=len(state.competing_managers(role)); shortage=max(0,solvent+1-supply['better_or_equal'])/max(1,solvent+1)
    my_role_need=left.get(role,0); role_budget_share=state.discretionary_budget(state.my_manager)/max(1,sum(left.values()))
    urgency=float(np.clip(.35*supply['scarcity']+.35*shortage+.20*sim['demand']+.10*(my_role_need/max(1,left.get(role,1))),0,1.75))
    clearing_target=(1-risk_tolerance)*sim['p50']+risk_tolerance*sim['p80']
    model_ceiling=max(fair, .72*fair+.28*market) * (1+.15*urgency) * (.90+.10*confidence)
    # Never lose all elite supply merely because the static fair value was one credit lower.
    strategic=max(fair, min(clearing_target,model_ceiling if shortage<.5 else model_ceiling*(1+.12*shortage)))
    # if there is lots of discretionary budget per remaining slot, prices naturally clear higher
    liquidity_factor=float(np.clip(state.room_liquidity()/max(1,role_budget_share),.85,1.18))
    strategic*=liquidity_factor
    max_bid=int(min(hard_cap,max(1,math.ceil(strategic)))) if hard_cap>=1 else 0
    value_gap=max_bid-sim['p50']
    if max_bid<=0: decision='NO_BUDGET'
    elif shortage>.45 and max_bid>=sim['p65']: decision='PUSH_IF_NEEDED'
    elif edge>=8 and max_bid>=sim['p50']: decision='TARGET'
    elif max_bid>=sim['p50']: decision='BUY_AT_MARKET'
    else: decision='DISCIPLINE_SKIP'
    return {'max_bid':max_bid,'decision':decision,'inflation':state.inflation(role),'hard_cap':hard_cap,'scarcity':supply['scarcity'],
            'demand':sim['demand'],'confidence':confidence,'league_need_role':supply['league_need'],'replacement_points':supply['replacement'],
            'expected_clearing':round(sim['p50'],1),'clearing_p80':round(sim['p80'],1),'tier_pressure':sim['tier_pressure'],
            'better_or_equal_left':sim['better_or_equal'],'urgency':urgency,'value_gap':round(value_gap,1),'shortage_risk':shortage}
