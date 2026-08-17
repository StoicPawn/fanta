from __future__ import annotations
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

ROLE_MAP={'Goalkeeper':'P','Defender':'D','Midfielder':'C','Offence':'A','Attacker':'A','Forward':'A'}


def _weighted_player_history(frames:list[pd.DataFrame], weights:list[float]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame()
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
            vals=pd.to_numeric(g[c],errors='coerce').fillna(0)
            d[c]=(vals*w).sum()/max(.001,w.sum())
        agg.append(d)
    return pd.DataFrame(agg)


def _season_label(y:int)->str:
    return f'{y}-{str(y+1)[2:]}'


def build_dataset(season_start_year:int, fanta_season_label:str, football_token:str|None=None,
                  fantasy_df:pd.DataFrame|None=None, stats_years:tuple[int,...]|None=None,
                  require_current_fanta:bool=True, bigballs_token:str|None=None,
                  api_football_token:str|None=None,
                  use_public_team_context:bool=True, use_fco_history:bool=True,
                  use_fantacalcio_dev_history:bool=True,
                  use_big_five_newcomer_history:bool=True,
                  use_api_football:bool=True):
    """Build a high-coverage master while keeping roster authority and enrichments distinct."""
    roster=FootballDataSource(football_token).serie_a_squads(season_start_year)
    roster['role']=roster['position_raw'].map(ROLE_MAP)
    if fantasy_df is None:
        try: fantasy_df=FantacalcioPublicSource().fetch(fanta_season_label)
        except Exception:
            if require_current_fanta: raise
            fantasy_df=pd.DataFrame()
    master,report=build_master_roster(roster,fantasy_df)
    report.notes.append('Roster authority: football-data.org + current fantasy list reconciliation.')

    years=stats_years or (season_start_year-1,season_start_year-2,season_start_year-3)

    # 1) Serie A xG-style player history.
    hist=[]
    for y in years:
        try:
            x=UnderstatSource().league_players(y); x['season']=y; hist.append(x)
        except Exception as e:
            report.notes.append(f'Understat {y} unavailable: {type(e).__name__}')
    if hist:
        agg=_weighted_player_history(hist,[.58,.27,.15])
        master,unmatched_stats=fuzzy_join(master,agg,'_stats',89)
        report.notes.append(f'Understat: {len(agg)} historical player aggregates; {len(unmatched_stats)} unmatched names.')

    # 2) Public fantasy-vote archive.
    if use_fantacalcio_dev_history:
        try:
            dev=FantacalcioDevSource().history([_season_label(y) for y in years])
            if len(dev):
                dev['weight']=dev.dev_season.map({_season_label(years[0]):.58,_season_label(years[1]):.27,_season_label(years[2]):.15}).fillna(.1)
                rows=[]
                for player,g in dev.groupby('player'):
                    w=pd.to_numeric(g.weight,errors='coerce').fillna(.1)
                    d={'player':player,'dev_history_seasons':int(g.dev_season.nunique())}
                    for c in ['dev_fantamedia','dev_avg_vote','dev_goals','dev_assists','dev_appearances']:
                        if c in g:
                            v=pd.to_numeric(g[c],errors='coerce').fillna(0); d[c]=(v*w).sum()/max(.001,w.sum())
                    rows.append(d)
                devagg=pd.DataFrame(rows); master,unmatched_dev=fuzzy_join(master,devagg,'_dev',88)
                report.notes.append(f'fantacalcio.dev archive: {len(devagg)} player aggregates; {len(unmatched_dev)} unmatched.')
                if 'dev_avg_vote' in master:
                    if 'avg_vote' not in master: master['avg_vote']=pd.NA
                    master['avg_vote']=pd.to_numeric(master['avg_vote'],errors='coerce').fillna(pd.to_numeric(master['dev_avg_vote'],errors='coerce'))
        except Exception as e:
            report.notes.append(f'fantacalcio.dev archive unavailable: {type(e).__name__}')

    # 3) Team environment from free match CSVs.
    if use_public_team_context:
        try:
            tf=FootballDataUKSource().team_features(season_start_year-1,'I1')
            if len(tf):
                teams=pd.DataFrame({'player':master['team'].dropna().astype(str).unique()})
                src=tf.rename(columns={'team':'player'})
                joined,_=fuzzy_join(teams,src,'_teamctx',82); joined=joined.rename(columns={'player':'team'})
                cols=['team']+[c for c in joined.columns if c.startswith('team_') or c.endswith('_pg')]
                master=master.merge(joined[cols].drop_duplicates('team'),on='team',how='left')
                report.notes.append(f'football-data.co.uk: team context loaded for {int(master.team_attack_strength.notna().sum()) if "team_attack_strength" in master else 0} player rows.')
        except Exception as e:
            report.notes.append(f'football-data.co.uk unavailable: {type(e).__name__}')

    # 4) Second fantasy-history source.
    if use_fco_history:
        try:
            prev=f'{season_start_year-1}-{season_start_year}'
            fco=FCOHistoricalSource().fetch(prev)
            if len(fco):
                master,unmatched_fco=fuzzy_join(master,fco,'_fco',88)
                report.notes.append(f'Fantacalcio-Online history: {len(fco)} rows; {len(unmatched_fco)} unmatched.')
                if 'fco_avg_vote' in master:
                    if 'avg_vote' not in master: master['avg_vote']=pd.NA
                    master['avg_vote']=pd.to_numeric(master['avg_vote'],errors='coerce').fillna(pd.to_numeric(master['fco_avg_vote'],errors='coerce'))
        except Exception as e:
            report.notes.append(f'Fantacalcio-Online history unavailable: {type(e).__name__}')

    # 5) API-Football: detailed previous-season stats + current injury/suspension feed.
    if api_football_token and use_api_football:
        try:
            af=APIFootballSource(api_football_token)
            prev_players=af.players(season_start_year-1)
            if len(prev_players):
                master,unmatched_af=fuzzy_join(master,prev_players,'_af',90)
                report.notes.append(f'API-Football previous-season stats: {len(prev_players)} rows; {len(unmatched_af)} unmatched.')
                # Fill gaps only; Understat / fantasy vote layers keep priority where already present.
                fills={'minutes':'af_minutes','goals':'af_goals','assists':'af_assists','shots':'af_shots','key_passes':'af_key_passes','yellow_cards':'af_yellow','red_cards':'af_red'}
                for dst,src in fills.items():
                    if src in master:
                        if dst not in master: master[dst]=pd.NA
                        master[dst]=pd.to_numeric(master[dst],errors='coerce').fillna(pd.to_numeric(master[src],errors='coerce'))
                if 'af_rating' in master:
                    if 'avg_vote' not in master: master['avg_vote']=pd.NA
                    master['avg_vote']=pd.to_numeric(master['avg_vote'],errors='coerce').fillna(pd.to_numeric(master['af_rating'],errors='coerce'))
                # Goalkeeper / penalty factual fields where the API provides them.
                if 'af_penalties_missed' in master: master['penalties_missed']=pd.to_numeric(master['af_penalties_missed'],errors='coerce')
                if 'af_penalties_saved' in master: master['penalties_saved_api']=pd.to_numeric(master['af_penalties_saved'],errors='coerce')
            try:
                current=af.serie_a(season_start_year)
                cov=current.get('coverage',{})
                injuries_enabled=bool(cov.get('injuries',False)) if isinstance(cov,dict) else False
                if injuries_enabled:
                    inj=af.injuries(season_start_year,int(current['id']))
                    if len(inj):
                        master,unmatched_inj=fuzzy_join(master,inj,'_injury',92)
                        report.notes.append(f'API-Football current injuries/suspensions: {len(inj)} rows; {len(unmatched_inj)} unmatched.')
                else:
                    report.notes.append('API-Football current injury coverage flag is false/not started; no injury facts injected.')
            except Exception as e:
                report.notes.append(f'API-Football current injuries unavailable: {type(e).__name__}')
        except Exception as e:
            report.notes.append(f'API-Football enrichment unavailable: {type(e).__name__}')

    # 6) Big-five historical xG: especially valuable for arrivals from abroad.
    if bigballs_token and use_big_five_newcomer_history:
        try:
            bb=BigBallsSource(bigballs_token); bbh=bb.big_five_history(list(years),limit=1000)
            if len(bbh):
                bbh['weight']=bbh['source_season'].astype(str).map({str(years[0]):.58,str(years[1]):.27,str(years[2]):.15}).fillna(.12)
                nums=[c for c in ['matches','minutes','goals','assists','shots','key_passes','xg','xa','npxg','xg_chain','xg_buildup'] if c in bbh]
                rows=[]
                for player,g in bbh.groupby('player'):
                    d={'player':player,'external_history_leagues':int(g.source_league.nunique()),'external_history_seasons':int(g.source_season.nunique())}
                    w=pd.to_numeric(g.weight,errors='coerce').fillna(.1)
                    for c in nums:
                        v=pd.to_numeric(g[c],errors='coerce').fillna(0); d['external_'+c]=(v*w).sum()/max(.001,w.sum())
                    rows.append(d)
                ext=pd.DataFrame(rows); master,unmatched_ext=fuzzy_join(master,ext,'_bigfive',90)
                report.notes.append(f'BigBalls big-five history: {len(ext)} player aggregates; {len(unmatched_ext)} unmatched.')
        except Exception as e:
            report.notes.append(f'BigBalls enrichment unavailable: {type(e).__name__}')

    # Derived evidence flags and confidence.
    master['has_market_data']=master.get('fvm_1000',pd.Series(index=master.index,dtype=float)).notna()
    master['has_history']=pd.to_numeric(master.get('minutes',0),errors='coerce').fillna(0).gt(0) if 'minutes' in master else False
    master['has_external_history']=pd.to_numeric(master.get('external_minutes',0),errors='coerce').fillna(0).gt(0) if 'external_minutes' in master else False
    master['has_team_context']=master.get('team_attack_strength',pd.Series(index=master.index,dtype=float)).notna()
    fantasy_vote_col=master.get('dev_avg_vote',master.get('fco_avg_vote',pd.Series(index=master.index,dtype=float)))
    master['has_fantasy_history']=pd.to_numeric(fantasy_vote_col,errors='coerce').notna()
    master['has_api_football']=master.get('api_football_player_id',pd.Series(index=master.index,dtype=float)).notna()
    master['has_current_injury_fact']=master.get('injury_reason',pd.Series(index=master.index,dtype=object)).notna()
    master['data_confidence']=(.18+.22*master['has_market_data'].astype(float)+.18*master['has_history'].astype(float)
        +.10*master['has_external_history'].astype(float)+.09*master['has_team_context'].astype(float)
        +.10*master['has_fantasy_history'].astype(float)+.10*master['has_api_football'].astype(float)
        +.03*master['has_current_injury_fact'].astype(float)).clip(0,1)
    return master,report
