from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fanta_lab.cache import purge_cache
from src.fanta_lab.source_registry import registry_frame, refresh_plan
from src.fanta_lab.ui import apply_theme,page_header,section,common_sidebar

st.set_page_config(page_title='Source Control · Fanta Auction Lab',page_icon='🔄',layout='wide')
apply_theme(); common_sidebar()
page_header('Source Control','Controlla copertura, priorità, freshness e cache senza sprecare quota API.','DATA OPERATIONS')

registry=registry_frame(); players=st.session_state.get('players')
reg_tab, refresh_tab, cache_tab=st.tabs(['Registry','Refresh plan','Cache'])
with reg_tab:
    section('Registry delle fonti','Ogni fonte ha un layer, priorità, TTL e campi prodotti. Le fonti critiche sono separate dagli enrichment.')
    st.dataframe(registry,use_container_width=True,hide_index=True,column_config={'priority':st.column_config.ProgressColumn('Priorità',min_value=0,max_value=100,format='%d'),'ttl_hours':st.column_config.NumberColumn('TTL h',format='%.1f')})
with refresh_tab:
    if isinstance(players,pd.DataFrame) and not players.empty:
        plan=refresh_plan(players); required=plan[plan.action.eq('required')]; gaps=plan[plan.action.eq('fill-gaps')]
        c=st.columns(4); c[0].metric('Required',len(required)); c[1].metric('Fill gaps',len(gaps)); c[2].metric('Copertura ≥75%',int((plan.coverage_pct>=75).sum())); c[3].metric('Fonti totali',len(plan))
        if len(required): st.error('Ci sono layer critici incompleti: roster/Listone vanno sistemati prima dell’asta.')
        elif len(gaps): st.warning('Struttura utilizzabile, ma alcuni enrichment sono ancora prioritari.')
        else: st.success('Copertura strutturale alta: aggiorna soprattutto in base alla freshness.')
        st.dataframe(plan,use_container_width=True,hide_index=True,column_config={'coverage_pct':st.column_config.ProgressColumn('Copertura %',min_value=0,max_value=100,format='%.0f%%'),'priority':st.column_config.ProgressColumn('Priorità',min_value=0,max_value=100,format='%d')})
    else:
        st.info('Costruisci un master in Data Sources per ottenere un refresh plan basato sulla copertura reale.')
with cache_tab:
    section('Cache locale','Evita chiamate ripetute alle fonti rate-limited e permette stale fallback quando una fonte è temporaneamente indisponibile.')
    st.info('Policy: roster/FVM 6h · ClubElo/calendario 12h · aste/cross-check 24h · storico xG/fantasy 7 giorni.')
    if st.button('Svuota cache locale',type='secondary',use_container_width=True):
        n=purge_cache(); st.success(f'Cache svuotata: {n} file rimossi.')
