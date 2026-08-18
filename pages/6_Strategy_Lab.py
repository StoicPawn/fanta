from __future__ import annotations

import json
from dataclasses import asdict
import pandas as pd
import streamlit as st

from src.fanta_lab.models import AuctionPurchase
from src.fanta_lab.auction import AuctionState, live_recommendation
from src.fanta_lab.strategy import buy_vs_wait, continuation_plan, role_budget_envelopes
from src.fanta_lab.ui import apply_theme,page_header,section,common_sidebar,empty_state

st.set_page_config(page_title='Strategy Lab · Fanta Auction Lab',page_icon='🧠',layout='wide')
apply_theme(); common_sidebar()
page_header('Strategy Lab','Confronta BUY vs WAIT e misura il costo-opportunità di lasciare andare un giocatore sulla rosa finale, non sul singolo prezzo.','SCENARIO ENGINE')

required=['rules','manager_names','my_manager','purchases']
missing=[x for x in required if x not in st.session_state]
if missing:
    empty_state('Sessione asta non inizializzata','Apri prima il Command Center e configura lega e partecipanti.')
    st.stop()

rules=st.session_state.rules
pool=st.session_state.get('scored')
if pool is None or not isinstance(pool,pd.DataFrame) or pool.empty:
    from src.fanta_lab.independent_model import build_independent_valuation
    players=st.session_state.get('players')
    if players is None or players.empty:
        empty_state('Dataset necessario','Costruisci prima il master in Data Sources.')
        st.stop()
    pool=build_independent_valuation(players.copy(),rules)
    pool['fair_price']=pd.to_numeric(pool.independent_fair_price,errors='coerce').fillna(rules.min_bid)

state=AuctionState(rules,st.session_state.manager_names[:rules.managers],st.session_state.my_manager)
for p in st.session_state.purchases:
    try: state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
    except Exception: pass
sold={p.player for p in state.purchases}; available=pool[~pool.player.isin(sold)].copy(); me=state.my_manager

c=st.columns(5)
c[0].metric('Budget residuo',f'{state.remaining(me):.0f}'); c[1].metric('Discrezionale',f'{state.discretionary_budget(me):.0f}'); c[2].metric('Slot',sum(state.slots_left(me).values())); c[3].metric('Inflazione',f'{state.inflation():.2f}×'); c[4].metric('Calibrazione',f'{state.forecast_calibration():.2f}×')

scenario_tab, budget_tab, continuation_tab, export_tab=st.tabs(['BUY vs WAIT','Budget per ruolo','Piano di continuazione','Snapshot'])
with scenario_tab:
    section('Decisione sul giocatore chiamato','Il modello confronta la miglior rosa raggiungibile comprando ora con la miglior rosa raggiungibile aspettando.')
    a,b=st.columns([3,1]); risk=b.slider('Aggressività strategica',0.0,1.0,.58,.05); player=a.selectbox('Giocatore',available.sort_values('independent_score_v1' if 'independent_score_v1' in available else 'independent_points',ascending=False).player.tolist())
    if player:
        row=available[available.player==player].iloc[0]; rec=live_recommendation(row,pool,state,risk); scenario=buy_vs_wait(row,pool,state,risk)
        k=st.columns(6)
        k[0].metric('Decisione',scenario.get('decision')); k[1].metric('Bid strategico',scenario.get('strategic_bid','—')); k[2].metric('MAX BID',rec.get('max_bid','—')); k[3].metric('Clearing',rec.get('expected_clearing','—')); k[4].metric('P10',f"{row.get('projected_points_p10',0):.0f}"); k[5].metric('P90',f"{row.get('projected_points_p90',0):.0f}")
        if scenario.get('buy_feasible') and scenario.get('wait_feasible'):
            delta=float(scenario.get('roster_delta',0) or 0)
            (st.success if delta>0 else st.info)(f"BUY: **{scenario.get('buy_points')}** punti rosa · WAIT: **{scenario.get('wait_points')}** · delta **{delta:+.1f}**")
            l,r=st.columns(2)
            with l:
                section('Se compri'); st.dataframe(pd.DataFrame(scenario.get('buy_plan',[])),use_container_width=True,height=360,hide_index=True)
            with r:
                section('Se aspetti'); st.dataframe(pd.DataFrame(scenario.get('wait_plan',[])),use_container_width=True,height=360,hide_index=True)
        elif scenario.get('decision')=='MUST_BUY': st.error('Aspettare rende non fattibile la continuazione ottimale nello scenario corrente.')

with budget_tab:
    section('Budget envelope per ruolo','Minimum = completamento economico; Balanced = fascia centrale; Top tier = costo per puntare i migliori ancora disponibili.')
    env=role_budget_envelopes(pool,state,.58); st.dataframe(env,use_container_width=True,hide_index=True)

with continuation_tab:
    section('Miglior prosecuzione possibile','Questa è la rosa residua che il motore cercherebbe di costruire dato lo stato corrente della stanza.')
    plan=continuation_plan(pool,state,.58)
    if plan.get('feasible'):
        a,b=st.columns(2); a.metric('Punti residui',round(plan['points'],1)); b.metric('Spesa attesa',round(plan['cost'],1)); st.dataframe(pd.DataFrame(plan.get('details',[])),use_container_width=True,height=540,hide_index=True)
    else: st.error(f"Piano non fattibile: {plan.get('reason','unknown')}")

with export_tab:
    section('Snapshot portatile','Salva lo stato asta e riaprilo senza perdere acquisti, regole o note.')
    snapshot={'version':7,'rules':rules.to_dict(),'managers':st.session_state.manager_names,'my_manager':st.session_state.my_manager,'purchases':[asdict(p) if isinstance(p,AuctionPurchase) else p for p in st.session_state.purchases],'manager_notes':st.session_state.get('manager_notes',{}),'global_notes':st.session_state.get('global_notes','')}
    st.download_button('Scarica snapshot JSON',json.dumps(snapshot,ensure_ascii=False,indent=2),file_name='fanta_auction_snapshot.json',mime='application/json',use_container_width=True)
