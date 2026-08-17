from __future__ import annotations
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT=Path(__file__).parent; sys.path.insert(0,str(ROOT))
from src.fanta_lab.models import LeagueRules,AuctionPurchase
from src.fanta_lab.projection import add_projections,add_market_comparison
from src.fanta_lab.auction import AuctionState,allocate_fair_prices,live_recommendation
from src.fanta_lab.pipeline import build_dataset
from src.fanta_lab.sources.fantacalcio import load_user_list
from src.fanta_lab.sources.auction_market import load_real_auction_averages,attach_market_prior

st.set_page_config(page_title='Fanta Auction Lab',page_icon='⚽',layout='wide')
st.title('Fanta Auction Lab · V4')
st.caption('Player intelligence + market reality + live auction copilot. Observed data and model estimates remain separate.')

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'coverage' not in st.session_state: st.session_state.coverage=None
if 'manager_names' not in st.session_state: st.session_state.manager_names=['Io']+[f'Avversario {i}' for i in range(1,8)]
if 'my_manager' not in st.session_state: st.session_state.my_manager='Io'
if 'manager_notes' not in st.session_state: st.session_state.manager_notes={}
if 'global_notes' not in st.session_state: st.session_state.global_notes=''


def build_state():
    names=st.session_state.manager_names[:int(st.session_state.rules.managers)]
    while len(names)<int(st.session_state.rules.managers): names.append(f'Avversario {len(names)}')
    st.session_state.manager_names=names
    if st.session_state.my_manager not in names: st.session_state.my_manager=names[0]
    state=AuctionState(st.session_state.rules,names,st.session_state.my_manager)
    for p in st.session_state.purchases:
        try: state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
        except TypeError: pass
    return state


def export_state():
    return json.dumps({
        'version':4,'rules':st.session_state.rules.to_dict(),'managers':st.session_state.manager_names,
        'my_manager':st.session_state.my_manager,
        'purchases':[asdict(p) if isinstance(p,AuctionPurchase) else p for p in st.session_state.purchases],
        'manager_notes':st.session_state.manager_notes,'global_notes':st.session_state.global_notes,
    },ensure_ascii=False,indent=2)

setup,data_tab,rankings,auction,teams_tab=st.tabs(['1 · Lega','2 · Dati','3 · Player Intelligence','4 · Asta LIVE','5 · Squadre & appunti'])

with setup:
    st.subheader('Regole della lega')
    r=st.session_state.rules
    a,b,c,d=st.columns(4); r.budget=int(a.number_input('Budget per squadra',50,5000,int(r.budget))); r.managers=int(b.number_input('Partecipanti',2,20,int(r.managers))); r.slots_gk=int(c.number_input('Portieri',1,5,int(r.slots_gk))); r.slots_def=int(d.number_input('Difensori',1,15,int(r.slots_def)))
    a,b,c,d=st.columns(4); r.slots_mid=int(a.number_input('Centrocampisti',1,15,int(r.slots_mid))); r.slots_fwd=int(b.number_input('Attaccanti',1,10,int(r.slots_fwd))); r.assist=c.number_input('Bonus assist',-5.,10.,float(r.assist),.5); r.clean_sheet_gk=d.number_input('Porta inviolata P',-5.,10.,float(r.clean_sheet_gk),.5)
    a,b,c,d=st.columns(4); r.goal_gk=a.number_input('Gol P',-5.,15.,float(r.goal_gk),.5); r.goal_def=b.number_input('Gol D',-5.,15.,float(r.goal_def),.5); r.goal_mid=c.number_input('Gol C',-5.,15.,float(r.goal_mid),.5); r.goal_fwd=d.number_input('Gol A',-5.,15.,float(r.goal_fwd),.5)
    a,b,c,d=st.columns(4); r.yellow=a.number_input('Ammonizione',-5.,2.,float(r.yellow),.5); r.red=b.number_input('Espulsione',-10.,2.,float(r.red),.5); r.clean_sheet_def=c.number_input('Porta inviolata D',-5.,10.,float(r.clean_sheet_def),.5); r.defense_modifier=d.toggle('Modificatore difesa',bool(r.defense_modifier))
    if r.defense_modifier:r.defense_modifier_strength=st.slider('Peso marginale modificatore',0.,2.,float(r.defense_modifier_strength),.1)
    st.divider(); st.subheader('Partecipanti')
    defaults=st.session_state.manager_names[:r.managers]
    raw=st.text_area('Una squadra/manager per riga',value='\n'.join(defaults),height=180)
    names=[x.strip() for x in raw.splitlines() if x.strip()]
    if st.button('Salva partecipanti'):
        if len(names)!=r.managers: st.error(f'Inserisci esattamente {r.managers} nomi.')
        elif len(set(names))!=len(names): st.error('I nomi devono essere univoci.')
        else:
            st.session_state.manager_names=names
            if st.session_state.my_manager not in names: st.session_state.my_manager=names[0]
            st.success('Partecipanti salvati.')
    if st.session_state.manager_names:
        st.session_state.my_manager=st.selectbox('La mia squadra',st.session_state.manager_names,index=st.session_state.manager_names.index(st.session_state.my_manager) if st.session_state.my_manager in st.session_state.manager_names else 0)
    st.info('Il motore usa le regole reali della lega per proiettare punti, replacement level e prezzi. Il MAX BID non è un tetto statico: cambia con la stanza.')

with data_tab:
    st.subheader('Pipeline Serie A 2026/27')
    st.write('Il roster master è lossless: il backbone delle rose e il Listone vengono riconciliati; una fonte incompleta non può essere dichiarata certificata.')
    with st.expander('Costruisci dataset',expanded=False):
        token=st.text_input('football-data.org API token (gratuito)',type='password')
        season=st.number_input('Anno iniziale stagione',2020,2030,2026)
        label=st.text_input('Etichetta stagione Fantacalcio','2026/27')
        list_file=st.file_uploader('Listone CSV/XLSX corrente (opzionale ma raccomandato)',type=['csv','xlsx','xls'],key='listone')
        if st.button('Costruisci e certifica',type='primary'):
            try:
                fdf=load_user_list(list_file) if list_file else None
                master,report=build_dataset(int(season),label,token or None,fantasy_df=fdf,require_current_fanta=True)
                st.session_state.players=master; st.session_state.coverage=report; st.session_state.pop('scored',None)
                st.success(f'Dataset: {len(master)} giocatori · {report.certification}')
            except Exception as e: st.error(str(e))
    up=st.file_uploader('Oppure carica un master CSV',type=['csv'],key='master')
    if up:
        st.session_state.players=pd.read_csv(up); st.session_state.pop('scored',None)
    if not st.session_state.players.empty:
        st.divider(); st.subheader('Prior di mercato da aste reali aggregate')
        st.caption('Fonte opzionale: prezzi medi pubblici realmente pagati. Serve a calibrare il comportamento umano; non sostituisce il nostro valore indipendente.')
        if st.button('Aggancia medie aste reali pubbliche'):
            try:
                market=load_real_auction_averages()
                st.session_state.players=attach_market_prior(st.session_state.players,market,r.managers,r.budget)
                st.session_state.pop('scored',None); st.success('Prior di mercato agganciato.')
            except Exception as e: st.warning(f'Fonte mercato non disponibile/HTML cambiato: {e}')
        df=st.session_state.players
        teams=df.team.nunique() if 'team' in df else 0; fvm=int(df.get('fvm_1000',pd.Series(dtype=float)).notna().sum()); hist=int(pd.to_numeric(df.get('minutes',pd.Series(dtype=float)),errors='coerce').fillna(0).gt(0).sum())
        a,b,c,d=st.columns(4); a.metric('Giocatori master',len(df)); b.metric('Squadre',teams); c.metric('Con FVM',fvm); d.metric('Con storico',hist)
        report=st.session_state.coverage
        if report:
            (st.success if report.certified else st.warning)(f'Coverage gate: {report.certification}')
        cols=[c for c in ['player','team','role','quotation','fvm_1000','market_auction_price','has_history','data_confidence','source'] if c in df]
        st.dataframe(df[cols].head(200),use_container_width=True)
    else: st.warning('Nessun dataset caricato.')

with rankings:
    if st.session_state.players.empty: st.warning('Carica prima i dati.')
    else:
        df=st.session_state.players.copy()
        for c,v in {'role':'C','minutes':0,'goals':0,'assists':0,'xg':0,'xa':0,'yellow_cards':0,'red_cards':0}.items():
            if c not in df: df[c]=v
        scored=allocate_fair_prices(add_market_comparison(add_projections(df,r)),r); st.session_state.scored=scored
        a,b,c=st.columns(3); role=a.selectbox('Ruolo',['Tutti','P','D','C','A']); sort=b.selectbox('Ordina per',['independent_score','edge_confidence_adjusted','fair_price','market_auction_price','fvm_1000','reliability']); search=c.text_input('Cerca giocatore')
        view=scored if role=='Tutti' else scored[scored.role==role]
        if search:view=view[view.player.str.contains(search,case=False,na=False)]
        cols=[c for c in ['player','team','role','quotation','fvm_1000','market_auction_price','market_score','independent_score','edge_confidence_adjusted','fair_price','projected_minutes','pred_goal90','pred_assist90','reliability'] if c in view]
        st.dataframe(view.sort_values(sort if sort in view else 'independent_score',ascending=False)[cols],use_container_width=True,height=650)
        st.caption('Market = consenso/prezzi reali osservabili. Independent = nostra proiezione sportiva sotto le regole della lega. Edge = divergenza scontata per incertezza.')

with auction:
    if 'scored' not in st.session_state: st.warning('Apri prima Player Intelligence per generare i valori.')
    else:
        pool=st.session_state.scored; state=build_state(); me=state.my_manager
        sold={p.player for p in state.purchases}; available=pool[~pool.player.isin(sold)].copy()
        a,b,c,d,e=st.columns(5); a.metric('Mio budget',f'{state.remaining(me):.0f}'); b.metric('Discrezionale',f'{state.discretionary_budget(me):.0f}'); c.metric('Inflazione',f'{state.inflation():.2f}×'); d.metric('Vendite',len(state.purchases)); e.metric('Slot rimasti',sum(state.slots_left(me).values()))
        st.subheader('Giocatore chiamato')
        player=st.selectbox('Nome',available.player.tolist() if len(available) else [])
        risk=st.slider('Aggressività strategica',0.0,1.0,.58,.05,help='Più alta = maggiore disponibilità a pagare il clearing price quando aspettare è rischioso.')
        rec=None
        if player:
            row=available[available.player==player].iloc[0]; rec=live_recommendation(row,pool,state,risk_tolerance=risk)
            a,b,c,d,e,f=st.columns(6)
            a.metric('MAX BID',rec['max_bid']); b.metric('Clearing atteso',rec['expected_clearing']); c.metric('P80 stanza',rec['clearing_p80']); d.metric('Fair modello',f"{float(row.get('fair_price',0)):.1f}"); e.metric('Rischio shortage',f"{rec['shortage_risk']:.0%}"); f.metric('Decisione',rec['decision'])
            st.progress(min(1.0,float(rec['urgency'])/1.75),text=f"Urgenza strategica {rec['urgency']:.2f} · giocatori comparabili rimasti {rec['better_or_equal_left']} · pressione tier {rec['tier_pressure']:.2f}×")
            st.caption(f"Inflazione ruolo {rec['inflation']:.2f}× · domanda {rec['demand']:.0%} · hard cap {rec['hard_cap']} · replacement points {rec['replacement_points']:.1f}")
        st.divider(); st.subheader('Registra acquisto in diretta')
        a,b,c,d=st.columns([1.2,1.6,.7,1.5]); buyer=a.selectbox('Squadra',state.manager_names,key='buyer'); bought=b.selectbox('Giocatore acquistato',available.player.tolist() if len(available) else [],key='bought'); price=c.number_input('Prezzo',1,int(r.budget),1); note=d.text_input('Nota',placeholder='es. molto aggressivo sugli attaccanti')
        if bought:
            brow=pool[pool.player==bought].iloc[0]; brec=live_recommendation(brow,pool,state,risk_tolerance=risk)
            if st.button('REGISTRA VENDITA',type='primary',use_container_width=True):
                mv=brow.get('market_auction_price',None); mv=float(mv) if pd.notna(mv) else None
                st.session_state.purchases.append(AuctionPurchase(buyer,bought,str(brow.role),float(price),float(brow.get('fair_price',1)),mv,float(brec['expected_clearing']),note))
                st.rerun()
        st.divider(); st.subheader('Suggerimenti live: migliori occasioni ancora acquistabili')
        candidates=available.sort_values('independent_points',ascending=False).head(55)
        rows=[]
        for _,x in candidates.iterrows():
            if state.slots_left(me).get(str(x.role),0)<=0: continue
            rr=live_recommendation(x,pool,state,risk_tolerance=risk)
            rows.append({'player':x.player,'team':x.get('team',''),'role':x.role,'MAX BID':rr['max_bid'],'clearing':rr['expected_clearing'],'fair':round(float(x.get('fair_price',0)),1),'edge':round(float(x.get('edge_confidence_adjusted',0) or 0),1),'shortage':round(rr['shortage_risk'],2),'urgency':round(rr['urgency'],2),'decision':rr['decision']})
        if rows:
            suggestions=pd.DataFrame(rows); suggestions['room']=suggestions['MAX BID']-suggestions['clearing']
            st.dataframe(suggestions.sort_values(['decision','edge','urgency'],ascending=[True,False,False]),use_container_width=True,height=480)
        if st.session_state.purchases:
            st.subheader('Ultimi acquisti')
            purch=pd.DataFrame([asdict(p) if isinstance(p,AuctionPurchase) else p for p in st.session_state.purchases])
            st.dataframe(purch.tail(25).iloc[::-1],use_container_width=True)
            if st.button('Annulla ultimo acquisto'): st.session_state.purchases.pop(); st.rerun()

with teams_tab:
    state=build_state()
    st.subheader('Situazione completa della stanza')
    rows=[]
    for m in state.manager_names:
        sl=state.slots_left(m)
        rows.append({'squadra':m,'budget residuo':state.remaining(m),'discrezionale':state.discretionary_budget(m),'P':sl['P'],'D':sl['D'],'C':sl['C'],'A':sl['A'],'aggr P':state.manager_aggression(m,'P'),'aggr D':state.manager_aggression(m,'D'),'aggr C':state.manager_aggression(m,'C'),'aggr A':state.manager_aggression(m,'A')})
    st.dataframe(pd.DataFrame(rows),use_container_width=True)
    selected=st.selectbox('Apri squadra',state.manager_names,key='team_detail')
    roster=pd.DataFrame([asdict(p) if isinstance(p,AuctionPurchase) else p for p in state.roster(selected)])
    a,b=st.columns([2,1])
    with a:
        st.markdown(f'### Rosa · {selected}')
        if len(roster): st.dataframe(roster[['player','role','price','note']],use_container_width=True)
        else: st.caption('Nessun acquisto registrato.')
    with b:
        st.markdown('### Appunti squadra')
        existing=st.session_state.manager_notes.get(selected,'')
        text=st.text_area('Note libere',value=existing,height=180,key=f'note_{selected}')
        if st.button('Salva appunti squadra'): st.session_state.manager_notes[selected]=text; st.success('Salvato.')
    st.markdown('### Appunti generali asta')
    st.session_state.global_notes=st.text_area('Pattern, strategie, promemoria',value=st.session_state.global_notes,height=140)
    st.divider(); st.subheader('Salva / riprendi asta')
    st.download_button('Scarica stato asta JSON',data=export_state(),file_name='fanta_auction_state.json',mime='application/json')
    state_file=st.file_uploader('Ripristina stato JSON',type=['json'],key='state_json')
    if state_file and st.button('Importa stato'):
        try:
            obj=json.load(state_file); st.session_state.rules=LeagueRules(**obj['rules']); st.session_state.manager_names=obj['managers']; st.session_state.my_manager=obj['my_manager']; st.session_state.purchases=[AuctionPurchase(**p) for p in obj.get('purchases',[])]; st.session_state.manager_notes=obj.get('manager_notes',{}); st.session_state.global_notes=obj.get('global_notes',''); st.success('Stato ripristinato.'); st.rerun()
        except Exception as e: st.error(f'JSON non valido: {e}')
