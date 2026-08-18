from __future__ import annotations

from dataclasses import asdict
import pandas as pd
import streamlit as st

from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.independent_model import build_independent_valuation
from src.fanta_lab.auction import AuctionState, live_recommendation
from src.fanta_lab.target_engine import build_target_plan, replacement_candidates, expected_defence_modifier

st.set_page_config(page_title='Copilot Principale · Fanta Auction Lab',page_icon='🎯',layout='wide')

st.markdown('''
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1500px;}
[data-testid="stMetric"] {background: rgba(127,127,127,.06); border:1px solid rgba(127,127,127,.15); padding:12px 14px; border-radius:14px;}
[data-testid="stMetricValue"] {font-size:1.65rem;}
.hero {padding:20px 22px;border:1px solid rgba(127,127,127,.18);border-radius:18px;margin-bottom:16px;background:linear-gradient(120deg,rgba(127,127,127,.08),rgba(127,127,127,.02));}
.small {opacity:.75;font-size:.92rem}
</style>
''',unsafe_allow_html=True)

st.markdown('<div class="hero"><h1 style="margin:0">Fanta Auction Copilot</h1><div class="small">Piano rosa → chiamata live → MAX BID → sostituti → nuovo piano. Ogni valore dipende dalle regole reali della tua lega.</div></div>',unsafe_allow_html=True)

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'manager_names' not in st.session_state: st.session_state.manager_names=['Io']+[f'Avversario {i}' for i in range(1,8)]
if 'my_manager' not in st.session_state: st.session_state.my_manager='Io'

r=st.session_state.rules

with st.expander('⚙️  Regole lega e partecipanti',expanded=st.session_state.players.empty):
    a,b,c,d,e=st.columns(5)
    r.budget=int(a.number_input('Budget',50,5000,int(r.budget)))
    r.managers=int(b.number_input('Partecipanti',2,20,int(r.managers)))
    r.slots_gk=int(c.number_input('P',1,5,int(r.slots_gk)))
    r.slots_def=int(d.number_input('D',1,15,int(r.slots_def)))
    r.slots_mid=int(e.number_input('C',1,15,int(r.slots_mid)))
    a,b,c,d,e=st.columns(5)
    r.slots_fwd=int(a.number_input('A',1,10,int(r.slots_fwd)))
    r.min_bid=int(b.number_input('Offerta minima',1,20,int(r.min_bid)))
    r.assist=float(c.number_input('Assist',-5.,10.,float(r.assist),.5))
    r.clean_sheet_gk=float(d.number_input('Porta inviolata P',-5.,10.,float(r.clean_sheet_gk),.5))
    r.clean_sheet_def=float(e.number_input('Porta inviolata D',-5.,10.,float(r.clean_sheet_def),.5))
    a,b,c,d=st.columns(4)
    r.goal_gk=float(a.number_input('Gol P',-5.,15.,float(r.goal_gk),.5))
    r.goal_def=float(b.number_input('Gol D',-5.,15.,float(r.goal_def),.5))
    r.goal_mid=float(c.number_input('Gol C',-5.,15.,float(r.goal_mid),.5))
    r.goal_fwd=float(d.number_input('Gol A',-5.,15.,float(r.goal_fwd),.5))
    a,b,c,d,e=st.columns(5)
    r.goal_conceded_gk=float(a.number_input('Gol subito P',-5.,2.,float(r.goal_conceded_gk),.5))
    r.penalty_saved=float(b.number_input('Rigore parato',0.,10.,float(r.penalty_saved),.5))
    r.penalty_missed=float(c.number_input('Rigore sbagliato',-10.,0.,float(r.penalty_missed),.5))
    r.yellow=float(d.number_input('Ammonizione',-5.,0.,float(r.yellow),.5))
    r.red=float(e.number_input('Espulsione',-10.,0.,float(r.red),.5))
    r.defense_modifier=st.toggle('Modificatore difesa',value=bool(r.defense_modifier))
    if r.defense_modifier:
        a,b,c,d=st.columns(4)
        r.modifier_defenders_required=int(a.number_input('Difensori richiesti',3,5,int(r.modifier_defenders_required)))
        r.defense_modifier_strength=float(b.number_input('Peso modificatore',0.,3.,float(r.defense_modifier_strength),.1))
        c.caption('Fasce media voto → bonus')
        d.caption('Personalizzabili sotto')
        a,b,c,d,e,f=st.columns(6)
        r.modifier_threshold_1=float(a.number_input('Soglia 1',5.,8.,float(r.modifier_threshold_1),.05))
        r.modifier_bonus_1=float(b.number_input('Bonus 1',0.,10.,float(r.modifier_bonus_1),.5))
        r.modifier_threshold_2=float(c.number_input('Soglia 2',5.,8.,float(r.modifier_threshold_2),.05))
        r.modifier_bonus_2=float(d.number_input('Bonus 2',0.,15.,float(r.modifier_bonus_2),.5))
        r.modifier_threshold_3=float(e.number_input('Soglia 3',5.,8.,float(r.modifier_threshold_3),.05))
        r.modifier_bonus_3=float(f.number_input('Bonus 3',0.,20.,float(r.modifier_bonus_3),.5))

    defaults=st.session_state.manager_names[:r.managers]
    while len(defaults)<r.managers: defaults.append(f'Avversario {len(defaults)}')
    raw=st.text_area('Squadre partecipanti · una per riga',value='\n'.join(defaults),height=120)
    names=[x.strip() for x in raw.splitlines() if x.strip()]
    if len(names)==r.managers and len(set(names))==len(names): st.session_state.manager_names=names
    if st.session_state.manager_names:
        st.session_state.my_manager=st.selectbox('La mia squadra',st.session_state.manager_names,index=st.session_state.manager_names.index(st.session_state.my_manager) if st.session_state.my_manager in st.session_state.manager_names else 0)

if st.session_state.players.empty:
    st.warning('Prima costruisci il dataset dalla pagina “Data Sources”. Quando esiste il master, qui appare automaticamente il piano d’asta.')
    st.stop()

# Build independent model directly from league rules; market fields cannot leak into the score.
try:
    pool=build_independent_valuation(st.session_state.players.copy(),r)
except Exception as e:
    st.error(f'Impossibile costruire la valutazione indipendente: {e}')
    st.stop()
# Auction module expects fair_price; use independent value as its sporting anchor.
pool['fair_price']=pd.to_numeric(pool['independent_fair_price'],errors='coerce').fillna(r.min_bid)

names=st.session_state.manager_names[:r.managers]
state=AuctionState(r,names,st.session_state.my_manager)
for p in st.session_state.purchases:
    try: state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
    except Exception: pass
me=state.my_manager
sold={p.player for p in state.purchases}
my_locked=[p for p in state.purchases if p.manager==me]
plan=build_target_plan(pool,r,budget=r.budget,locked=my_locked,sold_players=sold)

# Header KPIs
m1,m2,m3,m4,m5,m6=st.columns(6)
m1.metric('Budget residuo',f'{state.remaining(me):.0f}')
m2.metric('Slot rimasti',sum(state.slots_left(me).values()))
m3.metric('Inflazione stanza',f'{state.inflation():.2f}×')
m4.metric('Punti rosa target',f'{plan.expected_points:.0f}' if not plan.squad.empty else '—')
m5.metric('Mod. difesa atteso',f'+{plan.expected_modifier_points:.1f}' if r.defense_modifier and not plan.squad.empty else 'OFF')
m6.metric('Spesa piano',f'{plan.spend:.0f}/{r.budget}' if not plan.squad.empty else '—')

pre,live,room=st.tabs(['🎯 Piano iniziale','⚡ Asta LIVE','👥 Stanza'])

with pre:
    st.subheader('Rosa a cui puntare')
    st.caption('È una soluzione di portafoglio: punti attesi, scarsità, affidabilità, budget e — se attivo — qualità combinata del blocco difensivo. Non è una semplice Top 25.')
    if plan.squad.empty:
        st.error('Con il budget/prezzi correnti non esiste una rosa completa fattibile. Controlla budget, slot o dataset.')
    else:
        a,b,c,d=st.columns(4)
        for col,role in zip([a,b,c,d],['P','D','C','A']):
            col.metric(f'Budget {role}',f"{plan.role_budget.get(role,0):.0f}")
        show=[c for c in ['player','team','role','independent_score_v1','independent_points','target_price','reliability','vorp','independent_score_floor','independent_score_ceiling'] if c in plan.squad]
        st.dataframe(plan.squad[show],use_container_width=True,height=610,hide_index=True)
        st.download_button('Esporta piano CSV',plan.squad.to_csv(index=False).encode(),file_name='rosa_target.csv',mime='text/csv',use_container_width=True)
        if r.defense_modifier:
            defensive=plan.squad[plan.squad.role.isin(['P','D'])]
            st.info(f'Il blocco P+D selezionato produce circa **{expected_defence_modifier(defensive,r):.2f} punti attesi di modificatore per giornata-tipo** nel proxy corrente. Il valore è portfolio-level: cambia se cambia uno dei componenti.')

with live:
    available=pool[~pool.player.isin(sold)].copy()
    if available.empty:
        st.success('Asta completata: non risultano giocatori disponibili.')
    else:
        left,state_budget=state.slots_left(me),state.remaining(me)
        st.subheader('Giocatore chiamato')
        a,b=st.columns([2.4,1])
        called_name=a.selectbox('Cerca/seleziona',available.sort_values('independent_score_v1',ascending=False).player.tolist())
        risk=b.slider('Aggressività',0.0,1.0,.58,.05)
        called=available[available.player==called_name].iloc[0]
        rec=live_recommendation(called,pool,state,risk_tolerance=risk)
        in_plan=called_name in set(plan.squad.player) if not plan.squad.empty else False

        k1,k2,k3,k4,k5,k6=st.columns(6)
        k1.metric('MAX BID',rec['max_bid'])
        k2.metric('Clearing atteso',rec['expected_clearing'])
        k3.metric('Fair indipendente',f"{float(called.independent_fair_price):.1f}")
        k4.metric('Score',f"{float(called.independent_score_v1):.1f}")
        k5.metric('Rischio shortage',f"{rec.get('shortage_risk',0):.0%}")
        k6.metric('Nel piano?', 'SÌ' if in_plan else 'NO')
        decision=rec['decision']
        if in_plan and decision in {'TARGET','BUY_AT_MARKET'}: st.success(f'**{decision}** · è parte della rosa-obiettivo corrente.')
        elif decision=='PUSH_IF_NEEDED': st.warning('**PUSH IF NEEDED** · il rischio di perdere questa fascia è elevato; il tetto è già adattato alla stanza.')
        else: st.info(f'**{decision}** · confronta subito le alternative sotto.')

        st.subheader('Se lo perdi: sostituti immediati')
        repl=replacement_candidates(called,pool,plan,r,sold_players=sold,top_n=10)
        if repl.empty:
            st.warning('Nessun sostituto disponibile nello stesso ruolo.')
        else:
            st.caption('Replacement Fit misura quanto ogni alternativa preserva punti, budget, affidabilità e coerenza con il piano originario.')
            st.dataframe(repl,use_container_width=True,hide_index=True,height=390)

        st.divider()
        st.subheader('Registra la vendita')
        a,b,c,d=st.columns([1.2,2.0,.8,2.0])
        buyer=a.selectbox('Acquirente',names)
        bought=b.selectbox('Giocatore',available.player.tolist(),index=available.player.tolist().index(called_name) if called_name in available.player.tolist() else 0)
        price=int(c.number_input('Prezzo',r.min_bid,r.budget,r.min_bid))
        note=d.text_input('Appunto rapido',placeholder='es. aggressivo sui top A / cerca rigoristi')
        if st.button('REGISTRA E RICALCOLA PIANO',type='primary',use_container_width=True):
            brow=pool[pool.player==bought].iloc[0]
            brec=live_recommendation(brow,pool,state,risk_tolerance=risk)
            market=brow.get('market_auction_price',None)
            market=float(market) if market is not None and pd.notna(market) else None
            st.session_state.purchases.append(AuctionPurchase(
                buyer,bought,str(brow.role),float(price),float(brow.fair_price),market,float(brec['expected_clearing']),note
            ))
            st.rerun()

        st.subheader('Priorità rimaste per ruolo')
        cols=st.columns(4)
        for col,role in zip(cols,['P','D','C','A']):
            need=left.get(role,0)
            col.markdown(f'**{role} · {need} slot**')
            top=available[available.role==role].sort_values('independent_score_v1',ascending=False).head(5)
            for _,x in top.iterrows():
                marker='🎯' if x.player in set(plan.squad.player) else '·'
                col.caption(f"{marker} {x.player} · {x.independent_score_v1:.0f} · fair {x.independent_fair_price:.0f}")

with room:
    st.subheader('Situazione della stanza')
    rows=[]
    for m in names:
        sl=state.slots_left(m)
        rows.append({'Squadra':m,'Budget':state.remaining(m),'Discrezionale':state.discretionary_budget(m),'P':sl['P'],'D':sl['D'],'C':sl['C'],'A':sl['A'],
                     'Agg P':round(state.manager_aggression(m,'P'),2),'Agg D':round(state.manager_aggression(m,'D'),2),'Agg C':round(state.manager_aggression(m,'C'),2),'Agg A':round(state.manager_aggression(m,'A'),2)})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    if st.session_state.purchases:
        purch=pd.DataFrame([asdict(p) if isinstance(p,AuctionPurchase) else p for p in st.session_state.purchases])
        st.subheader('Ultime vendite')
        st.dataframe(purch.tail(30).iloc[::-1],use_container_width=True,hide_index=True)
        if st.button('↩️ Annulla ultimo acquisto'):
            st.session_state.purchases.pop(); st.rerun()
