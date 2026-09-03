from __future__ import annotations

from dataclasses import asdict
import pandas as pd
import streamlit as st

from src.fanta_lab.models import LeagueRules, AuctionPurchase
from src.fanta_lab.independent_model import build_independent_valuation
from src.fanta_lab.auction import AuctionState, live_recommendation
from src.fanta_lab.target_engine import build_target_plan, replacement_candidates
from src.fanta_lab.plan_health import role_spend_envelopes, plan_resilience, role_risk_summary, alternative_buckets
from src.fanta_lab.ui import apply_theme,page_header,section,common_sidebar,empty_state

st.set_page_config(page_title='Command Center · Fanta Auction Lab',page_icon='🎛️',layout='wide')
apply_theme(); common_sidebar()
page_header('Auction Command Center','La schermata da tenere aperta durante l’asta: stato della stanza, chiamata corrente, MAX BID, sostituti e aggiornamento immediato del piano.','LIVE AUCTION')

if 'rules' not in st.session_state: st.session_state.rules=LeagueRules()
if 'players' not in st.session_state: st.session_state.players=pd.DataFrame()
if 'purchases' not in st.session_state: st.session_state.purchases=[]
if 'manager_names' not in st.session_state: st.session_state.manager_names=['Io']+[f'Avversario {i}' for i in range(1,8)]
if 'my_manager' not in st.session_state: st.session_state.my_manager='Io'
if 'manager_notes' not in st.session_state: st.session_state.manager_notes={}

if st.session_state.players.empty:
    empty_state('Dataset necessario','Costruisci il master in Data Sources. Poi torna qui: il Command Center userà automaticamente regole, ranking e stato dell’asta.')
    st.stop()

r=st.session_state.rules; names=st.session_state.manager_names[:r.managers]
while len(names)<r.managers: names.append(f'Avversario {len(names)}')
if st.session_state.my_manager not in names: st.session_state.my_manager=names[0]
pool=build_independent_valuation(st.session_state.players.copy(),r); pool['fair_price']=pd.to_numeric(pool.independent_fair_price,errors='coerce'); st.session_state.scored=pool
state=AuctionState(r,names,st.session_state.my_manager)
for p in st.session_state.purchases:
    try: state.add_purchase(p if isinstance(p,AuctionPurchase) else AuctionPurchase(**p))
    except Exception: pass
me=state.my_manager; sold={p.player for p in state.purchases}; mine=[p for p in state.purchases if p.manager==me]
plan=build_target_plan(pool,r,budget=r.budget,locked=mine,sold_players=sold); resilience=plan_resilience(pool,plan,sold); role_risk=role_risk_summary(resilience,plan); envelopes=role_spend_envelopes(plan,r,state.remaining(me))

k=st.columns(7)
k[0].metric('Budget',f'{state.remaining(me):.0f}'); k[1].metric('Discrezionale',f'{state.discretionary_budget(me):.0f}'); k[2].metric('Slot',sum(state.slots_left(me).values())); k[3].metric('Inflazione',f'{state.inflation():.2f}×'); k[4].metric('Target points',f'{plan.expected_points:.0f}' if not plan.squad.empty else '—'); k[5].metric('Modifier',f'+{plan.expected_modifier_points:.1f}' if r.defense_modifier else 'OFF'); k[6].metric('Vendite',len(state.purchases))

live_tab, plan_tab, room_tab, notes_tab=st.tabs(['Chiamata LIVE','Piano e rischio','Stanza','Appunti'])
with live_tab:
    available=pool[~pool.player.isin(sold)].copy()
    if available.empty: st.success('Asta completata: nessun giocatore disponibile.')
    else:
        a,b=st.columns([3.2,1]); called_name=a.selectbox('Giocatore chiamato',available.sort_values('independent_score_v1',ascending=False).player.tolist()); risk=b.slider('Aggressività',0.,1.,.58,.05,help='Quanto accettare il rischio di pagare sopra fair quando aspettare può costare una fascia intera.')
        called=available[available.player==called_name].iloc[0]; rec=live_recommendation(called,pool,state,risk_tolerance=risk); in_plan=called_name in set(plan.squad.player) if not plan.squad.empty else False; has_prediction=bool(called.get('prediction_available',False)); canonical=called.get('canonical_value')
        x=st.columns(7)
        x[0].metric('MAX BID',rec['max_bid'] if rec['max_bid'] is not None else '—'); x[1].metric('Clearing',rec['expected_clearing'] if rec['expected_clearing'] is not None else '—'); x[2].metric('P80 stanza',rec.get('clearing_p80') if rec.get('clearing_p80') is not None else '—'); x[3].metric('Fair indip.' if has_prediction else 'Valore canonico',f"{called.independent_fair_price:.1f}" if has_prediction else f"{float(canonical):.1f}" if pd.notna(canonical) else '—',help=None if has_prediction else called.get('canonical_value_source')); x[4].metric('Score',f"{called.independent_score_v1:.1f}" if has_prediction else '—'); x[5].metric('Shortage',f"{rec.get('shortage_risk',0):.0%}" if rec.get('shortage_risk') is not None else '—'); x[6].metric('Nel piano','SÌ' if in_plan else 'NO')
        if not has_prediction:
            canonical_text=f"{float(canonical):.1f} {called.get('canonical_value_unit','')}" if pd.notna(canonical) else 'non disponibile nel Listone'
            st.warning(f"**Il modello non può fare una valutazione indipendente per {called_name}.** {called.get('prediction_reason','Dati insufficienti')}. Valutazione canonica: **{canonical_text}** ({called.get('canonical_value_source','Listone Fantacalcio')}). Puoi registrare normalmente la vendita, ma MAX BID, fair indipendente e sostituti quantitativi non vengono inventati.")
        else:
            if called.get('prediction_confidence')=='BASSA':
                st.warning(f"**Predizione a bassa confidenza.** {called.get('prediction_reason','Campione individuale limitato')}. Il MAX BID incorpora più prudenza, ma va confrontato con il valore canonico.")
            if rec['decision']=='PUSH_IF_NEEDED': st.warning('**PUSH IF NEEDED** · aspettare rischia di degradare il piano finale.')
            elif rec['decision'] in {'TARGET','BUY_AT_MARKET'}: st.success(f"**{rec['decision']}** · il prezzo è compatibile con la strategia corrente.")
            else: st.info(f"**{rec['decision']}** · valuta le alternative prima di inseguire il prezzo.")
            st.progress(min(1.0,float(rec.get('urgency',0))/1.75),text=f"Urgenza {rec.get('urgency',0):.2f} · comparabili rimasti {rec.get('better_or_equal_left','—')} · pressione fascia {rec.get('tier_pressure',1):.2f}×")

            section('Sostituti immediati','Se perdi il giocatore, il motore distingue alternative che preservano fascia, alternative value e soluzioni di emergenza affidabili.')
            repl=replacement_candidates(called,pool,plan,r,sold_players=sold,top_n=18); buckets=alternative_buckets(called,repl)
            t1,t2,t3=st.tabs(['Stessa fascia','Valore/prezzo','Emergenza'])
            for tab,key in [(t1,'same_tier'),(t2,'value'),(t3,'emergency')]:
                with tab:
                    if buckets[key].empty: st.caption('Nessuna alternativa in questa categoria.')
                    else: st.dataframe(buckets[key],use_container_width=True,hide_index=True,height=310)

        section('Registra la vendita')
        c=st.columns([1.2,2.2,.8,2.3]); buyer=c[0].selectbox('Acquirente',names); options=available.player.tolist(); bought=c[1].selectbox('Giocatore',options,index=options.index(called_name)); price=int(c[2].number_input('Prezzo',r.min_bid,r.budget,r.min_bid)); note=c[3].text_input('Nota rapida',placeholder='es. aggressivo sui top A')
        if st.button('REGISTRA · RICALCOLA TUTTO',type='primary',use_container_width=True):
            brow=pool[pool.player==bought].iloc[0]; brec=live_recommendation(brow,pool,state,risk_tolerance=risk); market=brow.get('market_auction_price',None); market=float(market) if market is not None and pd.notna(market) else None
            fair=float(brow.fair_price) if pd.notna(brow.get('fair_price')) else None; clearing=float(brec['expected_clearing']) if brec.get('expected_clearing') is not None else None
            st.session_state.purchases.append(AuctionPurchase(buyer,bought,str(brow.role),float(price),fair,market,clearing,note)); st.rerun()

with plan_tab:
    if plan.squad.empty: st.error('Nessuna rosa completa fattibile ai prezzi correnti.')
    else:
        l,rcol=st.columns([1.4,1])
        with l:
            section('Rosa obiettivo corrente')
            show=[c for c in ['player','team','role','independent_score_v1','independent_points','target_price','reliability','vorp'] if c in plan.squad]
            st.dataframe(plan.squad[show],use_container_width=True,hide_index=True,height=560,column_config={'reliability':st.column_config.ProgressColumn('Affidabilità',min_value=0,max_value=1,format='%.0%%')})
        with rcol:
            section('Budget per reparto'); st.dataframe(envelopes,use_container_width=True,hide_index=True)
            section('Rischio per ruolo')
            if not role_risk.empty:
                st.dataframe(role_risk,use_container_width=True,hide_index=True,column_config={'risk_score':st.column_config.ProgressColumn('Rischio',min_value=0,max_value=1,format='%.0%%')})
                worst=role_risk.iloc[0]
                if float(worst.risk_score)>=.55: st.warning(f"Priorità: **{worst.role}** · poche alternative equivalenti.")
            fragile=resilience[resilience.fragility=='HIGH'].head(8) if not resilience.empty else pd.DataFrame()
            if not fragile.empty:
                section('Target fragili'); st.dataframe(fragile,use_container_width=True,hide_index=True)

with room_tab:
    section('Situazione della stanza','Budget, slot e aggressività appresa per ciascun partecipante.')
    rows=[]
    for m in names:
        sl=state.slots_left(m); rows.append({'Squadra':m,'Budget':state.remaining(m),'Discrezionale':state.discretionary_budget(m),'P':sl['P'],'D':sl['D'],'C':sl['C'],'A':sl['A'],'Agg P':round(state.manager_aggression(m,'P'),2),'Agg D':round(state.manager_aggression(m,'D'),2),'Agg C':round(state.manager_aggression(m,'C'),2),'Agg A':round(state.manager_aggression(m,'A'),2)})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    if st.session_state.purchases:
        section('Ultime vendite'); purch=pd.DataFrame([asdict(p) if isinstance(p,AuctionPurchase) else p for p in st.session_state.purchases]); st.dataframe(purch.tail(35).iloc[::-1],use_container_width=True,hide_index=True)
        if st.button('↩️ Annulla ultima vendita'): st.session_state.purchases.pop(); st.rerun()

with notes_tab:
    section('Appunti sugli avversari','Le note rimangono nella sessione e possono accompagnare il modello quantitativo con segnali osservati dal vivo.')
    for m in names:
        key=f'note_{m}'; current=st.session_state.manager_notes.get(m,''); new=st.text_area(m,value=current,key=key,height=90)
        st.session_state.manager_notes[m]=new
