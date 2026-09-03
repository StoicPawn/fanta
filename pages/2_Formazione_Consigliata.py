from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.independent_model import build_independent_valuation
from src.fanta_lab.auction import AuctionState
from src.fanta_lab.target_engine import build_target_plan, expected_defence_modifier
from src.fanta_lab.plan_health import plan_resilience, role_risk_summary, role_spend_envelopes
from src.fanta_lab.ui import apply_theme, page_header, section, common_sidebar, empty_state

st.set_page_config(page_title='Formazione consigliata · Fanta Auction Lab', page_icon='🧩', layout='wide')
apply_theme(); common_sidebar()
page_header('Formazione consigliata', 'La rosa-obiettivo si ricostruisce dopo ogni vendita: budget, giocatori già presi, disponibilità residua e regole della lega cambiano la soluzione.', 'PIANO DINAMICO')

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'manager_names' not in st.session_state: st.session_state.manager_names=['Io']+[f'Avversario {i}' for i in range(1,8)]
if 'my_manager' not in st.session_state: st.session_state.my_manager='Io'

if st.session_state.players.empty:
    empty_state('Dataset necessario', 'Costruisci prima il master in Data Sources. Questa pagina userà automaticamente le regole e lo stato asta correnti.')
    st.stop()

r=st.session_state.rules
pool=build_independent_valuation(st.session_state.players.copy(),r)
pool['fair_price']=pd.to_numeric(pool['independent_fair_price'],errors='coerce').fillna(r.min_bid)
names=st.session_state.manager_names[:r.managers]
while len(names)<r.managers: names.append(f'Avversario {len(names)}')
me=st.session_state.my_manager if st.session_state.my_manager in names else names[0]
state=AuctionState(r,names,me)
for p in st.session_state.purchases:
    try: state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
    except Exception: pass
sold={p.player for p in state.purchases}; locked=[p for p in state.purchases if p.manager==me]
plan=build_target_plan(pool,r,budget=r.budget,locked=locked,sold_players=sold)

if plan.squad.empty:
    st.error('Non esiste al momento una rosa completa fattibile. Verifica budget, slot e prezzi stimati.')
    st.stop()

# plan_health.py espone la nuova API a componenti: resilienza per giocatore,
# sintesi del rischio per ruolo e corridoi di spesa. La pagina usa direttamente
# questi nomi per evitare dipendenze da alias rimossi durante il refactoring.
resilience=plan_resilience(pool,plan,sold_players=sold)
health=role_risk_summary(resilience,plan)
corridors=role_spend_envelopes(plan,r,remaining_budget=state.remaining(me))
frag=float(health['risk_score'].max()) if len(health) else 0
k=st.columns(6)
k[0].metric('Budget residuo',f'{state.remaining(me):.0f}')
k[1].metric('Spesa target',f'{plan.spend:.0f}/{r.budget}')
k[2].metric('Punti attesi',f'{plan.expected_points:.0f}')
k[3].metric('Slot rimasti',sum(state.slots_left(me).values()))
k[4].metric('Modificatore',f'+{plan.expected_modifier_points:.1f}' if r.defense_modifier else 'OFF')
k[5].metric('Fragilità max',f'{frag:.0%}')

summary, by_role, health_tab = st.tabs(['Rosa target','Per reparto','Rischio piano'])
with summary:
    section('Rosa obiettivo corrente','I giocatori già acquistati dalla tua squadra sono bloccati; gli altri vengono ottimizzati sui giocatori ancora disponibili.')
    show=[c for c in ['player','team','role','independent_score_v1','independent_points','target_price','reliability','vorp'] if c in plan.squad]
    display=plan.squad[show].copy()
    st.dataframe(display,use_container_width=True,height=610,hide_index=True,column_config={
        'player':'Giocatore','team':'Squadra','role':'R','independent_score_v1':st.column_config.NumberColumn('Score',format='%.1f'),
        'independent_points':st.column_config.NumberColumn('Punti attesi',format='%.1f'),'target_price':st.column_config.NumberColumn('Prezzo target',format='%.0f'),
        'reliability':st.column_config.ProgressColumn('Affidabilità',min_value=0,max_value=1,format='%.0%%'),'vorp':st.column_config.NumberColumn('VORP',format='%.1f')})
    st.download_button('Esporta rosa consigliata',plan.squad.to_csv(index=False).encode(),file_name='formazione_consigliata.csv',mime='text/csv',use_container_width=True)

with by_role:
    section('Allocazione del budget','I corridoi sono indicazioni elastiche: il motore può riallocare crediti se cambia il valore relativo dei reparti.')
    st.dataframe(corridors,use_container_width=True,hide_index=True)
    cols=st.columns(4)
    for col,role in zip(cols,['P','D','C','A']):
        rr=plan.squad[plan.squad.role.astype(str).str.upper().eq(role)].sort_values('independent_score_v1',ascending=False)
        with col:
            st.markdown(f'**{role} · {len(rr)} target**')
            for _,x in rr.iterrows():
                st.caption(f"{x.player} · score {x.independent_score_v1:.0f} · {x.target_price:.0f} cr")
    if r.defense_modifier:
        defensive=plan.squad[plan.squad.role.isin(['P','D'])]
        st.info(f'Con le regole correnti il blocco difensivo target vale circa **{expected_defence_modifier(defensive,r):.2f}** punti attesi di modificatore nel proxy portfolio-level.')

with health_tab:
    section('Fragilità e alternative','Un rischio alto indica target difficili da rimpiazzare: sono i giocatori/reparti per cui rimandare l’acquisto è più costoso.')
    if len(health):
        st.dataframe(health.sort_values('risk_score',ascending=False),use_container_width=True,hide_index=True,column_config={'risk_score':st.column_config.ProgressColumn('Rischio',min_value=0,max_value=1,format='%.0%%')})
        worst=health.sort_values('risk_score',ascending=False).iloc[0]
        if float(worst.risk_score)>=.55: st.warning(f"Priorità attuale: **{worst.get('role','')}** · il piano ha poche alternative equivalenti.")
        else: st.success('Il piano corrente ha una buona profondità di alternative.')
    if len(resilience):
        st.markdown('**Dettaglio target per target**')
        st.dataframe(resilience,use_container_width=True,hide_index=True,column_config={
            'player':'Giocatore','role':'R','alternatives':'Alternative equivalenti','fragility':'Fragilità',
            'target_points':st.column_config.NumberColumn('Punti target',format='%.1f'),
            'target_price':st.column_config.NumberColumn('Prezzo target',format='%.0f')})
