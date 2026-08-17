from __future__ import annotations
import pandas as pd
import requests

BASE='https://raw.githubusercontent.com/statsbomb/open-data/master/data'

class StatsBombOpenSource:
    """Open event/lineup data for historical feature research and calibration only."""
    def __init__(self,timeout=30): self.timeout=timeout
    def _json(self,url):
        r=requests.get(url,timeout=self.timeout,headers={'User-Agent':'fanta-auction-lab/1.0'}); r.raise_for_status(); return r.json()
    def competitions(self): return pd.DataFrame(self._json(f'{BASE}/competitions.json'))
    def serie_a_seasons(self):
        x=self.competitions(); return x[(x.competition_name.astype(str).str.lower()=='serie a')].copy() if len(x) else x
    def matches(self,competition_id:int,season_id:int): return pd.DataFrame(self._json(f'{BASE}/matches/{competition_id}/{season_id}.json'))
    def events(self,match_id:int): return pd.DataFrame(self._json(f'{BASE}/events/{match_id}.json'))
    def lineups(self,match_id:int): return self._json(f'{BASE}/lineups/{match_id}.json')
