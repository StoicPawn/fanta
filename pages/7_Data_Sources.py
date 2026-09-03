from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fanta_lab.pipeline import build_dataset
from src.fanta_lab.sources.fantacalcio import load_user_list
from src.fanta_lab.sources.auction_market import load_real_auction_averages, attach_market_prior
from src.fanta_lab.sources.football_data import FootballDataSource
from src.fanta_lab.config import get_secret, secret_status
from src.fanta_lab.source_registry import registry_frame
from src.fanta_lab.projection import prediction_eligibility
from src.fanta_lab.independent_model import add_canonical_valuation
from src.fanta_lab.ui import apply_theme,page_header,section,common_sidebar

st.set_page_config(page_title='Data Sources · Fanta Auction Lab',page_icon='🗄️',layout='wide')
apply_theme(); common_sidebar()
page_header('Data Sources','Il Listone ufficiale Fantacalcio definisce tutto l\'universo d\'asta; ogni altra fonte può soltanto arricchirne i giocatori.','DATA INGESTION')

setup_tab, sources_tab, coverage_tab=st.tabs(['Costruisci dataset','Fonti disponibili','Copertura corrente'])

with setup_tab:
    section('Credenziali runtime','Nessuna chiave viene salvata nel repository o negli snapshot.')
    a,b,c=st.columns(3)
    with a:
        football_input=st.text_input('football-data.org token',type='password',value='',placeholder='env/secret o incolla per la sessione')
        football_token=get_secret('FOOTBALL_DATA_TOKEN',football_input); st.caption(f"Stato: {secret_status('FOOTBALL_DATA_TOKEN',football_input)}")
    with b:
        api_input=st.text_input('API-Football token · opzionale',type='password',value='')
        api_football_token=get_secret('API_FOOTBALL_TOKEN',api_input); st.caption(f"Stato: {secret_status('API_FOOTBALL_TOKEN',api_input)}")
    with c:
        big_input=st.text_input('BigBalls token · opzionale',type='password',value='')
        bigballs_token=get_secret('BIGBALLS_TOKEN',big_input); st.caption(f"Stato: {secret_status('BIGBALLS_TOKEN',big_input)}")
    if st.button('Test football-data.org',use_container_width=True):
        if not football_token: st.error('Token football-data.org non configurato.')
        else:
            try:
                result=FootballDataSource(football_token).ping(); st.success(f"Connessione OK · {result.get('competition')} ({result.get('code')})")
                if result.get('rate_limit'): st.json(result['rate_limit'])
            except Exception as e: st.error(str(e))

    section('Parametri dataset')
    a,b=st.columns(2)
    with a:
        season=int(st.number_input('Anno iniziale stagione',2020,2030,2026)); label=st.text_input('Stagione Fantacalcio','2026/27')
        list_file=st.file_uploader('Listone ufficiale corrente CSV/XLSX',type=['csv','xlsx'],help='Fonte canonica: nessun giocatore assente da questo file entrerà nel dataset. Senza file l\'app prova a leggere la versione corrente da Fantacalcio.it.')
        build_profile=st.radio('Profilo costruzione',['Rapido · Listone + stagione corrente','Completo · tutte le fonti abilitate'],horizontal=True,help='Rapido è sufficiente per provare subito l’app; Completo richiede più tempo ma aumenta qualità e copertura storica.')
    with b:
        use_team=st.toggle('football-data.co.uk · team context',True); use_elo=st.toggle('ClubElo · forza squadra',True); use_dev=st.toggle('fantacalcio.dev · storico fantasy',True); use_fco=st.toggle('Fantacalcio-Online · cross-check',True); use_api=st.toggle('API-Football · dettaglio/infortuni',True); use_big=st.toggle('BigBalls · newcomers esteri',True)
    fast=build_profile.startswith('Rapido')
    button_label='COSTRUISCI DATASET RAPIDO' if fast else 'COSTRUISCI DATASET MASSIMO'
    if st.button(button_label,type='primary',use_container_width=True):
        try:
            fdf=load_user_list(list_file) if list_file else None
            master,report=build_dataset(season,label,football_token or None,fantasy_df=fdf,require_current_fanta=True,bigballs_token=bigballs_token or None,api_football_token=api_football_token or None,use_public_team_context=use_team and not fast,use_clubelo=use_elo and not fast,use_openfootball_schedule=not fast,use_fco_history=use_fco and not fast,use_fantacalcio_dev_history=use_dev and not fast,use_api_football=use_api and not fast,use_big_five_newcomer_history=use_big and not fast,use_kickest=not fast,use_understat=not fast)
            st.session_state.players=master; st.session_state.coverage=report; st.session_state.pop('scored',None)
            (st.success if report.certified else st.warning)(f'{len(master)} giocatori caricati · {report.certification}')
        except Exception as e: st.error(str(e))

with sources_tab:
    section('Registry fonti','Solo il Listone ufficiale costruisce l\'universo del gioco; tutti gli enrichment migliorano statistiche, contesto o mercato senza aggiungere giocatori.')
    reg=registry_frame(); st.dataframe(reg,use_container_width=True,hide_index=True,column_config={'priority':st.column_config.ProgressColumn('Priorità',min_value=0,max_value=100,format='%d'),'ttl_hours':st.column_config.NumberColumn('TTL h',format='%.1f')})
    st.caption('Kickest, Understat, ClubElo, OpenFootball, football-data.co.uk e archivi fantasy pubblici non richiedono una chiave privata nel flusso base.')

with coverage_tab:
    df=st.session_state.get('players')
    if not isinstance(df,pd.DataFrame) or df.empty:
        st.info('Costruisci prima il dataset per vedere la copertura reale.')
    else:
        prediction_check=df.apply(prediction_eligibility,axis=1)
        prediction_ok=prediction_check.map(lambda x:x[0])
        rules=st.session_state.get('rules')
        if rules is None:
            from src.fanta_lab.models import LeagueRules
            rules=LeagueRules()
        display_df=add_canonical_valuation(df,rules)
        display_df['prediction_status']=prediction_ok.map({True:'DISPONIBILE',False:'NON DISPONIBILE'})
        display_df['prediction_reason']=prediction_check.map(lambda x:x[1])
        display_df['prediction_confidence']=prediction_check.map(lambda x:'BASSA' if x[0] and str(x[1]).startswith('Copertura minima') else 'DA CALCOLARE' if x[0] else 'NON DISPONIBILE')
        metrics={
            'Giocatori':len(df),'Squadre':df.team.nunique() if 'team' in df else 0,
            'Con predizione':int(prediction_ok.sum()),'Dati insufficienti':int((~prediction_ok).sum()),
            'FVM/mercato':int(df.get('has_market_data',pd.Series(False,index=df.index)).fillna(False).sum()),
            'Storico Serie A':int(df.get('has_history',pd.Series(False,index=df.index)).fillna(False).sum()),
            'Stagione corrente':int(df.get('has_current_fantasy_stats',pd.Series(False,index=df.index)).fillna(False).sum()),
            'Storico estero':int(df.get('has_external_history',pd.Series(False,index=df.index)).fillna(False).sum()),
            'API-Football':int(df.get('has_api_football',pd.Series(False,index=df.index)).fillna(False).sum()),
            'Injury facts':int(df.get('has_current_injury_fact',pd.Series(False,index=df.index)).fillna(False).sum()),
            'Team context':int(df.get('has_team_context',pd.Series(False,index=df.index)).fillna(False).sum()),
            'ClubElo':int(df.get('has_clubelo',pd.Series(False,index=df.index)).fillna(False).sum()),
            'Storico fantasy':int(df.get('has_fantasy_history',pd.Series(False,index=df.index)).fillna(False).sum()),
        }
        cols=st.columns(5)
        for i,(k,v) in enumerate(metrics.items()): cols[i%5].metric(k,v)
        rep=st.session_state.get('coverage')
        if rep:
            (st.success if rep.certified else st.warning)(f'Coverage gate: {rep.certification}')
            prediction_ready=bool(getattr(rep,'prediction_majority_ready',False))
            coverage=float(getattr(rep,'prediction_coverage',prediction_ok.mean()))
            (st.success if prediction_ready else st.warning)(f'Copertura modello indipendente: {coverage:.1%} · target minimo: maggioranza del Listone (>50%).')
            with st.expander('Provenance / log fonti'):
                for note in getattr(rep,'notes',[]): st.write('• '+str(note))
        if st.button('Aggancia prezzi medi di aste reali pubbliche',use_container_width=True):
            try:
                market=load_real_auction_averages(); rules=st.session_state.get('rules'); managers=int(getattr(rules,'managers',8)); budget=int(getattr(rules,'budget',500))
                st.session_state.players=attach_market_prior(df,market,managers,budget); st.session_state.pop('scored',None); st.success(f'Prior aste reali agganciato · {len(market)} righe sorgente'); st.rerun()
            except Exception as e: st.warning(f'Fonte aste non disponibile: {e}')
        show=[c for c in ['player','team','role','prediction_status','prediction_confidence','prediction_reason','canonical_value','canonical_value_source','quotation','fvm_1000','market_auction_price','current_appearances','current_avg_vote','current_goals','current_assists','minutes','xg','xa','dev_avg_vote','af_rating','currently_injured','external_minutes','team_attack_strength','team_defense_strength','team_elo','data_confidence'] if c in display_df]
        st.dataframe(display_df[show].sort_values('data_confidence',ascending=False) if 'data_confidence' in show else display_df[show],use_container_width=True,height=610,hide_index=True,column_config={'data_confidence':st.column_config.ProgressColumn('Confidenza dati',min_value=0,max_value=1,format='%.0%%')})
