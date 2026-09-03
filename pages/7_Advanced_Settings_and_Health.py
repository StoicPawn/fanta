from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.auction import AuctionState
from src.fanta_lab.health import dataset_health, auction_health
from src.fanta_lab.persistence import autosave_active_slot
from src.fanta_lab.ui import apply_theme,page_header,section,common_sidebar

st.set_page_config(page_title='Advanced settings & health',page_icon='🩺',layout='wide')
apply_theme(); common_sidebar()
page_header('Advanced settings & health','Regole meno comuni, controlli di coerenza e readiness tecnica prima di affidarsi al motore durante l’asta.','SYSTEM HEALTH')

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'manager_names' not in st.session_state: st.session_state.manager_names=['Io']+[f'Avversario {i}' for i in range(1,8)]
if 'my_manager' not in st.session_state: st.session_state.my_manager=st.session_state.manager_names[0]
r=st.session_state.rules

settings, data_tab, auction_tab, checklist=st.tabs(['Regole avanzate','Salute dataset','Salute asta','Checklist'])
with settings:
    section('Regole avanzate','Modificano direttamente la proiezione fantasy quando il dato necessario è disponibile.')
    a,b,c,d=st.columns(4)
    r.goal_conceded_gk=a.number_input('Gol subito portiere',-5.0,1.0,float(r.goal_conceded_gk),.5)
    r.penalty_saved=b.number_input('Rigore parato',-2.0,10.0,float(r.penalty_saved),.5)
    r.penalty_missed=c.number_input('Rigore sbagliato',-10.0,1.0,float(r.penalty_missed),.5)
    r.own_goal=d.number_input('Autogol',-10.0,1.0,float(r.own_goal),.5)
    a,b,c=st.columns(3)
    r.base_vote_weight=a.number_input('Peso voto base',0.0,2.0,float(r.base_vote_weight),.05)
    r.min_bid=int(b.number_input('Offerta minima',1,20,int(r.min_bid)))
    r.defense_modifier_strength=c.number_input('Peso modificatore difesa',0.0,3.0,float(r.defense_modifier_strength),.1)
    st.info('Le metriche avanzate vengono usate solo quando presenti; altrimenti il modello applica prior prudenti e riduce la confidenza.')

h=dataset_health(st.session_state.players)
with data_tab:
    c=st.columns(4); c[0].metric('Readiness',h['status']); c[1].metric('Quality score',f"{h['score']}/100"); c[2].metric('Giocatori',h['metrics'].get('players',0)); c[3].metric('Squadre',h['metrics'].get('teams',0))
    if h['issues']:
        for x in h['issues']: st.warning(x)
    else: st.success('Nessuna anomalia strutturale rilevata.')
    if h['metrics']:
        metrics=pd.DataFrame([{'Metrica':k,'Valore':v} for k,v in h['metrics'].items()])
        st.dataframe(metrics,use_container_width=True,hide_index=True)

names=st.session_state.manager_names[:int(r.managers)] or ['Io']; me=st.session_state.my_manager if st.session_state.my_manager in names else names[0]
state=AuctionState(r,names,me)
for p in st.session_state.purchases:
    try: state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
    except Exception: pass
ah=auction_health(state)
with auction_tab:
    c=st.columns(4); c[0].metric('Stato',ah['status']); c[1].metric('Vendite',len(state.purchases)); c[2].metric('Budget mio',f'{state.remaining(me):.0f}'); c[3].metric('Slot miei',sum(state.slots_left(me).values()))
    if ah['status']=='OK': st.success('Budget, slot e unicità degli acquisti sono coerenti.')
    else:
        for x in ah['issues']: st.error(x)

with checklist:
    checks={
        '20 squadre presenti': h['metrics'].get('teams',0)==20,
        'Nessun duplicato player/team': h['metrics'].get('duplicates',1)==0,
        'Ruoli validi': h['metrics'].get('invalid_roles',1)==0,
        'Copertura FVM almeno 90%': h['metrics'].get('coverage_fvm_1000',0)>=.90,
        'Copertura minuti almeno 70%': h['metrics'].get('coverage_minutes',0)>=.70,
        'Stato asta coerente': ah['status']=='OK',
    }
    done=sum(checks.values()); st.metric('Checklist completata',f'{done}/{len(checks)}')
    for label,ok in checks.items():
        (st.success if ok else st.warning)(('OK · ' if ok else 'DA VERIFICARE · ')+label)

autosave_active_slot(st.session_state)
