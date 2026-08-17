from __future__ import annotations
import pandas as pd
import streamlit as st
from src.fanta_lab.gaps import player_gap_matrix, gap_summary, source_priority_for_gaps

st.set_page_config(page_title='Gap Analyzer · Fanta Auction Lab',page_icon='🧩',layout='wide')
st.title('Gap Analyzer · cosa manca davvero')
st.caption('Analizza il master giocatore per giocatore e ordina i buchi dati per impatto. Serve a decidere quale fonte aggiungere prima, evitando raccolta ridondante.')

if 'players' not in st.session_state or not isinstance(st.session_state.players,pd.DataFrame) or st.session_state.players.empty:
    st.warning('Costruisci prima il dataset dalla pagina Data Sources.')
    st.stop()

df=st.session_state.players
gaps=player_gap_matrix(df); summary=gap_summary(df); priorities=source_priority_for_gaps(gaps)

c1,c2,c3,c4=st.columns(4)
c1.metric('Giocatori',len(df))
c2.metric('Gap medi',round(float(gaps.gap_count.mean()),2))
c3.metric('Gap severità media',round(float(gaps.gap_severity.mean()),2))
c4.metric('Giocatori completi',int((gaps.gap_count==0).sum()))

st.subheader('Copertura per layer')
st.dataframe(summary,use_container_width=True,hide_index=True)

st.subheader('Priorità di raccolta')
st.dataframe(priorities,use_container_width=True,hide_index=True)

st.subheader('Giocatori più scoperti')
a,b,c=st.columns(3)
role=a.selectbox('Ruolo',['Tutti','P','D','C','A'])
team=b.selectbox('Squadra',['Tutte']+sorted(df.team.dropna().astype(str).unique().tolist()) if 'team' in df else ['Tutte'])
search=c.text_input('Cerca')
view=gaps.copy()
if role!='Tutti' and 'role' in view:view=view[view.role==role]
if team!='Tutte' and 'team' in view:view=view[view.team==team]
if search:view=view[view.player.astype(str).str.contains(search,case=False,na=False)]
st.dataframe(view,use_container_width=True,height=650)

st.download_button('Scarica gap report CSV',gaps.to_csv(index=False).encode('utf-8'),file_name='fanta_data_gaps.csv',mime='text/csv',use_container_width=True)
