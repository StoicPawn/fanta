from __future__ import annotations
import pandas as pd
from .reconcile import build_master_roster, fuzzy_join
from .sources.football_data import FootballDataSource
from .sources.fantacalcio import FantacalcioPublicSource
from .sources.understat import UnderstatSource
from .sources.football_data_uk import FootballDataUKSource
from .sources.fco_history import FCOHistoricalSource
from .sources.bigballs import BigBallsSource

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


def build_dataset(season_start_year:int, fanta_season_label:str, football_token:str|None=None,
                  fantasy_df:pd.DataFrame|None=None, stats_years:tuple[int,...]|None=None,
                  require_current_fanta:bool=True, bigballs_token:str|None=None,
                  use_public_team_context:bool=True, use_fco_history:bool=True,
                  use_big_five_newcomer_history:bool=True):
    """Build the master with roster authority + as many free enrichments as available.

    Hard failures are limited to roster/list certification. Optional sources fail softly and
    add provenance notes. This keeps the auction usable when a third-party site changes.
    """
    roster=FootballDataSource(football_token).serie_a_squads(season_start_year)
    roster['role']=roster['position_raw'].map(ROLE_MAP)
    if fantasy_df is None:
        try: fantasy_df=FantacalcioPublicSource().fetch(fanta_season_label)
        except Exception:
            if require_current_fanta: raise
            fantasy_df=pd.DataFrame()
    master,report=build_master_roster(roster,fantasy_df)
    report.notes.append('Roster authority: football-data.org + current fantasy list reconciliation.')

    # 1) Serie A player history: Understat, three recency-weighted seasons.
    years=stats_years or (season_start_year-1,season_start_year-2,season_start_year-3)
    hist=[]
    for y in years:
        try:
            x=UnderstatSource().league_players(y); x['season']=y; hist.append(x)
        except Exception as e:
            report.notes.append(f'Understat {y} unavailable: {type(e).__name__}')
    if hist:
        agg=_weighted_player_history(hist,[.58,.27,.15])
        master,unmatched_stats=fuzzy_join(master,agg,'_stats',89)
        report.notes.append(f'Understat: {len(agg)} historical player rows aggregated; {len(unmatched_stats)} unmatched names.')

    # 2) Previous-season team environment from free match CSVs.
    if use_public_team_context:
        try:
            tf=FootballDataUKSource().team_features(season_start_year-1,'I1')
            if len(tf):
                # Team names are fewer and distinctive: fuzzy join through a temporary team frame.
                teams=pd.DataFrame({'player':master['team'].dropna().astype(str).unique()})
                src=tf.rename(columns={'team':'player'})
                joined,_=fuzzy_join(teams,src,'_teamctx',82)
                joined=joined.rename(columns={'player':'team'})
                cols=['team']+[c for c in joined.columns if c.startswith('team_') or c.endswith('_pg')]
                master=master.merge(joined[cols].drop_duplicates('team'),on='team',how='left')
                report.notes.append(f'football-data.co.uk: team context loaded for {int(master.team_attack_strength.notna().sum()) if "team_attack_strength" in master else 0} player rows.')
        except Exception as e:
            report.notes.append(f'football-data.co.uk unavailable: {type(e).__name__}')

    # 3) Public historical fantasy vote/appearance context.
    if use_fco_history:
        try:
            prev=f'{season_start_year-1}-{season_start_year}'
            fco=FCOHistoricalSource().fetch(prev)
            if len(fco):
                master,unmatched_fco=fuzzy_join(master,fco,'_fco',88)
                report.notes.append(f'Fantacalcio-Online history: {len(fco)} rows; {len(unmatched_fco)} unmatched.')
        except Exception as e:
            report.notes.append(f'Fantacalcio-Online history unavailable: {type(e).__name__}')

    # 4) Optional BigBalls big-five history: especially valuable for newcomers from abroad.
    # The provider itself documents xG history back to 2014. We only use recent years here.
    if bigballs_token and use_big_five_newcomer_history:
        try:
            bb=BigBallsSource(bigballs_token)
            bbh=bb.big_five_history(list(years),limit=1000)
            if len(bbh):
                # Aggregate by name across seasons/leagues. Prefix columns so Serie A history remains primary.
                bbh['weight']=bbh['source_season'].astype(str).map({str(years[0]):.58,str(years[1]):.27,str(years[2]):.15}).fillna(.12)
                nums=[c for c in ['matches','minutes','goals','assists','shots','key_passes','xg','xa','npxg','xg_chain','xg_buildup'] if c in bbh]
                rows=[]
                for player,g in bbh.groupby('player'):
                    d={'player':player,'external_history_leagues':int(g.source_league.nunique()),'external_history_seasons':int(g.source_season.nunique())}
                    w=pd.to_numeric(g.weight,errors='coerce').fillna(.1)
                    for c in nums:
                        v=pd.to_numeric(g[c],errors='coerce').fillna(0); d['external_'+c]=(v*w).sum()/max(.001,w.sum())
                    rows.append(d)
                ext=pd.DataFrame(rows)
                master,unmatched_ext=fuzzy_join(master,ext,'_bigfive',90)
                report.notes.append(f'BigBalls big-five history: {len(ext)} player aggregates; {len(unmatched_ext)} unmatched.')
        except Exception as e:
            report.notes.append(f'BigBalls enrichment unavailable: {type(e).__name__}')

    master['has_market_data']=master.get('fvm_1000',pd.Series(index=master.index,dtype=float)).notna()
    master['has_history']=pd.to_numeric(master.get('minutes',0),errors='coerce').fillna(0).gt(0) if 'minutes' in master else False
    master['has_external_history']=pd.to_numeric(master.get('external_minutes',0),errors='coerce').fillna(0).gt(0) if 'external_minutes' in master else False
    master['has_team_context']=master.get('team_attack_strength',pd.Series(index=master.index,dtype=float)).notna()
    master['has_fantasy_history']=master.get('fco_avg_vote',pd.Series(index=master.index,dtype=float)).notna()
    # Confidence rewards independent corroboration, capped below 1 unless multiple layers agree.
    master['data_confidence']=(
        .25 + .25*master['has_market_data'].astype(float) + .22*master['has_history'].astype(float)
        + .10*master['has_external_history'].astype(float) + .10*master['has_team_context'].astype(float)
        + .08*master['has_fantasy_history'].astype(float)
    ).clip(0,1)
    return master,report
