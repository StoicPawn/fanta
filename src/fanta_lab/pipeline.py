from __future__ import annotations
import os
import pandas as pd
from .reconcile import build_master_roster, fuzzy_join
from .sources.football_data import FootballDataSource
from .sources.fantacalcio import FantacalcioPublicSource
from .sources.understat import UnderstatSource
from .sources.football_data_uk import FootballDataUKSource
from .sources.fco_history import FCOHistoricalSource
from .sources.bigballs import BigBallsSource
from .sources.fantacalcio_dev import FantacalcioDevSource
from .sources.api_football import APIFootballSource
from .sources.clubelo import ClubEloSource
from .sources.openfootball import OpenFootballItalySource, schedule_difficulty

ROLE_MAP={'Goalkeeper':'P','Defender':'D','Midfielder':'C','Offence':'A','Attacker':'A','Forward':'A'}


def _weighted_player_history(frames:list[pd.DataFrame], weights:list[float]) -> pd.DataFrame:
    if not frames:return pd.DataFrame()
    xs=[]
    for i,x in enumerate(frames):
        y=x.copy(); y['weight']=weights[min(i,len(weights)-1)]; xs.append(y)
    h=pd.concat(xs,ignore_index=True)
    num=[c for c in ['games','matches','minutes','goals','assists','shots','key_passes','xg','xa','npxg','xg_chain','xg_buildup','yellow_cards','red_cards'] if c in h]
    agg=[]
    for player,g in h.groupby('player'):
        d={'player':player,'history_seasons':int(g.get('season',g.get('source_season',pd.Series(dtype=str))).nunique())}
        w=pd.to_numeric(g.weight,errors='coerce').fillna(1)
        for c in num:
            vals=pd.to_numeric(g[c],errors='coerce').fillna(0); d[c]=(vals*w).sum()/max(.001,w.sum())
        agg.append(d)
    return pd.DataFrame(agg)


def _season_label(y:int)->str:return f'{y}-{str(y+1)[2:]}'


def _merge_team_source(master:pd.DataFrame, source:pd.DataFrame, threshold:int=82)->pd.DataFrame:
    if source.empty or 'team' not in source:return master
    teams=pd.DataFrame({'player':master['team'].dropna().astype(str).unique()})
    src=source.rename(columns={'team':'player'}); joined,_=fuzzy_join(teams,src,'_teamsrc',threshold); joined=joined.rename(columns={'player':'team'})
    cols=['team']+[c for c in joined.columns if c!='team']
    return master.merge(joined[cols].drop_duplicates('team'),on='team',how='left')


def build_dataset(season_start_year:int, fanta_season_label:str, football_token:str|None=None,
                  fantasy_df:pd.DataFrame|None=None, stats_years:tuple[int,...]|None=None,
                  require_current_fanta:bool=True, bigballs_token:str|None=None,
                  api_football_token:str|None=None,
                  use_public_team_context:bool=True, use_clubelo:bool=True,
                  use_openfootball_schedule:bool=True,
                  use_fco_history:bool=True, use_fantacalcio_dev_history:bool=True,
                  use_big_five_newcomer_history:bool=True, use_api_football:bool=True):
    """Build the richest available master while keeping roster authority and enrichment distinct.

    API keys may be passed explicitly or supplied as environment variables:
    FOOTBALL_DATA_TOKEN, API_FOOTBALL_TOKEN, BIGBALLS_TOKEN.
    """
    football_token=football_token or os.getenv('FOOTBALL_DATA_TOKEN')
    api_football_token=api_football_token or os.getenv('API_FOOTBALL_TOKEN')
    bigballs_token=bigballs_token or os.getenv('BIGBALLS_TOKEN')

    roster=FootballDataSource(football_token).serie_a_squads(season_start_year); roster['role']=roster['position_raw'].map(ROLE_MAP)
    if fantasy_df is None:
        try: fantasy_df=FantacalcioPublicSource().fetch(fanta_season_label)
        except Exception:
            if require_current_fanta:raise
            fantasy_df=pd.DataFrame()
    master,report=build_master_roster(roster,fantasy_df); report.notes.append('Roster authority: football-data.org + current fantasy list reconciliation.')
    years=stats_years or (season_start_year-1,season_start_year-2,season_start_year-3)

    hist=[]
    for y in years:
        try:
            x=UnderstatSource().league_players(y); x['season']=y; hist.append(x)
        except Exception as e:report.notes.append(f'Understat {y} unavailable: {type(e).__name__}')
    if hist:
        agg=_weighted_player_history(hist,[.58,.27,.15]); master,unmatched=fuzzy_join(master,agg,'_stats',89)
        report.notes.append(f'Understat: {len(agg)} historical player aggregates; {len(unmatched)} unmatched names.')

    if use_fantacalcio_dev_history:
        try:
            dev=FantacalcioDevSource().history([_season_label(y) for y in years])
            if len(dev):
                dev['weight']=dev.dev_season.map({_season_label(years[0]):.58,_season_label(years[1]):.27,_season_label(years[2]):.15}).fillna(.1); rows=[]
                for player,g in dev.groupby('player'):
                    w=pd.to_numeric(g.weight,errors='coerce').fillna(.1); d={'player':player,'dev_history_seasons':int(g.dev_season.nunique())}
                    for c in ['dev_fantamedia','dev_avg_vote','dev_goals','dev_assists','dev_appearances']:
                        if c in g:
                            v=pd.to_numeric(g[c],errors='coerce').fillna(0); d[c]=(v*w).sum()/max(.001,w.sum())
                    rows.append(d)
                devagg=pd.DataFrame(rows); master,unmatched=fuzzy_join(master,devagg,'_dev',88); report.notes.append(f'fantacalcio.dev archive: {len(devagg)} player aggregates; {len(unmatched)} unmatched.')
                if 'dev_avg_vote' in master:
                    if 'avg_vote' not in master:master['avg_vote']=pd.NA
                    master['avg_vote']=pd.to_numeric(master['avg_vote'],errors='coerce').fillna(pd.to_numeric(master['dev_avg_vote'],errors='coerce'))
        except Exception as e:report.notes.append(f'fantacalcio.dev archive unavailable: {type(e).__name__}')

    if use_public_team_context:
        try:
            tf=FootballDataUKSource().team_features(season_start_year-1,'I1')
            if len(tf):
                master=_merge_team_source(master,tf,82); report.notes.append(f'football-data.co.uk: team context loaded for {int(master.team_attack_strength.notna().sum()) if "team_attack_strength" in master else 0} player rows.')
        except Exception as e:report.notes.append(f'football-data.co.uk unavailable: {type(e).__name__}')

    elo=pd.DataFrame()
    if use_clubelo:
        try:
            elo=ClubEloSource().italy(levels=(1,2))
            if len(elo):master=_merge_team_source(master,elo,80); report.notes.append(f'ClubElo: current Elo attached to {int(master.team_elo.notna().sum()) if "team_elo" in master else 0} player rows.')
        except Exception as e:report.notes.append(f'ClubElo unavailable: {type(e).__name__}')

    if use_openfootball_schedule:
        try:
            fixtures=OpenFootballItalySource().fixtures(season_start_year); sched=schedule_difficulty(fixtures,elo if len(elo) else None,6)
            if len(sched):
                master=_merge_team_source(master,sched,80); report.notes.append(f'OpenFootball CC0: parsed {len(fixtures)} Serie A fixtures; six-match schedule context attached.')
        except Exception as e:report.notes.append(f'OpenFootball schedule unavailable: {type(e).__name__}')

    if use_fco_history:
        try:
            prev=f'{season_start_year-1}-{season_start_year}'; fco=FCOHistoricalSource().fetch(prev)
            if len(fco):
                master,unmatched=fuzzy_join(master,fco,'_fco',88); report.notes.append(f'Fantacalcio-Online history: {len(fco)} rows; {len(unmatched)} unmatched.')
                if 'fco_avg_vote' in master:
                    if 'avg_vote' not in master:master['avg_vote']=pd.NA
                    master['avg_vote']=pd.to_numeric(master['avg_vote'],errors='coerce').fillna(pd.to_numeric(master['fco_avg_vote'],errors='coerce'))
        except Exception as e:report.notes.append(f'Fantacalcio-Online history unavailable: {type(e).__name__}')

    if api_football_token and use_api_football:
        try:
            af=APIFootballSource(api_football_token); prev_players=af.players(season_start_year-1)
            if len(prev_players):
                master,unmatched=fuzzy_join(master,prev_players,'_af',90); report.notes.append(f'API-Football previous-season stats: {len(prev_players)} rows; {len(unmatched)} unmatched.')
                fills={'minutes':'af_minutes','goals':'af_goals','assists':'af_assists','shots':'af_shots','key_passes':'af_key_passes','yellow_cards':'af_yellow','red_cards':'af_red'}
                for dst,src in fills.items():
                    if src in master:
                        if dst not in master:master[dst]=pd.NA
                        master[dst]=pd.to_numeric(master[dst],errors='coerce').fillna(pd.to_numeric(master[src],errors='coerce'))
                if 'af_rating' in master:
                    if 'avg_vote' not in master:master['avg_vote']=pd.NA
                    master['avg_vote']=pd.to_numeric(master['avg_vote'],errors='coerce').fillna(pd.to_numeric(master['af_rating'],errors='coerce'))
                if 'af_appearances' in master and 'af_lineups' in master:
                    apps=pd.to_numeric(master.af_appearances,errors='coerce'); starts=pd.to_numeric(master.af_lineups,errors='coerce'); master['starting_probability']=(starts/apps.replace(0,pd.NA)).clip(0,1); master['starting_probability_source']='api-football previous-season lineup share'
                if 'af_penalties_missed' in master:master['penalties_missed']=pd.to_numeric(master['af_penalties_missed'],errors='coerce')
            try:
                current=af.serie_a(season_start_year); cov=current.get('coverage',{}); enabled=bool(cov.get('injuries',False)) if isinstance(cov,dict) else False
                if enabled:
                    inj=af.injuries(season_start_year,int(current['id']))
                    if len(inj):master,unmatched=fuzzy_join(master,inj,'_injury',92); report.notes.append(f'API-Football current injuries/suspensions: {len(inj)} rows; {len(unmatched)} unmatched.')
                else:report.notes.append('API-Football current injury coverage flag false/not started.')
            except Exception as e:report.notes.append(f'API-Football current injuries unavailable: {type(e).__name__}')
        except Exception as e:report.notes.append(f'API-Football enrichment unavailable: {type(e).__name__}')
    elif use_api_football:report.notes.append('API-Football skipped: no API_FOOTBALL_TOKEN configured.')

    if bigballs_token and use_big_five_newcomer_history:
        try:
            bb=BigBallsSource(bigballs_token); bbh=bb.big_five_history(list(years),limit=1000)
            if len(bbh):
                bbh['weight']=bbh['source_season'].astype(str).map({str(years[0]):.58,str(years[1]):.27,str(years[2]):.15}).fillna(.12); nums=[c for c in ['matches','minutes','goals','assists','shots','key_passes','xg','xa','npxg','xg_chain','xg_buildup'] if c in bbh]; rows=[]
                for player,g in bbh.groupby('player'):
                    d={'player':player,'external_history_leagues':int(g.source_league.nunique()),'external_history_seasons':int(g.source_season.nunique())}; w=pd.to_numeric(g.weight,errors='coerce').fillna(.1)
                    for c in nums:
                        v=pd.to_numeric(g[c],errors='coerce').fillna(0); d['external_'+c]=(v*w).sum()/max(.001,w.sum())
                    rows.append(d)
                ext=pd.DataFrame(rows); master,unmatched=fuzzy_join(master,ext,'_bigfive',90); report.notes.append(f'BigBalls big-five history: {len(ext)} player aggregates; {len(unmatched)} unmatched.')
        except Exception as e:report.notes.append(f'BigBalls enrichment unavailable: {type(e).__name__}')
    elif use_big_five_newcomer_history:report.notes.append('BigBalls skipped: no BIGBALLS_TOKEN configured.')

    master['has_market_data']=master.get('fvm_1000',pd.Series(index=master.index,dtype=float)).notna(); master['has_history']=pd.to_numeric(master.get('minutes',0),errors='coerce').fillna(0).gt(0) if 'minutes' in master else False
    master['has_external_history']=pd.to_numeric(master.get('external_minutes',0),errors='coerce').fillna(0).gt(0) if 'external_minutes' in master else False; master['has_team_context']=master.get('team_attack_strength',pd.Series(index=master.index,dtype=float)).notna(); master['has_clubelo']=master.get('team_elo',pd.Series(index=master.index,dtype=float)).notna(); master['has_schedule_context']=master.get('schedule_ease_factor',pd.Series(index=master.index,dtype=float)).notna()
    fantasy_vote_col=master.get('dev_avg_vote',master.get('fco_avg_vote',pd.Series(index=master.index,dtype=float))); master['has_fantasy_history']=pd.to_numeric(fantasy_vote_col,errors='coerce').notna(); master['has_api_football']=master.get('api_football_player_id',pd.Series(index=master.index,dtype=float)).notna(); master['has_current_injury_fact']=master.get('injury_reason',pd.Series(index=master.index,dtype=object)).notna()
    master['data_confidence']=(.14+.20*master['has_market_data'].astype(float)+.17*master['has_history'].astype(float)+.10*master['has_external_history'].astype(float)+.08*master['has_team_context'].astype(float)+.05*master['has_clubelo'].astype(float)+.03*master['has_schedule_context'].astype(float)+.10*master['has_fantasy_history'].astype(float)+.10*master['has_api_football'].astype(float)+.03*master['has_current_injury_fact'].astype(float)).clip(0,1)
    return master,report
