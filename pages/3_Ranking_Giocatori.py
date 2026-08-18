from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fanta_lab.models import LeagueRules
from src.fanta_lab.independent_model import build_independent_valuation

st.set_page_config(page_title='Ranking giocatori · Fanta Auction Lab', page_icon='📊', layout='wide')
st.title('📊 Ranking giocatori')
st.caption('Classifica indipendente, specifica per le regole della tua lega. Mercato/FVM sono mostrati solo come confronto e non entrano nello score indipendente.')

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()

if st.session_state.players.empty:
    st.warning('Costruisci prima il dataset dalla pagina Data Sources.')
    st.stop()

r=st.session_state.rules
ranked=build_independent_valuation(st.session_state.players.copy(),r)

f1,f2,f3,f4=st.columns([1,1,1.2,1.8])
role=f1.selectbox('Ruolo',['Tutti','P','D','C','A'])
min_rel=f2.slider('Affidabilità minima',0.0,1.0,0.0,.05)
sort=f3.selectbox('Ordina per',['independent_score_v1','independent_points','vorp','independent_fair_price','reliability','independent_price_edge_conf_adj'])
query=f4.text_input('Cerca giocatore/squadra')

view=ranked.copy()
if role!='Tutti': view=view[view.role.astype(str).str.upper().eq(role)]
view=view[pd.to_numeric(view.get('reliability',0),errors='coerce').fillna(0)>=min_rel]
if query:
    mask=view.player.astype(str).str.contains(query,case=False,na=False)
    if 'team' in view: mask |= view.team.astype(str).str.contains(query,case=False,na=False)
    view=view[mask]

cols=[c for c in [
    'player','team','role','independent_score_v1','independent_score_floor','independent_score_ceiling',
    'independent_points','projected_points_p10','projected_points_p50','projected_points_p90','vorp',
    'independent_fair_price','reliability','projected_minutes','model_xg90','model_xa90',
    'fvm_1000','market_price_from_fvm','independent_price_edge','independent_price_edge_conf_adj'
] if c in view]

ascending=False
st.dataframe(view.sort_values(sort if sort in view else 'independent_score_v1',ascending=ascending)[cols],use_container_width=True,height=700,hide_index=True)

st.subheader('Top per ruolo')
for rr in ['P','D','C','A']:
    top=ranked[ranked.role.astype(str).str.upper().eq(rr)].sort_values('independent_score_v1',ascending=False).head(10)
    with st.expander(f'Top 10 {rr}',expanded=False):
        st.dataframe(top[[c for c in ['player','team','independent_score_v1','independent_points','vorp','independent_fair_price','reliability'] if c in top]],use_container_width=True,hide_index=True)

st.caption('Lo score cambia automaticamente se cambiano bonus/malus, porta inviolata, modificatore difesa, budget, numero partecipanti o struttura delle rose.')
