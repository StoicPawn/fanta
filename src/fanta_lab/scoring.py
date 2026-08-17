import numpy as np
import pandas as pd

def add_scores(df: pd.DataFrame) -> pd.DataFrame:
    x=df.copy()
    for c in ['minutes','goals','assists','starts','appearances','clean_sheets','yellow_cards','red_cards']:
        if c not in x: x[c]=0
        x[c]=pd.to_numeric(x[c], errors='coerce').fillna(0)
    mins=np.maximum(x.minutes,1)
    per90=90/mins
    x['g90']=x.goals*per90; x['a90']=x.assists*per90
    role=x.get('role', pd.Series('M', index=x.index)).astype(str).str.upper()
    base=(0.32*np.log1p(x.minutes)+2.8*x.g90+2.0*x.a90+0.10*x.starts-0.08*x.yellow_cards-0.35*x.red_cards)
    bonus=np.where(role.eq('P'),0.25*x.clean_sheets, np.where(role.eq('D'),0.16*x.clean_sheets,0))
    raw=base+bonus
    lo,hi=np.nanpercentile(raw,[5,95]) if len(raw)>3 else (raw.min(),raw.max())
    x['fanta_score']=np.clip((raw-lo)/(hi-lo+1e-9)*100,0,100).round(1)
    x['reliability']=np.clip(np.log1p(x.minutes)/np.log(3001)*100,0,100).round(0)
    return x
