from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.independent_model import build_independent_valuation
from src.fanta_lab.auction import AuctionState
from src.fanta_lab.target_engine import build_target_plan, expected_defence_modifier
from src.fanta_lab.plan_health import plan_health, role_spend_corridors

st.set_page_config(page_title='Formazione consigliata · Fanta Auction Lab', page_icon='🧩', layout='wide')
st.title('🧩 Formazione consigliata dinamica')
st.caption('La rosa-obiettivo cambia con regole, budget residuo, acquisti già effettuati e giocatori usciti dal mercato.')

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'manager_names' not in st.session_state: st.session_state.manager_names=['Io']+[f'Avversario {i}' for i in range(1,8)]
if 'my_manager' not in st.session_state: st.session_state.my_manager='Io'

if st.session_state.players.empty:
    st.warning('Costruisci prima il dataset dalla pagina Data Sources.')
    st.stop()

r=st.session_state.rules
pool=build_independent_valuation(st.session_state.players.copy(),r)
pool['fair_price']=pd.to_numeric(pool['independent_fair_price'],errors='coerce').fillna(r.min_bid)

names=st.session_state.manager_names[:r.managers]
state=AuctionState(r,names,st.session_state.my_manager)
for p in st.session_state.purchases:
    try: state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
    except Exception: pass

me=state.my_manager
sold={p.player for p in state.purchases}
locked=[p for p in state.purchases if p.manager==me]
plan=build_target_plan(pool,r,budget=r.budget,locked=locked,sold_players=sold)

if plan.squad.empty:
    st.error('Non esiste al momento una rosa completa fattibile con budget e vincoli correnti.')
    st.stop()

health=plan_health(pool,plan,state,r)
corridors=role_spend_corridors(plan,state,r)

k1,k2,k3,k4,k5=st.columns(5)
k1.metric('Budget residuo',f'{state.remaining(me):.0f}')
k2.metric('Spesa piano',f'{plan.spend:.0f}')
k3.metric('Punti attesi',f'{plan.expected_points:.0f}')
k4.metric('Modificatore',f'+{plan.expected_modifier_points:.1f}' if r.defense_modifier else 'OFF')
k5.metric('Fragilità max',f"{health['risk_score'].max():.0%}" if len(health) else '—')

st.subheader('Rosa target corrente')
show=[c for c in ['player','team','role','independent_score_v1','independent_points','target_price','reliability','vorp'] if c in plan.squad]
st.dataframe(plan.squad[show],use_container_width=True,height=620,hide_index=True)

st.subheader('Budget consigliato per reparto')
st.dataframe(corridors,use_container_width=True,hide_index=True)

st.subheader('Fragilità del piano')
st.caption('Un rischio alto significa che il piano dipende da pochi giocatori senza sostituti quasi equivalenti ancora disponibili.')
st.dataframe(health,use_container_width=True,hide_index=True)

if r.defense_modifier:
    defensive=plan.squad[plan.squad.role.isin(['P','D'])]
    st.info(f'Valore atteso del blocco difensivo per modificatore: **{expected_defence_modifier(defensive,r):.2f}** nel proxy corrente.')

st.download_button('Esporta rosa consigliata CSV',plan.squad.to_csv(index=False).encode(),file_name='formazione_consigliata.csv',mime='text/csv',use_container_width=True)
