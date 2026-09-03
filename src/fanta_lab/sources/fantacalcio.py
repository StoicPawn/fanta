from __future__ import annotations
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

URL = 'https://www.fantacalcio.it/quotazioni-fantacalcio'
STATS_URL = 'https://www.fantacalcio.it/statistiche-serie-a'


def _number(value, default=None):
    """Parse the decimal format used by the public Fantacalcio tables."""
    if value is None:
        return default
    value = str(value).strip().replace('.', '').replace(',', '.')
    parsed = pd.to_numeric(value, errors='coerce')
    return default if pd.isna(parsed) else parsed


def _cell_text(row, key):
    cell = row.select_one(f'[data-col-key="{key}"]')
    return cell.get_text(' ', strip=True) if cell else None

class FantacalcioPublicSource:
    """Public quotation/listone adapter, with mandatory season freshness validation."""
    def __init__(self, timeout:int=30): self.timeout=timeout
    def fetch(self, expected_season:str|None=None)->pd.DataFrame:
        r=requests.get(URL,timeout=self.timeout,headers={'User-Agent':'Mozilla/5.0 FantaAuctionLab/0.3'})
        r.raise_for_status(); text=r.text
        if expected_season and expected_season not in text:
            raise RuntimeError(f'Pagina non certificata per {expected_season}. Usa il file Listone corrente scaricato dal sito.')
        out=self._parse_public_rows(text)
        if len(out)<350:
            raise RuntimeError(f'Tabella quotazioni incompleta: riconosciuti soltanto {len(out)} giocatori.')
        return out

    @staticmethod
    def _parse_public_rows(text:str)->pd.DataFrame:
        """Read semantic row attributes instead of fragile visual table headers."""
        rows=[]
        for row in BeautifulSoup(text,'html.parser').select('tr.player-row'):
            player=(row.get('data-filter-keywords') or '').strip()
            if not player:
                link=row.select_one('.player-name span')
                player=link.get_text(' ',strip=True) if link else ''
            if not player:
                continue
            rows.append({
                'player':player,
                'team_fanta':_cell_text(row,'sq'),
                'role_fanta':str(row.get('data-filter-role-classic') or '').upper() or None,
                'quotation_initial':_number(_cell_text(row,'c_qi')),
                'quotation':_number(_cell_text(row,'c_qa')),
                'fvm_1000':_number(_cell_text(row,'c_fvm')),
                'source_fanta':'fantacalcio.it-public',
                'fantasy_eligible':True,
            })
        return pd.DataFrame(rows).drop_duplicates(['player','team_fanta']) if rows else pd.DataFrame()

    @staticmethod
    def normalize(df:pd.DataFrame)->pd.DataFrame:
        cols=list(map(str,df.columns)); low={c:c.lower() for c in cols}
        def find_any(parts):
            for c in cols:
                if any(p in low[c] for p in parts): return c
        pcol=find_any(['calciatore','player','nome']); tcol=find_any(['squadra',' team',' sq'])
        rcols=[c for c in cols if 'ruolo' in low[c] or low[c].strip() in {'r','rm'}]
        fcols=[c for c in cols if 'fvm' in low[c]]
        qacols=[c for c in cols if re.search(r'(^|\s)qa($|\s)',low[c])]
        qicols=[c for c in cols if re.search(r'(^|\s)qi($|\s)',low[c])]
        if not pcol: raise RuntimeError('Colonna calciatore non trovata.')
        out=pd.DataFrame({'player':df[pcol].astype(str).str.strip()})
        if tcol: out['team_fanta']=df[tcol].astype(str).str.strip()
        if rcols: out['role_fanta']=df[rcols[0]].astype(str).str.strip().str[0].str.upper()
        if qicols: out['quotation_initial']=pd.to_numeric(df[qicols[0]],errors='coerce')
        if qacols: out['quotation']=pd.to_numeric(df[qacols[0]],errors='coerce')
        elif qicols: out['quotation']=pd.to_numeric(df[qicols[0]],errors='coerce')
        if fcols: out['fvm_1000']=pd.to_numeric(df[fcols[0]],errors='coerce')
        out['source_fanta']='fantacalcio.it-public'; out['fantasy_eligible']=True
        return out[out.player.ne('nan') & out.player.ne('')].drop_duplicates(['player','team_fanta'] if 'team_fanta' in out else ['player'])


class FantacalcioCurrentStatsSource:
    """Official current-season fantasy results used as low-sample model evidence.

    The source enriches only players already present in the canonical Listone.  A
    rated appearance is useful evidence, but it remains explicitly lower-confidence
    than historical minutes and is strongly shrunk by the projection model.
    """
    def __init__(self,timeout:int=30): self.timeout=timeout

    def fetch(self,expected_season:str|None=None)->pd.DataFrame:
        r=requests.get(STATS_URL,timeout=self.timeout,headers={'User-Agent':'Mozilla/5.0 FantaAuctionLab/0.3'})
        r.raise_for_status(); text=r.text
        if expected_season and expected_season not in text:
            raise RuntimeError(f'Pagina statistiche non certificata per {expected_season}.')
        out=self._parse_public_rows(text)
        if len(out)<350:
            raise RuntimeError(f'Tabella statistiche incompleta: riconosciuti soltanto {len(out)} giocatori.')
        return out

    @staticmethod
    def _parse_public_rows(text:str)->pd.DataFrame:
        rows=[]
        for row in BeautifulSoup(text,'html.parser').select('tr.player-row'):
            player=(row.get('data-filter-keywords') or '').strip()
            if not player:
                continue
            penalties=_cell_text(row,'rig') or ''
            penalty_numbers=re.findall(r'\d+(?:[.,]\d+)?',penalties)
            scored=_number(penalty_numbers[0],0) if penalty_numbers else 0
            attempted=_number(penalty_numbers[1],scored) if len(penalty_numbers)>1 else scored
            rows.append({
                'player':player,
                'current_team':_cell_text(row,'sq'),
                'current_role':str(row.get('data-filter-role-classic') or '').upper() or None,
                'current_appearances':_number(_cell_text(row,'pg'),0),
                'current_avg_vote':_number(_cell_text(row,'mv')),
                'current_fantasy_avg':_number(_cell_text(row,'mfv')),
                'current_goals':_number(_cell_text(row,'gol'),0),
                'current_goals_conceded':_number(_cell_text(row,'gs'),0),
                'current_penalties_scored':scored,
                'current_penalties_attempted':attempted,
                'current_penalties_saved':_number(_cell_text(row,'rp'),0),
                'current_assists':_number(_cell_text(row,'ass'),0),
                'current_yellow_cards':_number(_cell_text(row,'amm'),0),
                'current_red_cards':_number(_cell_text(row,'esp'),0),
                'current_stats_source':'fantacalcio.it-current-stats',
            })
        out=pd.DataFrame(rows)
        if out.empty:
            return out
        matchdays=max(1,int(pd.to_numeric(out.current_appearances,errors='coerce').max() or 1))
        out['current_league_matchdays']=matchdays
        return out.drop_duplicates(['player','current_team'])

def load_user_list(path_or_file)->pd.DataFrame:
    name=getattr(path_or_file,'name',str(path_or_file)).lower()
    df=pd.read_excel(path_or_file) if name.endswith(('.xlsx','.xls')) else pd.read_csv(path_or_file)
    if {'player','fvm_1000'}.issubset(df.columns): return df
    return FantacalcioPublicSource.normalize(df)
