from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fanta_lab.cache import purge_cache
from src.fanta_lab.source_registry import registry_frame, refresh_plan

st.set_page_config(page_title='Source Control · Fanta Auction Lab',page_icon='🔄',layout='wide')
st.title('Source Control · freshness, cache e refresh intelligente')
st.caption('Centralizza le policy delle fonti: priorità, TTL, copertura e azione consigliata. Il refresh manuale non salva mai le API key nel repository.')

st.subheader('Registry fonti')
st.dataframe(registry_frame(),use_container_width=True,hide_index=True)

players=st.session_state.get('players')
if isinstance(players,pd.DataFrame) and not players.empty:
    st.subheader('Refresh plan sul master corrente')
    plan=refresh_plan(players)
    st.dataframe(plan,use_container_width=True,hide_index=True)
    required=plan[plan.action.eq('required')]
    gaps=plan[plan.action.eq('fill-gaps')]
    a,b,c=st.columns(3)
    a.metric('Fonti/layer obbligatori incompleti',len(required))
    b.metric('Layer da colmare',len(gaps))
    c.metric('Layer già ad alta copertura',int((plan.coverage_pct>=75).sum()))
    if len(required): st.error('Ci sono layer critici non sufficientemente coperti: controlla roster/Listone prima dell’asta.')
    elif len(gaps): st.warning('Il roster è utilizzabile, ma il piano identifica enrichment prioritari da completare.')
    else: st.success('Copertura strutturale alta: i refresh possono seguire soprattutto la freshness.')
else:
    st.info('Costruisci prima un master dalla pagina Data Sources per ottenere un refresh plan basato sulla copertura reale.')

st.divider()
st.subheader('Cache locale')
st.write('Le risposte costose/rate-limited possono essere riutilizzate finché il TTL della fonte non scade. Se una fonte temporaneamente fallisce, il motore può continuare con l’ultima copia cache marcandola come stale.')
if st.button('SVUOTA CACHE LOCALE',type='secondary'):
    n=purge_cache()
    st.success(f'Cache svuotata: {n} file rimossi.')

st.info('Policy attuale: roster/FVM 6h, ClubElo e calendario 12h, aste/fantasy cross-check 24h, storico xG/fantasy 7 giorni. Questi TTL sono centralizzati nel registry e possono essere modificati senza cambiare la logica del motore.')
