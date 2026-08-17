from __future__ import annotations
import os
import pandas as pd
from .reconcile import build_master_roster, fuzzy_join
from .sources.football_data import FootballDataSource
from .sources.fantacalcio import FantacalcioPublicSource
from .sources.understat import UnderstatSource
from .sources.kickest import KickestSource
from .sources.football_data_uk import FootballDataUKSource
from .sources.fco_history import FCOHistoricalSource
from .sources.bigballs import BigBallsSource
from .sources.fantacalcio_dev import FantacalcioDevSource
from .sources.api_football import APIFootballSource
from .sources.clubelo import ClubEloSource
from .sources.openfootball import OpenFootballItalySource, schedule_difficulty

ROLE_MAP={'Goalkeeper':'P','Defender':'D','Midfielder':'C','Offence':'A','Attacker':'A','Forward':'A'}

def _weighted_player_history(frames,weights):
    if not frames:return pd.DataFrame()
    xs=[]
    for i,x in enumerate(frames): y=x.copy(); y['weight']=weights[min(i,len(weights)-1)]; xs.append(y)
    h=pd.concat(xs,ignore_index=True); num=[c for c in ['games','matches','minutes','goals','assists','shots','key_passes','xg','xa','npxg','xg_chain','xg_buildup','yellow_cards','red_cards'] if c in h]; agg=[]
    for player,g in h.groupby('player'):
        d={'player':player,'history_seasons':int(g.get('season',g.get('source_season',pd.Series(dtype=str))).nunique())}; w=pd.to_numeric(g.weight,errors='coerce').fillna(1)
        for c in num: d[c]=(pd.to_numeric(g[c],errors='coerce').fillna(0)*w).sum()/max(.001,w.sum())
        agg.append(d)
    return pd.DataFrame(agg)

def _season_label(y):return f'{y}-{str(y+1)[2:]}'
def _merge_team_source(master,source,threshold=82):
    if source.empty or 'team' not in source:return master
    teams=pd.DataFrame({'player':master['team'].dropna().astype(str).unique()}); src=source.rename(columns={'team':'player'}); joined,_=fuzzy_join(teams,src,'_teamsrc',threshold); joined=joined.rename(columns={'player':'team'}); return master.merge(joined.drop_duplicates('team'),on='team',how='left')

def build_dataset(season_start_year:int,fanta_season_label:str,football_token=None,fantasy_df=None,stats_years=None,require_current_fanta=True,bigballs_token=None,api_football_token=None,use_public_team_context=True,use_clubelo=True,use_openfootball_schedule=True,use_fco_history=True,use_fantacalcio_dev_history=True,use_big_five_newcomer_history=True,use_api_football=True,use_kickest=True):
    football_token=football_token or os.getenv('FOOTBALL_DATA_TOKEN'); api_football_token=api_football_token or os.getenv('API_FOOTBALL_TOKEN'); bigballs_token=bigballs_token or os.getenv('BIGBALLS_TOKEN')
    roster=FootballDataSource(football_token).serie_a_squads(season_start_year); roster['role']=roster['position_raw'].map(ROLE_MAP)
    if fantasy_df is None:
        try: fantasy_df=FantacalcioPublicSource().fetch(fanta_season_label)
        except Exception:
            if require_current_fanta:raise
            fantasy_df=pd.DataFrame()
    master,report=build_master_roster(roster,fantasy_df); report.notes.append('Roster authority: football-data.org + current fantasy list reconciliation.'); years=stats_years or (season_start_year-1,season_start_year-2,season_start_year-3)
    hist=[]
    for y in years:
        try: x=UnderstatSource().league_players(y); x['season']=y; hist.append(x)
        except Exception as e: report.notes.append(f'Understat {y} unavailable: {type(e).__name__}')
    if hist:
        agg=_weighted_player_history(hist,[.58,.27,.15]); master,unmatched=fuzzy_join(master,agg,'_stats',89); report.notes.append(f'Understat: {len(agg)} historical aggregates; {len(unmatched)} unmatched.')
    if use_kickest:
        try:
            k=KickestSource().fetch(f'{season_start_year-1}-{season_start_year}')
            if len(k):
                master,unmatched=fuzzy_join(master,k,'_kickest',86); report.notes.append(f'Kickest public detailed stats: {len(k)} rows; {len(unmatched)} unmatched.')
                fills={'minutes':'kickest_minutes','goals':'kickest_goals','assists':'kickest_assists','shots':'kickest_shots','key_passes':'kickest_key_passes','yellow_cards':'kickest_yellow','red_cards':'kickest_red','saves':'kickest_saves','clean_sheets':'kickest_clean_sheets'}
                for dst,src in fills.items():
                    if src in master:
                        if dst not in master: master[dst]=pd.NA
                        master[dst]=pd.to_numeric(master[dst],errors='coerce').fillna(pd.to_numeric(master[src],errors='coerce'))
                if 'kickest_apps' in master and 'kickest_starts' in master:
                    a=pd.to_numeric(master.kickest_apps,errors='coerce'); s=pd.to_numeric(master.kickest_starts,errors='coerce'); master['starting_probability_kickest']=(s/a.replace(0,pd.NA)).clip(0,1)
        except Exception as e: report.notes.append(f'Kickest unavailable: {type(e).__name__}')
    if use_fantacalcio_dev_history:
        try:
            dev=FantacalcioDevSource().history([_season_label(y) for y in years])
            if len(dev):
                dev['weight']=dev.dev_season.map({_season_label(years[0]):.58,_season_label(years[1]):.27,_season_label(years[2]):.15}).fillna(.1); rows=[]
                for player,g in dev.groupby('player'):
                    w=pd.to_numeric(g.weight,errors='coerce').fillna(.1); d={'player':player,'dev_history_seasons':int(g.dev_season.nunique())}
                    for c in ['dev_fantamedia','dev_avg_vote','dev_goals','dev_assists','dev_appearances']:
                        if c in g: d[c]=(pd.to_numeric(g[c],errors='coerce').fillna(0)*w).sum()/max(.001,w.sum())
                    rows.append(d)
                master,unmatched=fuzzy_join(master,pd.DataFrame(rows),'_dev',88); report.notes.append(f'fantacalcio.dev: {len(rows)} aggregates; {len(unmatched)} unmatched.')
                if 'dev_avg_vote' in master:
                    if 'avg_vote' not in master:master['avg_vote']=pd.NA
                    master['avg_vote']=pd.to_numeric(master.avg_vote,errors='coerce').fillna(pd.to_numeric(master.dev_avg_vote,errors='coerce'))
        except Exception as e:report.notes.append(f'fantacalcio.dev unavailable: {type(e).__name__}')
    if use_public_team_context:
        try:
            tf=FootballDataUKSource().team_features(season_start_year-1,'I1')
            if len(tf): master=_merge_team_source(master,tf); report.notes.append('football-data.co.uk team context loaded.')
        except Exception as e:report.notes.append(f'football-data.co.uk unavailable: {type(e).__name__}')
    elo=pd.DataFrame()
    if use_clubelo:
        try:
            elo=ClubEloSource().italy(levels=(1,2)); master=_merge_team_source(master,elo,80) if len(elo) else master
        except Exception as e:report.notes.append(f'ClubElo unavailable: {type(e).__name__}')
    if use_openfootball_schedule:
        try:
            fixtures=OpenFootballItalySource().fixtures(season_start_year); sched=schedule_difficulty(fixtures,elo if len(elo) else None,6); master=_merge_team_source(master,sched,80) if len(sched) else master
        except Exception as e:report.notes.append(f'OpenFootball unavailable: {type(e).__name__}')
    if use_fco_history:
        try:
            fco=FCOHistoricalSource().fetch(f'{season_start_year-1}-{season_start_year}'); master,unmatched=fuzzy_join(master,fco,'_fco',88) if len(fco) else (master,[])
        except Exception as e:report.notes.append(f'Fantacalcio-Online unavailable: {type(e).__name__}')
    if api_football_token and use_api_football:
        try:
            af=APIFootballSource(api_football_token); ap=af.players(season_start_year-1); master,unmatched=fuzzy_join(master,ap,'_af',90) if len(ap) else (master,[])
        except Exception as e:report.notes.append(f'API-Football unavailable: {type(e).__name__}')
    elif use_api_football: report.notes.append('API-Football skipped: no token.')
    if bigballs_token and use_big_five_newcomer_history:
        try:
            b=BigBallsSource(bigballs_token).big_five_history(list(years)); master,unmatched=fuzzy_join(master,b,'_bigfive',90) if len(b) else (master,[])
        except Exception as e:report.notes.append(f'BigBalls unavailable: {type(e).__name__}')
    elif use_big_five_newcomer_history: report.notes.append('BigBalls skipped: no token.')
    master['has_market_data']=master.get('fvm_1000',pd.Series(index=master.index,dtype=float)).notna(); master['has_history']=pd.to_numeric(master.get('minutes',0),errors='coerce').fillna(0).gt(0) if 'minutes' in master else False; master['has_kickest']=master.get('kickest_source',pd.Series(index=master.index,dtype=object)).notna(); master['has_team_context']=master.get('team_attack_strength',pd.Series(index=master.index,dtype=float)).notna(); master['has_clubelo']=master.get('team_elo',pd.Series(index=master.index,dtype=float)).notna(); master['has_schedule_context']=master.get('schedule_ease_factor',pd.Series(index=master.index,dtype=float)).notna(); master['has_fantasy_history']=master.get('dev_avg_vote',master.get('fco_avg_vote',pd.Series(index=master.index,dtype=float))).notna(); master['has_api_football']=master.get('api_football_player_id',pd.Series(index=master.index,dtype=float)).notna()
    master['data_confidence']=(.14+.20*master.has_market_data.astype(float)+.18*master.has_history.astype(float)+.14*master.has_kickest.astype(float)+.08*master.has_team_context.astype(float)+.05*master.has_clubelo.astype(float)+.03*master.has_schedule_context.astype(float)+.10*master.has_fantasy_history.astype(float)+.08*master.has_api_football.astype(float)).clip(0,1)
    return master,report
