from __future__ import annotations
import re
from io import StringIO
import pandas as pd
import requests

URL = 'https://www.fantacalcio.it/quotazioni-fantacalcio'

class FantacalcioPublicSource:
    """Public quotation/listone adapter, with mandatory season freshness validation."""
    def __init__(self, timeout:int=30): self.timeout=timeout
    def fetch(self, expected_season:str|None=None)->pd.DataFrame:
        r=requests.get(URL,timeout=self.timeout,headers={'User-Agent':'Mozilla/5.0 FantaAuctionLab/0.3'})
        r.raise_for_status(); text=r.text
        if expected_season and expected_season not in text:
            raise RuntimeError(f'Pagina non certificata per {expected_season}. Usa il file Listone corrente scaricato dal sito.')
        tables=pd.read_html(StringIO(text)); candidates=[t for t in tables if any('FVM' in str(c) for c in t.columns)]
        if not candidates: raise RuntimeError('Tabella quotazioni non riconosciuta.')
        df=max(candidates,key=len).copy(); df.columns=[' '.join(map(str,c)).strip() if isinstance(c,tuple) else str(c).strip() for c in df.columns]
        return self.normalize(df)

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

def load_user_list(path_or_file)->pd.DataFrame:
    name=getattr(path_or_file,'name',str(path_or_file)).lower()
    df=pd.read_excel(path_or_file) if name.endswith(('.xlsx','.xls')) else pd.read_csv(path_or_file)
    if {'player','fvm_1000'}.issubset(df.columns): return df
    return FantacalcioPublicSource.normalize(df)
