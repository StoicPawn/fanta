from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fanta_lab.pipeline import build_dataset
from src.fanta_lab.sources.fantacalcio import load_user_list
from src.fanta_lab.sources.auction_market import load_real_auction_averages, attach_market_prior

st.set_page_config(page_title='Data Sources · Fanta Auction Lab',page_icon='🗄️',layout='wide')
st.title('Data Sources · massima copertura reale')
st.caption('Costruisce il master usando fonti reali gratuite/optional-free. Nessun dato mancante viene inventato: ogni layer può fallire senza corrompere il roster master.')

sources=pd.DataFrame([
    ['football-data.org','Roster corrente','Serie A teams + squads','API token gratuito','ROSTER AUTHORITY'],
    ['Fantacalcio.it','Mercato fantasy','Ruoli, quotazioni, FVM','Pubblico / file utente','MARKET'],
    ['Understat','Performance','minuti, gol, assist, xG, xA, npxG, xGChain, xGBuildup, shots, key passes','Pubblico','MODEL'],
    ['fantacalcio.dev','Storico fantasy','fantamedia, voto medio, gol, assist, presenze; archivio multi-stagione','Pubblico','MODEL/CROSS-CHECK'],
    ['football-data.co.uk','Contesto squadra','gol, tiri, tiri in porta, corner, cartellini; Serie A/Serie B storiche','CSV gratuito','TEAM MODEL'],
    ['Fantacalcio-Online','Storico/quotazioni','voti, presenze, quotazioni e statistiche pubbliche','Pubblico','CROSS-CHECK'],
    ['Fantacalcio-Online aste','Prezzi reali aggregati','prezzi medi realmente pagati per bucket partecipanti/budget','Pubblico','AUCTION PRIOR'],
    ['API-Football / API-Sports','Availability + dettaglio','infortuni/squalifiche, minuti, rating, tiri, passaggi chiave, tackle, cartellini, rigori, profilo','Free API key · 100 req/day','INJURY/DETAIL'],
    ['Big Balls Sports Data','Big-five/xG estero','xG, xA, npxG, chain, buildup, goals, assists, shots, key passes, minutes; storia fino al 2014','Free API key','NEWCOMERS'],
])
sources.columns=['Fonte','Layer','Dati','Accesso','Uso nel motore']
st.dataframe(sources,use_container_width=True,hide_index=True)

st.subheader('Costruisci master arricchito')
a,b=st.columns(2)
with a:
    football_token=st.text_input('football-data.org token',type='password',help='Necessario per il roster automatico corrente.')
    api_football_token=st.text_input('API-Football token (opzionale)',type='password',help='Infortuni/squalifiche e statistiche individuali dettagliate. Piano free 100 richieste/giorno.')
    bigballs_token=st.text_input('BigBalls token (opzionale)',type='password',help='Aggiunge storico xG big-five per nuovi arrivi e giocatori esteri.')
    season=int(st.number_input('Anno iniziale stagione',2020,2030,2026))
    label=st.text_input('Stagione Fantacalcio','2026/27')
with b:
    use_team=st.toggle('football-data.co.uk team context',True)
    use_dev=st.toggle('fantacalcio.dev multi-season archive',True)
    use_fco=st.toggle('Fantacalcio-Online cross-check',True)
    use_api=st.toggle('API-Football stats + injuries',True)
    use_big=st.toggle('BigBalls big-five newcomers',True)

list_file=st.file_uploader('Listone corrente CSV/XLSX (raccomandato per bloccare ruoli/FVM della tua piattaforma)',type=['csv','xlsx','xls'])
if st.button('COSTRUISCI DATASET MASSIMO',type='primary',use_container_width=True):
    try:
        fdf=load_user_list(list_file) if list_file else None
        master,report=build_dataset(
            season,label,football_token or None,fantasy_df=fdf,require_current_fanta=True,
            bigballs_token=bigballs_token or None,api_football_token=api_football_token or None,
            use_public_team_context=use_team,use_fco_history=use_fco,
            use_fantacalcio_dev_history=use_dev,use_api_football=use_api,
            use_big_five_newcomer_history=use_big,
        )
        st.session_state.players=master; st.session_state.coverage=report; st.session_state.pop('scored',None)
        st.success(f'{len(master)} giocatori caricati · {report.certification}')
    except Exception as e:
        st.error(str(e))

if 'players' in st.session_state and isinstance(st.session_state.players,pd.DataFrame) and not st.session_state.players.empty:
    df=st.session_state.players
    st.divider(); st.subheader('Copertura effettiva')
    metrics={
        'Giocatori':len(df),
        'Squadre':df.team.nunique() if 'team' in df else 0,
        'FVM/mercato':int(df.get('has_market_data',pd.Series(False,index=df.index)).fillna(False).sum()),
        'Storico Serie A':int(df.get('has_history',pd.Series(False,index=df.index)).fillna(False).sum()),
        'Storico estero':int(df.get('has_external_history',pd.Series(False,index=df.index)).fillna(False).sum()),
        'API-Football':int(df.get('has_api_football',pd.Series(False,index=df.index)).fillna(False).sum()),
        'Injury facts':int(df.get('has_current_injury_fact',pd.Series(False,index=df.index)).fillna(False).sum()),
        'Contesto squadra':int(df.get('has_team_context',pd.Series(False,index=df.index)).fillna(False).sum()),
        'Storico fantasy':int(df.get('has_fantasy_history',pd.Series(False,index=df.index)).fillna(False).sum()),
    }
    cols=st.columns(4)
    for i,(k,v) in enumerate(metrics.items()): cols[i%4].metric(k,v)
    rep=st.session_state.get('coverage')
    if rep:
        st.markdown('#### Log fonti / provenance')
        for note in getattr(rep,'notes',[]): st.write('• '+str(note))

    if st.button('Aggancia anche prezzi medi aste reali pubbliche'):
        try:
            market=load_real_auction_averages(); rules=st.session_state.get('rules')
            managers=int(getattr(rules,'managers',8)); budget=int(getattr(rules,'budget',500))
            st.session_state.players=attach_market_prior(df,market,managers,budget); st.session_state.pop('scored',None)
            st.success(f'Prior aste reali agganciato ({len(market)} righe sorgente).'); st.rerun()
        except Exception as e:
            st.warning(f'Fonte aste non disponibile: {e}')

    show=[c for c in ['player','team','role','quotation','fvm_1000','market_auction_price','minutes','xg','xa','dev_avg_vote','dev_fantamedia','af_minutes','af_rating','af_key_passes','currently_injured','injury_reason','external_minutes','external_xg','external_xa','team_attack_strength','team_defense_strength','data_confidence'] if c in df]
    st.dataframe(df[show].sort_values('data_confidence',ascending=False) if 'data_confidence' in show else df[show],use_container_width=True,height=600)
