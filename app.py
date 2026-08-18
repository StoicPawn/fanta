from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fanta_lab.models import LeagueRules
from src.fanta_lab.ui import apply_theme,page_header,section,common_sidebar

st.set_page_config(page_title='Fanta Auction Lab',page_icon='⚽',layout='wide')
apply_theme(); common_sidebar()
page_header('Fanta Auction Lab','Valutazione indipendente, rosa-obiettivo e guida live all’asta. Il prodotto separa sempre prestazione sportiva, mercato fantasy e comportamento reale della stanza.','SERIE A AUCTION INTELLIGENCE')

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'manager_names' not in st.session_state: st.session_state.manager_names=['Io']+[f'Avversario {i}' for i in range(1,8)]
if 'my_manager' not in st.session_state: st.session_state.my_manager='Io'

r=st.session_state.rules; players=st.session_state.players; purchases=st.session_state.purchases
k=st.columns(5)
k[0].metric('Dataset','PRONTO' if not players.empty else 'DA COSTRUIRE')
k[1].metric('Giocatori',len(players) if not players.empty else 0)
k[2].metric('Partecipanti',r.managers)
k[3].metric('Budget',r.budget)
k[4].metric('Vendite registrate',len(purchases))

section('Flusso operativo','Quattro passaggi principali; gli altri moduli servono per analisi più profonde o manutenzione dati.')
cols=st.columns(4)
with cols[0]:
    st.markdown('### 1 · Data Sources')
    st.caption('Costruisci e certifica il master Serie A con tutte le fonti gratuite disponibili.')
    st.page_link('pages/7_Data_Sources.py',label='Apri Data Sources',icon='🗄️')
with cols[1]:
    st.markdown('### 2 · Formazione')
    st.caption('Ottieni la rosa-obiettivo coerente con regole, budget e giocatori ancora disponibili.')
    st.page_link('pages/2_Formazione_Consigliata.py',label='Apri Formazione',icon='🧩')
with cols[2]:
    st.markdown('### 3 · Ranking')
    st.caption('Esplora score indipendente, rischio, VORP, fair price e confronto con il mercato.')
    st.page_link('pages/3_Ranking_Giocatori.py',label='Apri Ranking',icon='📊')
with cols[3]:
    st.markdown('### 4 · Command Center')
    st.caption('Durante l’asta: MAX BID, shortage, sostituti, stanza e note sugli avversari.')
    st.page_link('pages/0_Command_Center.py',label='Apri Command Center',icon='🎛️')

st.divider()
left,right=st.columns([1.4,1])
with left:
    section('Configurazione rapida lega','Questi parametri sono condivisi da tutti i moduli. Le regole avanzate restano nella pagina Health.')
    a,b,c,d=st.columns(4)
    r.budget=int(a.number_input('Budget',50,5000,int(r.budget)))
    r.managers=int(b.number_input('Partecipanti',2,20,int(r.managers)))
    r.slots_gk=int(c.number_input('Portieri',1,5,int(r.slots_gk)))
    r.slots_def=int(d.number_input('Difensori',1,15,int(r.slots_def)))
    a,b,c,d=st.columns(4)
    r.slots_mid=int(a.number_input('Centrocampisti',1,15,int(r.slots_mid)))
    r.slots_fwd=int(b.number_input('Attaccanti',1,10,int(r.slots_fwd)))
    r.assist=float(c.number_input('Bonus assist',-5.,10.,float(r.assist),.5))
    r.clean_sheet_gk=float(d.number_input('Porta inviolata P',-5.,10.,float(r.clean_sheet_gk),.5))
    a,b,c,d=st.columns(4)
    r.goal_def=float(a.number_input('Gol D',-5.,15.,float(r.goal_def),.5))
    r.goal_mid=float(b.number_input('Gol C',-5.,15.,float(r.goal_mid),.5))
    r.goal_fwd=float(c.number_input('Gol A',-5.,15.,float(r.goal_fwd),.5))
    r.defense_modifier=d.toggle('Modificatore difesa',value=bool(r.defense_modifier))
    if r.defense_modifier:
        st.caption('Soglie e bonus del modificatore sono configurabili nel Command Center / Advanced Settings.')
with right:
    section('Partecipanti')
    defaults=st.session_state.manager_names[:r.managers]
    while len(defaults)<r.managers: defaults.append(f'Avversario {len(defaults)}')
    raw=st.text_area('Una squadra per riga',value='\n'.join(defaults),height=215)
    names=[x.strip() for x in raw.splitlines() if x.strip()]
    if len(names)==r.managers and len(set(names))==len(names):
        st.session_state.manager_names=names
        if st.session_state.my_manager not in names: st.session_state.my_manager=names[0]
        st.session_state.my_manager=st.selectbox('La mia squadra',names,index=names.index(st.session_state.my_manager))
        st.success('Configurazione partecipanti valida.')
    else:
        st.warning(f'Servono esattamente {r.managers} nomi univoci.')

st.divider()
section('Moduli di supporto')
a,b,c,d=st.columns(4)
with a: st.page_link('pages/6_Strategy_Lab.py',label='Strategy Lab · BUY vs WAIT',icon='🧠')
with b: st.page_link('pages/8_Gap_Analyzer.py',label='Gap Analyzer · qualità dati',icon='🧩')
with c: st.page_link('pages/9_Source_Control.py',label='Source Control · refresh/cache',icon='🔄')
with d: st.page_link('pages/7_Advanced_Settings_and_Health.py',label='Advanced & Health',icon='🩺')
