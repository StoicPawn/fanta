from __future__ import annotations
import pandas as pd
import streamlit as st
from src.fanta_lab.gaps import player_gap_matrix, gap_summary, source_priority_for_gaps
from src.fanta_lab.ui import apply_theme,page_header,section,common_sidebar,empty_state

st.set_page_config(page_title='Gap Analyzer · Fanta Auction Lab',page_icon='🧩',layout='wide')
apply_theme(); common_sidebar()
page_header('Gap Analyzer','Misura quali informazioni mancano davvero, giocatore per giocatore, e ordina gli interventi per impatto sul modello.','DATA QUALITY')

if 'players' not in st.session_state or not isinstance(st.session_state.players,pd.DataFrame) or st.session_state.players.empty:
    empty_state('Dataset necessario','Costruisci prima il master in Data Sources.')
    st.stop()

df=st.session_state.players; gaps=player_gap_matrix(df); summary=gap_summary(df); priorities=source_priority_for_gaps(gaps)
complete=int((gaps.gap_count==0).sum()); critical=int((gaps.gap_severity>=3).sum())
c=st.columns(5)
c[0].metric('Giocatori',len(df)); c[1].metric('Completi',complete); c[2].metric('Critici',critical); c[3].metric('Gap medi',f'{gaps.gap_count.mean():.2f}'); c[4].metric('Severità media',f'{gaps.gap_severity.mean():.2f}')

coverage, priority, players = st.tabs(['Copertura','Priorità fonti','Giocatori'])
with coverage:
    section('Copertura per layer','Identifica subito i layer che limitano maggiormente l’affidabilità del modello.')
    st.dataframe(summary,use_container_width=True,hide_index=True)
with priority:
    section('Prossime fonti da interrogare','Ordinamento per capacità di chiudere i gap più pesanti senza raccogliere dati ridondanti.')
    st.dataframe(priorities,use_container_width=True,hide_index=True)
    if len(priorities): st.info(f"Prima priorità corrente: **{priorities.iloc[0].get('source',priorities.iloc[0].get('recommended_source','—'))}**")
with players:
    section('Giocatori più scoperti')
    a,b,c=st.columns([1,1.3,2])
    role=a.selectbox('Ruolo',['Tutti','P','D','C','A']); team=b.selectbox('Squadra',['Tutte']+sorted(df.team.dropna().astype(str).unique().tolist()) if 'team' in df else ['Tutte']); search=c.text_input('Cerca giocatore')
    view=gaps.copy()
    if role!='Tutti' and 'role' in view:view=view[view.role==role]
    if team!='Tutte' and 'team' in view:view=view[view.team==team]
    if search:view=view[view.player.astype(str).str.contains(search,case=False,na=False)]
    st.dataframe(view.sort_values(['gap_severity','gap_count'],ascending=False),use_container_width=True,height=640,hide_index=True,column_config={'gap_severity':st.column_config.NumberColumn('Severità',format='%.1f'),'gap_count':st.column_config.NumberColumn('Gap',format='%d')})

st.download_button('Esporta gap report',gaps.to_csv(index=False).encode('utf-8'),file_name='fanta_data_gaps.csv',mime='text/csv',use_container_width=True)
