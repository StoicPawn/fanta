from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).parent; sys.path.insert(0,str(ROOT))
from src.fanta_lab.models import LeagueRules,AuctionPurchase
from src.fanta_lab.projection import add_projections,add_market_comparison
from src.fanta_lab.auction import AuctionState,allocate_fair_prices,live_recommendation
from src.fanta_lab.pipeline import build_dataset
from src.fanta_lab.sources.fantacalcio import load_user_list

st.set_page_config(page_title='Fanta Auction Lab',page_icon='⚽',layout='wide')
st.title('Fanta Auction Lab · V3')
st.caption('Roster certificato → mercato Fantacalcio → modello indipendente → scoring della tua lega → Auction Copilot')
if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'coverage' not in st.session_state: st.session_state.coverage=None

setup,data_tab,rankings,auction=st.tabs(['1 · Regole lega','2 · Dati & copertura','3 · Valutazioni','4 · Asta live'])
with setup:
    r=st.session_state.rules
    a,b,c,d=st.columns(4); r.budget=a.number_input('Budget',50,5000,r.budget); r.managers=b.number_input('Partecipanti',2,20,r.managers); r.slots_gk=c.number_input('Portieri',1,5,r.slots_gk); r.slots_def=d.number_input('Difensori',1,15,r.slots_def)
    a,b,c,d=st.columns(4); r.slots_mid=a.number_input('Centrocampisti',1,15,r.slots_mid); r.slots_fwd=b.number_input('Attaccanti',1,10,r.slots_fwd); r.assist=c.number_input('Bonus assist',-5.,10.,r.assist,.5); r.clean_sheet_gk=d.number_input('Porta inviolata P',-5.,10.,r.clean_sheet_gk,.5)
    a,b,c,d=st.columns(4); r.goal_gk=a.number_input('Gol P',-5.,15.,r.goal_gk,.5); r.goal_def=b.number_input('Gol D',-5.,15.,r.goal_def,.5); r.goal_mid=c.number_input('Gol C',-5.,15.,r.goal_mid,.5); r.goal_fwd=d.number_input('Gol A',-5.,15.,r.goal_fwd,.5)
    a,b,c,d=st.columns(4); r.yellow=a.number_input('Ammonizione',-5.,2.,r.yellow,.5); r.red=b.number_input('Espulsione',-10.,2.,r.red,.5); r.clean_sheet_def=c.number_input('Porta inviolata D',-5.,10.,r.clean_sheet_def,.5); r.defense_modifier=d.toggle('Modificatore difesa',r.defense_modifier)
    if r.defense_modifier:r.defense_modifier_strength=st.slider('Peso marginale modificatore',0.,2.,float(r.defense_modifier_strength),.1)
    st.info('Il ranking viene ricostruito dalle regole della tua lega. Il modificatore è stimato marginalmente sul singolo giocatore; una versione futura ottimizzerà direttamente l’intera combinazione difensiva.')

with data_tab:
    st.subheader('Pipeline dati 2026/27')
    st.write('Il master è una **unione lossless**: football-data.org è il backbone delle rose; il Listone Fantacalcio corrente certifica l’eleggibilità fantasy. Un nuovo acquisto presente nel Listone ma non ancora nella fonte roster viene comunque aggiunto e marcato da riconciliare.')
    with st.expander('Esegui pipeline automatica',expanded=False):
        token=st.text_input('football-data.org API token (gratuito)',type='password')
        season=st.number_input('Anno iniziale stagione',2020,2030,2026)
        label=st.text_input('Etichetta stagione da verificare sulla pagina Fantacalcio','2026/27')
        list_file=st.file_uploader('Opzionale: Listone CSV/XLSX corrente (fallback più robusto)',type=['csv','xlsx','xls'],key='listone')
        if st.button('Costruisci e certifica dataset',type='primary'):
            try:
                fdf=load_user_list(list_file) if list_file else None
                master,report=build_dataset(int(season),label,token or None,fantasy_df=fdf,require_current_fanta=True)
                st.session_state.players=master; st.session_state.coverage=report
                st.success(f'Dataset costruito: {len(master)} righe · stato {report.certification}')
            except Exception as e: st.error(str(e))
    up=st.file_uploader('Oppure carica CSV master già costruito',type=['csv'],key='master')
    if up: st.session_state.players=pd.read_csv(up)
    if st.session_state.players.empty:
        sample=ROOT/'data'/'sample_players.csv'
        if sample.exists():
            df=pd.read_csv(sample).rename(columns={'name':'player','position':'role','fvm':'fvm_1000'}); st.session_state.players=df
    df=st.session_state.players
    if not df.empty:
        teams=df.team.nunique() if 'team' in df else 0; fvm=int(df.get('fvm_1000',pd.Series(dtype=float)).notna().sum()); hist=int(pd.to_numeric(df.get('minutes',pd.Series(dtype=float)),errors='coerce').fillna(0).gt(0).sum())
        a,b,c,d=st.columns(4); a.metric('Giocatori master',len(df)); b.metric('Squadre backbone',teams); c.metric('Con FVM',fvm); d.metric('Con storico Serie A',hist)
        report=st.session_state.coverage
        if report:
            (st.success if report.certified else st.warning)(f'Coverage gate: {report.certification} · Listone {report.fantasy_players} · matched {report.matched_fantasy} · listone-only {len(report.unmatched_fantasy)}')
            for n in report.notes: st.caption('• '+n)
        elif teams!=20: st.error('Dataset non certificato: il numero squadre non è 20.')
        cols=[c for c in ['player','team','role','fantasy_eligible','quotation','fvm_1000','has_history','data_confidence','source'] if c in df]
        st.dataframe(df[cols].head(150) if cols else df.head(150),use_container_width=True)

with rankings:
    if st.session_state.players.empty: st.warning('Carica prima i dati.')
    else:
        df=st.session_state.players.copy()
        for c,v in {'role':'C','minutes':0,'goals':0,'assists':0,'xg':0,'xa':0,'yellow_cards':0,'red_cards':0}.items():
            if c not in df: df[c]=v
        scored=allocate_fair_prices(add_market_comparison(add_projections(df,st.session_state.rules)),st.session_state.rules); st.session_state.scored=scored
        a,b,c=st.columns(3); role=a.selectbox('Ruolo',['Tutti','P','D','C','A']); sort=b.selectbox('Ordina per',['independent_score','edge_confidence_adjusted','edge_vs_market','fair_price','fvm_1000','reliability']); search=c.text_input('Cerca')
        view=scored.copy(); view=view if role=='Tutti' else view[view.role==role]
        if search:view=view[view.player.str.contains(search,case=False,na=False)]
        cols=[c for c in ['player','team','role','quotation','fvm_1000','market_score','independent_score','edge_vs_market','edge_confidence_adjusted','fair_price','projected_minutes','minutes_source','pred_goal90','pred_assist90','reliability'] if c in view]
        st.dataframe(view.sort_values(sort if sort in view else 'independent_score',ascending=False)[cols],use_container_width=True,height=620)
        st.caption('Edge grezzo = differenza dal mercato. Edge confidence-adjusted = stessa divergenza scontata per qualità dati e affidabilità del minutaggio: è più prudente con nuovi arrivi e piccoli campioni.')

with auction:
    if 'scored' not in st.session_state: st.warning('Apri prima Valutazioni.')
    else:
        pool=st.session_state.scored; defaults=['Io']+[f'Avversario {i}' for i in range(1,st.session_state.rules.managers)]
        managers=[x.strip() for x in st.text_input('Manager separati da virgola',', '.join(defaults)).split(',') if x.strip()]; me=st.selectbox('La mia squadra',managers)
        state=AuctionState(st.session_state.rules,managers,me)
        for p in st.session_state.purchases: state.add_purchase(p)
        a,b,c,d=st.columns(4); a.metric('Mio budget residuo',f'{state.remaining(me):.0f}'); b.metric('Inflazione globale',f'{state.inflation():.2f}×'); c.metric('Vendite',len(state.purchases)); d.metric('Slot miei rimasti',sum(state.slots_left(me).values()))
        available=pool[~pool.player.isin([p.player for p in state.purchases])]
        player=st.selectbox('Giocatore chiamato',available.player.tolist()) if len(available) else None
        if player:
            row=available[available.player==player].iloc[0]; rec=live_recommendation(row,pool,state)
            a,b,c,d,e=st.columns(5); a.metric('MAX BID',rec['max_bid']); b.metric('Fair pre-asta',f"{row.get('fair_price',0):.1f}"); c.metric('Inflazione ruolo',f"{rec['inflation']:.2f}×"); d.metric('Pressione domanda',f"{rec['demand']:.0%}"); e.metric('Decisione',rec['decision'])
            st.caption(f"Scarsità {rec['scarcity']:.0%} · bisogno lega nel ruolo {rec['league_need_role']} · confidenza giocatore {rec['confidence']:.0%} · hard cap finanziario {rec['hard_cap']}")
        st.divider(); st.subheader('Registra acquisto')
        a,b,c,d=st.columns(4); buyer=a.selectbox('Acquirente',managers,key='buyer'); bought=b.selectbox('Giocatore',available.player.tolist() if len(available) else [],key='bought'); price=c.number_input('Prezzo',1,st.session_state.rules.budget,1)
        if bought:
            brow=pool[pool.player==bought].iloc[0]; d.metric('Fair pre-vendita',f"{float(brow.get('fair_price',1)):.1f}")
            if st.button('Registra vendita',type='primary'):
                st.session_state.purchases.append(AuctionPurchase(buyer,bought,str(brow.role),price,float(brow.get('fair_price',1)))); st.rerun()
        if st.session_state.purchases:
            purch=pd.DataFrame([p.__dict__ for p in st.session_state.purchases]); st.dataframe(purch,use_container_width=True)
            st.subheader('Profilo avversari appreso')
            rows=[]
            for m in managers:
                rows.append({'manager':m,'budget_left':state.remaining(m),'P_aggr':state.manager_aggression(m,'P'),'D_aggr':state.manager_aggression(m,'D'),'C_aggr':state.manager_aggression(m,'C'),'A_aggr':state.manager_aggression(m,'A')})
            st.dataframe(pd.DataFrame(rows),use_container_width=True)
            if st.button('Annulla ultimo acquisto'): st.session_state.purchases.pop(); st.rerun()
