from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT))
from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.auction import AuctionState
from src.fanta_lab.health import dataset_health, auction_health

st.set_page_config(page_title='Advanced settings & health',layout='wide')
st.title('Advanced settings & health')
st.caption('Regole avanzate, controlli di coerenza e readiness prima dell asta.')

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'manager_names' not in st.session_state: st.session_state.manager_names=['Io']+[f'Avversario {i}' for i in range(1,8)]
if 'my_manager' not in st.session_state: st.session_state.my_manager=st.session_state.manager_names[0]

r=st.session_state.rules
st.subheader('Regole avanzate')
a,b,c,d=st.columns(4)
r.goal_conceded_gk=a.number_input('Gol subito portiere',-5.0,1.0,float(r.goal_conceded_gk),.5)
r.penalty_saved=b.number_input('Rigore parato',-2.0,10.0,float(r.penalty_saved),.5)
r.penalty_missed=c.number_input('Rigore sbagliato',-10.0,1.0,float(r.penalty_missed),.5)
r.own_goal=d.number_input('Autogol',-10.0,1.0,float(r.own_goal),.5)
a,b,c=st.columns(3)
r.base_vote_weight=a.number_input('Peso voto base',0.0,2.0,float(r.base_vote_weight),.05)
r.min_bid=int(b.number_input('Offerta minima',1,20,int(r.min_bid)))
r.defense_modifier_strength=c.number_input('Peso modificatore difesa',0.0,3.0,float(r.defense_modifier_strength),.1)
st.info('Il voto base entra nel totale atteso. Le metriche avanzate vengono usate solo se presenti; altrimenti il modello usa prior prudenti.')

st.divider()
st.subheader('Salute dataset')
h=dataset_health(st.session_state.players)
a,b,c=st.columns(3)
a.metric('Readiness',h['status'])
b.metric('Quality score',f"{h['score']}/100")
c.metric('Giocatori',h['metrics'].get('players',0))
if h['issues']:
    for x in h['issues']: st.warning(x)
else:
    st.success('Nessuna anomalia strutturale rilevata.')
if h['metrics']:
    st.dataframe(pd.DataFrame([h['metrics']]).T.rename(columns={0:'value'}),use_container_width=True)

st.divider()
st.subheader('Salute asta')
names=st.session_state.manager_names[:int(r.managers)]
if not names: names=['Io']
me=st.session_state.my_manager if st.session_state.my_manager in names else names[0]
state=AuctionState(r,names,me)
for p in st.session_state.purchases:
    try:
        state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
    except Exception:
        pass
ah=auction_health(state)
if ah['status']=='OK':
    st.success('Stato asta coerente: budget, slot e unicita acquisti sono validi.')
else:
    for x in ah['issues']: st.error(x)

st.divider()
st.subheader('Checklist pre-asta')
checks={
    '20 squadre presenti': h['metrics'].get('teams',0)==20,
    'nessun duplicato player/team': h['metrics'].get('duplicates',1)==0,
    'ruoli validi': h['metrics'].get('invalid_roles',1)==0,
    'copertura FVM almeno 90%': h['metrics'].get('coverage_fvm_1000',0)>=.90,
    'copertura minuti almeno 70%': h['metrics'].get('coverage_minutes',0)>=.70,
    'stato asta coerente': ah['status']=='OK',
}
for label,ok in checks.items():
    st.write(('OK - ' if ok else 'WARN - ')+label)
