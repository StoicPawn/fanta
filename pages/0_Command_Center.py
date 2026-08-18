from __future__ import annotations

from dataclasses import asdict
import pandas as pd
import streamlit as st

from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.independent_model import build_independent_valuation
from src.fanta_lab.auction import AuctionState, live_recommendation
from src.fanta_lab.target_engine import build_target_plan, replacement_candidates
from src.fanta_lab.plan_health import role_spend_envelopes, plan_resilience, role_risk_summary, alternative_buckets

st.set_page_config(page_title='Command Center · Fanta Auction Lab',page_icon='🎛️',layout='wide')
st.markdown('''<style>
.block-container{padding-top:1.1rem;max-width:1550px}.hero{padding:18px 20px;border-radius:18px;border:1px solid rgba(127,127,127,.18);background:linear-gradient(120deg,rgba(127,127,127,.08),rgba(127,127,127,.02));margin-bottom:12px}[data-testid="stMetric"]{padding:10px 12px;border:1px solid rgba(127,127,127,.14);border-radius:13px;background:rgba(127,127,127,.04)}
</style><div class="hero"><h1 style="margin:0">Auction Command Center</h1><div style="opacity:.72">Piano robusto, budget per reparto, rischio di restare scoperti e sostituti live.</div></div>''',unsafe_allow_html=True)

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'manager_names' not in st.session_state: st.session_state.manager_names=['Io']+[f'Avversario {i}' for i in range(1,8)]
if 'my_manager' not in st.session_state: st.session_state.my_manager='Io'

if st.session_state.players.empty:
    st.warning('Costruisci prima il dataset in Data Sources. Questo è il modulo operativo da usare subito dopo.')
    st.stop()

r=st.session_state.rules
names=st.session_state.manager_names[:r.managers]
while len(names)<r.managers: names.append(f'Avversario {len(names)}')
if st.session_state.my_manager not in names: st.session_state.my_manager=names[0]

pool=build_independent_valuation(st.session_state.players.copy(),r)
pool['fair_price']=pd.to_numeric(pool.independent_fair_price,errors='coerce').fillna(r.min_bid)
state=AuctionState(r,names,st.session_state.my_manager)
for p in st.session_state.purchases:
    try: state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
    except Exception: pass
me=state.my_manager; sold={p.player for p in state.purchases}; mine=[p for p in state.purchases if p.manager==me]
plan=build_target_plan(pool,r,budget=r.budget,locked=mine,sold_players=sold)
resilience=plan_resilience(pool,plan,sold)
role_risk=role_risk_summary(resilience,plan)
envelopes=role_spend_envelopes(plan,r,state.remaining(me))

k=st.columns(7)
k[0].metric('Budget',f'{state.remaining(me):.0f}')
k[1].metric('Discrezionale',f'{state.discretionary_budget(me):.0f}')
k[2].metric('Slot',sum(state.slots_left(me).values()))
k[3].metric('Inflazione',f'{state.inflation():.2f}×')
k[4].metric('Target points',f'{plan.expected_points:.0f}' if not plan.squad.empty else '—')
k[5].metric('Modifier',f'+{plan.expected_modifier_points:.1f}' if r.defense_modifier else 'OFF')
k[6].metric('Piano',f'{plan.spend:.0f}/{r.budget}' if not plan.squad.empty else '—')

plan_tab,live_tab,room_tab=st.tabs(['🎯 Piano robusto','⚡ Chiamata live','👥 Stanza'])

with plan_tab:
    if plan.squad.empty:
        st.error('Nessuna rosa completa fattibile ai prezzi correnti.')
    else:
        c1,c2=st.columns([1.35,1])
        with c1:
            st.subheader('Rosa obiettivo corrente')
            show=[c for c in ['player','team','role','independent_score_v1','independent_points','target_price','reliability','vorp'] if c in plan.squad]
            st.dataframe(plan.squad[show],use_container_width=True,hide_index=True,height=600)
        with c2:
            st.subheader('Budget per reparto')
            st.dataframe(envelopes,use_container_width=True,hide_index=True)
            st.caption('Le fasce sono corridoi morbidi: puoi superarli se il valore residuo della rosa lo giustifica.')
            st.subheader('Fragilità del piano')
            if not role_risk.empty:
                st.dataframe(role_risk,use_container_width=True,hide_index=True)
                worst=role_risk.iloc[0]
                if float(worst.risk_score)>=.55: st.warning(f"Priorità: {worst.role}. Poche alternative equivalenti rimaste: evita di rimandare troppo.")
            st.subheader('Target senza sostituti')
            fragile=resilience[resilience.fragility=='HIGH'].head(10) if not resilience.empty else pd.DataFrame()
            if fragile.empty: st.success('Nessun target è attualmente senza alternative plausibili.')
            else: st.dataframe(fragile,use_container_width=True,hide_index=True)

with live_tab:
    available=pool[~pool.player.isin(sold)].copy()
    if available.empty:
        st.success('Nessun giocatore disponibile.')
    else:
        a,b=st.columns([3,1]); called_name=a.selectbox('Giocatore chiamato',available.sort_values('independent_score_v1',ascending=False).player.tolist()); risk=b.slider('Aggressività',0.,1.,.58,.05)
        called=available[available.player==called_name].iloc[0]; rec=live_recommendation(called,pool,state,risk_tolerance=risk)
        in_plan=called_name in set(plan.squad.player) if not plan.squad.empty else False
        x=st.columns(7)
        x[0].metric('MAX BID',rec['max_bid']); x[1].metric('Clearing',rec['expected_clearing']); x[2].metric('P80',rec['clearing_p80']); x[3].metric('Fair',f"{called.independent_fair_price:.1f}"); x[4].metric('Score',f"{called.independent_score_v1:.1f}"); x[5].metric('Shortage',f"{rec.get('shortage_risk',0):.0%}"); x[6].metric('Nel piano','SÌ' if in_plan else 'NO')
        if rec['decision']=='PUSH_IF_NEEDED': st.warning('PUSH IF NEEDED: aspettare rischia di degradare la rosa finale.')
        elif rec['decision'] in {'TARGET','BUY_AT_MARKET'}: st.success(rec['decision'])
        else: st.info(rec['decision'])

        repl=replacement_candidates(called,pool,plan,r,sold_players=sold,top_n=18)
        buckets=alternative_buckets(called,repl)
        st.subheader('Alternative immediate')
        t1,t2,t3=st.tabs(['Stessa fascia','Valore/prezzo','Emergenza affidabile'])
        for tab,key in [(t1,'same_tier'),(t2,'value'),(t3,'emergency')]:
            with tab:
                if buckets[key].empty: st.caption('Nessuna alternativa in questa categoria.')
                else: st.dataframe(buckets[key],use_container_width=True,hide_index=True)

        st.divider(); st.subheader('Registra vendita')
        c=st.columns([1.2,2.3,.8,2.3])
        buyer=c[0].selectbox('Acquirente',names); bought=c[1].selectbox('Giocatore',available.player.tolist(),index=available.player.tolist().index(called_name)); price=int(c[2].number_input('Prezzo',r.min_bid,r.budget,r.min_bid)); note=c[3].text_input('Nota')
        if st.button('REGISTRA · AGGIORNA TUTTO',type='primary',use_container_width=True):
            brow=pool[pool.player==bought].iloc[0]; brec=live_recommendation(brow,pool,state,risk_tolerance=risk); market=brow.get('market_auction_price',None); market=float(market) if market is not None and pd.notna(market) else None
            st.session_state.purchases.append(AuctionPurchase(buyer,bought,str(brow.role),float(price),float(brow.fair_price),market,float(brec['expected_clearing']),note)); st.rerun()

with room_tab:
    rows=[]
    for m in names:
        sl=state.slots_left(m); rows.append({'Squadra':m,'Budget':state.remaining(m),'Discrezionale':state.discretionary_budget(m),'P':sl['P'],'D':sl['D'],'C':sl['C'],'A':sl['A'],'Agg P':round(state.manager_aggression(m,'P'),2),'Agg D':round(state.manager_aggression(m,'D'),2),'Agg C':round(state.manager_aggression(m,'C'),2),'Agg A':round(state.manager_aggression(m,'A'),2)})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    if st.session_state.purchases:
        st.subheader('Ultime vendite'); purch=pd.DataFrame([asdict(p) if isinstance(p,AuctionPurchase) else p for p in st.session_state.purchases]); st.dataframe(purch.tail(35).iloc[::-1],use_container_width=True,hide_index=True)
        if st.button('↩️ Annulla ultima vendita'): st.session_state.purchases.pop(); st.rerun()
