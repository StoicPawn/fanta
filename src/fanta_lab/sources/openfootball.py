from __future__ import annotations
import re
import requests
import pandas as pd

class OpenFootballItalySource:
    """CC0 Serie A schedule/results source from openfootball/italy."""
    BASE='https://raw.githubusercontent.com/openfootball/italy/master'
    def __init__(self,timeout:int=30): self.timeout=timeout
    def season_text(self,start_year:int)->str:
        label=f'{start_year}-{str(start_year+1)[2:]}'
        r=requests.get(f'{self.BASE}/{label}/1-seriea.txt',timeout=self.timeout,headers={'User-Agent':'fanta-auction-lab/1.0'})
        r.raise_for_status(); return r.text
    def fixtures(self,start_year:int)->pd.DataFrame:
        text=self.season_text(start_year); rows=[]; md=None
        for line in text.splitlines():
            m=re.match(r'\s*▪\s*Matchday\s+(\d+)',line)
            if m: md=int(m.group(1)); continue
            if md is None or ' v ' not in line: continue
            # Strip optional leading clock, then split around the explicit v separator.
            s=re.sub(r'^\s*\d{1,2}:\d{2}\s+','',line).strip()
            parts=re.split(r'\s+v\s+',s,maxsplit=1)
            if len(parts)!=2: continue
            home,away=parts[0].strip(),parts[1].strip()
            if home and away: rows.append({'matchday':md,'home_team':home,'away_team':away,'source':'openfootball/italy'})
        return pd.DataFrame(rows)


def schedule_difficulty(fixtures:pd.DataFrame, team_ratings:pd.DataFrame|None=None, horizon:int=6)->pd.DataFrame:
    if fixtures.empty:return pd.DataFrame()
    ratings={}
    if team_ratings is not None and not team_ratings.empty and {'team','team_elo'}.issubset(team_ratings.columns):
        ratings=dict(zip(team_ratings.team.astype(str),pd.to_numeric(team_ratings.team_elo,errors='coerce')))
    base=float(pd.Series(list(ratings.values())).median()) if ratings else 1600.0
    teams=sorted(set(fixtures.home_team)|set(fixtures.away_team)); rows=[]
    for team in teams:
        games=fixtures[(fixtures.home_team==team)|(fixtures.away_team==team)].sort_values('matchday').head(horizon)
        opp=[]; home_n=0
        for _,g in games.iterrows():
            is_home=g.home_team==team; other=g.away_team if is_home else g.home_team
            home_n+=int(is_home); opp.append(float(ratings.get(other,base) if pd.notna(ratings.get(other,base)) else base))
        avg=sum(opp)/max(1,len(opp)); # >1 = easier schedule; bounded modestly
        rows.append({'team':team,'schedule_horizon':len(games),'schedule_opponent_elo':avg,
                     'schedule_ease_factor':max(.88,min(1.12,1+(base-avg)/2500)),
                     'schedule_home_share':home_n/max(1,len(games))})
    return pd.DataFrame(rows)
