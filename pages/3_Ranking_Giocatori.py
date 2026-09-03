from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fanta_lab.models import LeagueRules
from src.fanta_lab.independent_model import build_independent_valuation
from src.fanta_lab.ui import apply_theme, page_header, section, common_sidebar, empty_state

st.set_page_config(page_title='Ranking giocatori · Fanta Auction Lab', page_icon='📊', layout='wide')
apply_theme(); common_sidebar()
page_header('Ranking giocatori','Classifica indipendente costruita sulle regole della tua lega. FVM e mercato sono mostrati a valle solo per evidenziare divergenze e possibili inefficienze.','PLAYER INTELLIGENCE')

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if st.session_state.players.empty:
    empty_state('Dataset necessario','Costruisci prima il master in Data Sources.')
    st.stop()

r=st.session_state.rules
ranked=build_independent_valuation(st.session_state.players.copy(),r)

k=st.columns(7)
predicted=int(ranked.prediction_available.fillna(False).sum())
k[0].metric('Listone ufficiale',len(ranked)); k[1].metric('Con predizione',predicted); k[2].metric('Dati insufficienti',len(ranked)-predicted); k[3].metric('P',int((ranked.role=='P').sum())); k[4].metric('D',int((ranked.role=='D').sum())); k[5].metric('C',int((ranked.role=='C').sum())); k[6].metric('A',int((ranked.role=='A').sum()))

list_tab, detail_tab, top_tab = st.tabs(['Classifica completa','Scheda giocatore','Top per ruolo'])
with list_tab:
    f1,f2,f3,f4,f5=st.columns([1,1,1.25,1.25,2])
    role=f1.selectbox('Ruolo',['Tutti','P','D','C','A'])
    min_rel=f2.slider('Affidabilità minima',0.0,1.0,0.0,.05)
    sort=f3.selectbox('Ordina per',['independent_score_v1','independent_points','vorp','independent_fair_price','reliability','independent_price_edge_conf_adj'])
    availability=f4.selectbox('Predizione',['Tutti','Disponibile','Non disponibile'])
    query=f5.text_input('Cerca giocatore o squadra',placeholder='es. Inter, Lautaro…')
    view=ranked.copy()
    if role!='Tutti': view=view[view.role.astype(str).str.upper().eq(role)]
    if availability=='Disponibile': view=view[view.prediction_available.fillna(False)]
    elif availability=='Non disponibile': view=view[~view.prediction_available.fillna(False)]
    view=view[pd.to_numeric(view.get('reliability',0),errors='coerce').fillna(0)>=min_rel]
    if query:
        mask=view.player.astype(str).str.contains(query,case=False,na=False)
        if 'team' in view: mask|=view.team.astype(str).str.contains(query,case=False,na=False)
        view=view[mask]
    cols=[c for c in ['player','team','role','prediction_status','prediction_reason','canonical_value','canonical_value_source','quotation','fvm_1000','independent_score_v1','independent_score_floor','independent_score_ceiling','independent_points','projected_points_p10','projected_points_p50','projected_points_p90','vorp','independent_fair_price','reliability','projected_minutes','model_xg90','model_xa90','independent_price_edge','independent_price_edge_conf_adj'] if c in view]
    st.dataframe(view.sort_values(sort if sort in view else 'independent_score_v1',ascending=False)[cols],use_container_width=True,height=690,hide_index=True,column_config={
        'player':'Giocatore','team':'Squadra','role':'R','independent_score_v1':st.column_config.NumberColumn('Score',format='%.1f'),
        'independent_score_floor':st.column_config.NumberColumn('Floor',format='%.1f'),'independent_score_ceiling':st.column_config.NumberColumn('Ceiling',format='%.1f'),
        'canonical_value':st.column_config.NumberColumn('Valore canonico',format='%.1f'),'canonical_value_source':'Fonte valore canonico',
        'quotation':st.column_config.NumberColumn('Quotazione ufficiale',format='%.0f'),'fvm_1000':st.column_config.NumberColumn('FVM 1000',format='%.0f'),
        'independent_points':st.column_config.NumberColumn('Punti',format='%.1f'),'vorp':st.column_config.NumberColumn('VORP',format='%.1f'),
        'independent_fair_price':st.column_config.NumberColumn('Fair',format='%.0f'),'reliability':st.column_config.ProgressColumn('Affidabilità',min_value=0,max_value=1,format='%.0%%'),
        'independent_price_edge_conf_adj':st.column_config.NumberColumn('Edge adj.',format='%+.1f')})

with detail_tab:
    section('Scheda giocatore','Separa produzione attesa, rischio, valore economico e confronto con il mercato.')
    chosen=st.selectbox('Giocatore',ranked.sort_values('independent_score_v1',ascending=False).player.tolist(),key='ranking_detail_player')
    row=ranked[ranked.player==chosen].iloc[0]
    has_prediction=bool(row.get('prediction_available',False))
    canonical=row.get('canonical_value')
    canonical_text=f"{float(canonical):.1f} {row.get('canonical_value_unit','')}" if pd.notna(canonical) else 'non disponibile nel Listone'
    if not has_prediction:
        st.warning(f"**Il modello non può fare una valutazione indipendente per {chosen}.** {row.get('prediction_reason','Dati insufficienti')}. Come riferimento resta disponibile la valutazione canonica: **{canonical_text}**.")
    a=st.columns(7)
    def metric_value(key,fmt):
        value=row.get(key)
        return format(float(value),fmt) if has_prediction and pd.notna(value) else '—'
    a[0].metric('Score',metric_value('independent_score_v1','.1f'))
    a[1].metric('Punti attesi',metric_value('independent_points','.1f'))
    a[2].metric('VORP',metric_value('vorp','.1f'))
    a[3].metric('Fair price',metric_value('independent_fair_price','.0f'))
    a[4].metric('Valore canonico',f"{float(canonical):.1f}" if pd.notna(canonical) else '—',help=row.get('canonical_value_source'))
    a[5].metric('Affidabilità',metric_value('reliability','.0%'))
    a[6].metric('Minuti',metric_value('projected_minutes','.0f'))
    c1,c2=st.columns(2)
    with c1:
        section('Distribuzione prevista')
        dist=pd.DataFrame({'Scenario':['P10','P50','P90'],'Punti':[row.get('projected_points_p10'),row.get('projected_points_p50'),row.get('projected_points_p90')]})
        st.dataframe(dist,use_container_width=True,hide_index=True)
        if has_prediction: st.caption(f"xG/90 modellato: {row.get('model_xg90',0):.2f} · xA/90: {row.get('model_xa90',0):.2f}")
        else: st.caption('Distribuzione non calcolata: dati individuali insufficienti.')
    with c2:
        section('Mercato vs modello')
        comp=pd.DataFrame({'Voce':['Fair indipendente','Valore canonico Listone','Quotazione ufficiale','FVM su 1000','Edge','Edge corretto per confidenza'],'Valore':[row.get('independent_fair_price'),row.get('canonical_value'),row.get('quotation'),row.get('fvm_1000'),row.get('independent_price_edge'),row.get('independent_price_edge_conf_adj')]})
        st.dataframe(comp,use_container_width=True,hide_index=True)
        st.caption(f"{row.get('canonical_value_source','Valore canonico non disponibile')}. Il mercato non entra nella costruzione dello score: serve soltanto per il confronto finale o come riferimento quando il modello non può stimare.")

with top_tab:
    section('Top 10 per ruolo')
    cols=st.columns(4)
    for col,rr in zip(cols,['P','D','C','A']):
        top=ranked[ranked.role.astype(str).str.upper().eq(rr)&ranked.prediction_available.fillna(False)].sort_values('independent_score_v1',ascending=False).head(10)
        with col:
            st.markdown(f'**{rr}**')
            for i,(_,x) in enumerate(top.iterrows(),1):
                st.caption(f"{i}. {x.player} · {x.independent_score_v1:.0f} · fair {x.independent_fair_price:.0f}")

st.caption('Cambiare bonus/malus, porta inviolata, modificatore difesa, budget, partecipanti o slot genera una classifica diversa.')
