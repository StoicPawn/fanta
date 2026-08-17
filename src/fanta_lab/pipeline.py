from __future__ import annotations
import pandas as pd
from .reconcile import build_master_roster, fuzzy_join
from .sources.football_data import FootballDataSource
from .sources.fantacalcio import FantacalcioPublicSource
from .sources.understat import UnderstatSource

ROLE_MAP={'Goalkeeper':'P','Defender':'D','Midfielder':'C','Offence':'A','Attacker':'A','Forward':'A'}

def build_dataset(season_start_year:int, fanta_season_label:str, football_token:str|None=None,
                  fantasy_df:pd.DataFrame|None=None, stats_years:tuple[int,...]|None=None,
                  require_current_fanta:bool=True):
    roster=FootballDataSource(football_token).serie_a_squads(season_start_year)
    roster['role']=roster['position_raw'].map(ROLE_MAP)
    if fantasy_df is None:
        try: fantasy_df=FantacalcioPublicSource().fetch(fanta_season_label)
        except Exception:
            if require_current_fanta: raise
            fantasy_df=pd.DataFrame()
    master,report=build_master_roster(roster,fantasy_df)
    years=stats_years or (season_start_year-1,season_start_year-2,season_start_year-3)
    hist=[]
    for i,y in enumerate(years):
        try:
            x=UnderstatSource().league_players(y); x['season']=y; x['weight']=[.58,.27,.15][min(i,2)]; hist.append(x)
        except Exception: continue
    if hist:
        h=pd.concat(hist,ignore_index=True); num=[c for c in ['games','minutes','goals','assists','shots','key_passes','xg','xa','npxg','xg_chain','xg_buildup','yellow_cards','red_cards'] if c in h]
        agg=[]
        for player,g in h.groupby('player'):
            d={'player':player,'history_seasons':int(g.season.nunique())}
            for c in num: d[c]=(g[c].fillna(0)*g.weight).sum()/g.weight.sum()
            agg.append(d)
        master,unmatched_stats=fuzzy_join(master,pd.DataFrame(agg),'_stats',89)
        report.notes.append(f'Storico non abbinato: {len(unmatched_stats)} nomi (non blocca la copertura; nuovi arrivi possono non avere storico Serie A).')
    master['has_market_data']=master.get('fvm_1000',pd.Series(index=master.index,dtype=float)).notna()
    master['has_history']=pd.to_numeric(master.get('minutes',0),errors='coerce').fillna(0).gt(0) if 'minutes' in master else False
    master['data_confidence']=0.35 + 0.35*master['has_market_data'].astype(float) + 0.30*master['has_history'].astype(float)
    return master,report
