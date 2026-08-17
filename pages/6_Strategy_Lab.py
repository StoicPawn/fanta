from __future__ import annotations

import json
from dataclasses import asdict
import pandas as pd
import streamlit as st

from src.fanta_lab.models import AuctionPurchase
from src.fanta_lab.auction import AuctionState, live_recommendation
from src.fanta_lab.strategy import buy_vs_wait, continuation_plan, role_budget_envelopes

st.set_page_config(page_title='Strategy Lab · Fanta Auction Lab',page_icon='🧠',layout='wide')
st.title('Strategy Lab · scenari BUY vs WAIT')
st.caption('Confronta il giocatore chiamato con il miglior piano di continuazione possibile se lo lasci andare.')

required=['rules','manager_names','my_manager','purchases','scored']
missing=[x for x in required if x not in st.session_state]
if missing:
    st.warning('Apri prima la pagina principale, configura la lega e genera Player Intelligence.')
    st.stop()

rules=st.session_state.rules
state=AuctionState(rules,st.session_state.manager_names[:rules.managers],st.session_state.my_manager)
for p in st.session_state.purchases:
    try: state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
    except Exception: pass
pool=st.session_state.scored
sold={p.player for p in state.purchases}
available=pool[~pool.player.isin(sold)].copy()
me=state.my_manager

c1,c2,c3,c4,c5=st.columns(5)
c1.metric('Budget residuo',f'{state.remaining(me):.0f}')
c2.metric('Discrezionale',f'{state.discretionary_budget(me):.0f}')
c3.metric('Slot rimasti',sum(state.slots_left(me).values()))
c4.metric('Inflazione stanza',f'{state.inflation():.2f}×')
c5.metric('Calibrazione forecast',f'{state.forecast_calibration():.2f}×')

st.subheader('1 · BUY vs WAIT sul giocatore chiamato')
risk=st.slider('Aggressività strategica',0.0,1.0,.58,.05)
player=st.selectbox('Giocatore',available.player.tolist())
if player:
    row=available[available.player==player].iloc[0]
    rec=live_recommendation(row,pool,state,risk)
    scenario=buy_vs_wait(row,pool,state,risk)
    a,b,c,d,e=st.columns(5)
    a.metric('Decisione scenario',scenario.get('decision'))
    b.metric('Bid strategico',scenario.get('strategic_bid','—'))
    c.metric('MAX BID tattico',rec.get('max_bid','—'))
    d.metric('Clearing atteso',rec.get('expected_clearing','—'))
    e.metric('Calibrazione',f"{rec.get('calibration',1):.2f}×")
    p10=row.get('projected_points_p10',None); p50=row.get('projected_points_p50',row.get('independent_points',None)); p90=row.get('projected_points_p90',None)
    if p50 is not None:
        x,y,z=st.columns(3); x.metric('P10 punti',f'{float(p10):.1f}' if pd.notna(p10) else '—'); y.metric('P50 punti',f'{float(p50):.1f}'); z.metric('P90 punti',f'{float(p90):.1f}' if pd.notna(p90) else '—')
    if scenario.get('buy_feasible') and scenario.get('wait_feasible'):
        st.write(f"**BUY:** {scenario.get('buy_points')} punti rosa proiettati · **WAIT:** {scenario.get('wait_points')} · differenza {scenario.get('roster_delta')}.")
        l,r=st.columns(2)
        with l:
            st.markdown('#### Piano se COMPRI')
            st.dataframe(pd.DataFrame(scenario.get('buy_plan',[])),use_container_width=True,height=360)
        with r:
            st.markdown('#### Piano se ASPETTI')
            st.dataframe(pd.DataFrame(scenario.get('wait_plan',[])),use_container_width=True,height=360)
    elif scenario.get('decision')=='MUST_BUY':
        st.error('Lasciare questo giocatore rende il completamento ottimale della rosa non fattibile nello scenario corrente.')

st.divider(); st.subheader('2 · Budget envelope per ruolo')
env=role_budget_envelopes(pool,state,risk)
st.dataframe(env,use_container_width=True)
st.caption('Minimum = completamento economico atteso; Balanced = fascia intermedia; Top tier = costo stimato per puntare i migliori nomi ancora disponibili.')

st.divider(); st.subheader('3 · Piano ottimo di continuazione della mia rosa')
plan=continuation_plan(pool,state,risk)
if plan.get('feasible'):
    a,b=st.columns(2); a.metric('Punti proiettati residui',round(plan['points'],1)); b.metric('Spesa attesa',round(plan['cost'],1))
    st.dataframe(pd.DataFrame(plan.get('details',[])),use_container_width=True,height=520)
else:
    st.error(f"Piano non fattibile: {plan.get('reason','unknown')}")

st.divider(); st.subheader('4 · Snapshot portatile dell’asta')
snapshot={'version':6,'rules':rules.to_dict(),'managers':st.session_state.manager_names,'my_manager':st.session_state.my_manager,'purchases':[asdict(p) if isinstance(p,AuctionPurchase) else p for p in st.session_state.purchases],'manager_notes':st.session_state.get('manager_notes',{}),'global_notes':st.session_state.get('global_notes','')}
st.download_button('Scarica snapshot JSON',json.dumps(snapshot,ensure_ascii=False,indent=2),file_name='fanta_auction_snapshot.json',mime='application/json',use_container_width=True)
