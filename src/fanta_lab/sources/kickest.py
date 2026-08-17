from __future__ import annotations
import re, unicodedata
from io import StringIO
import pandas as pd
import requests

URL='https://www.kickest.it/it/serie-a/statistiche/giocatori/tabellone'

def _n(x):
    s=unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+','_',s).strip('_')

class KickestSource:
    """Public Serie A stats: apps, starts, minutes, attack, passing, defence, GK."""
    def __init__(self,timeout=30): self.timeout=timeout
    def fetch(self,season='2025-2026'):
        r=requests.get(URL,params={'season':season},timeout=self.timeout,headers={'User-Agent':'Mozilla/5.0 FantaAuctionLab/1.0'}); r.raise_for_status()
        cand=[]
        for t in pd.read_html(StringIO(r.text)):
            t=t.copy(); t.columns=[_n(c) for c in t.columns]; j=' '.join(t.columns)
            if ('giocatore' in j or 'player' in j) and ('minuti' in j or 'mins' in j): cand.append(t)
        if not cand: raise RuntimeError('Kickest player-stat table not recognised')
        t=max(cand,key=lambda x:(len(x),len(x.columns)))
        a={'giocatore':'player','player':'player','pos':'kickest_role','squadra':'kickest_team','team':'kickest_team','presenze':'kickest_apps','apps':'kickest_apps','titolare':'kickest_starts','starter':'kickest_starts','minuti':'kickest_minutes','mins':'kickest_minutes','goal':'kickest_goals','goals':'kickest_goals','tiri':'kickest_shots','shots':'kickest_shots','tiri_porta':'kickest_shots_on','on_tar_shots':'kickest_shots_on','goal_rig':'kickest_pen_goals','pen_goals':'kickest_pen_goals','ass':'kickest_assists','ast':'kickest_assists','pass_chiave':'kickest_key_passes','key_pass':'kickest_key_passes','falli':'kickest_fouls','falli_subiti':'kickest_fouled','was_fouled':'kickest_fouled','gialli':'kickest_yellow','yc':'kickest_yellow','rossi':'kickest_red','rc':'kickest_red','pall_rubati':'kickest_recoveries','rec_ball':'kickest_recoveries','tackle':'kickest_tackles','tackles':'kickest_tackles','clean_sheet':'kickest_clean_sheets','clean_sheets':'kickest_clean_sheets','parate':'kickest_saves','saves':'kickest_saves','pts':'kickest_points','cr':'kickest_credit'}
        t=t.rename(columns={c:a[c] for c in t.columns if c in a}); out=t[[c for c in dict.fromkeys(a.values()) if c in t]].copy()
        if 'player' not in out: raise RuntimeError('Kickest player column not found')
        out.player=out.player.astype(str).str.strip()
        for c in [c for c in out if c.startswith('kickest_') and c not in {'kickest_role','kickest_team'}]: out[c]=pd.to_numeric(out[c].astype(str).str.replace(',','.',regex=False),errors='coerce')
        out['kickest_season']=season; out['kickest_source']='kickest-public'
        return out[out.player.str.len().between(2,100)].drop_duplicates('player')
