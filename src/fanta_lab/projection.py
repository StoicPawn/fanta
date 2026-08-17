from __future__ import annotations
import numpy as np
import pandas as pd
from .models import LeagueRules

ROLE_GOAL_FIELD={'P':'goal_gk','D':'goal_def','C':'goal_mid','A':'goal_fwd'}

def _num(row,col,default=0.0):
    try:
        x=float(row.get(col,default)); return default if np.isnan(x) else x
    except Exception: return default

def safe_rate(row,col,minutes_col='minutes'):
    m=max(_num(row,minutes_col),90.0); return _num(row,col)*90.0/m

def estimate_minutes(row:pd.Series)->tuple[float,float,str]:
    """Transparent prior for expected minutes; no fake certainty for newcomers."""
    if pd.notna(row.get('projected_minutes',np.nan)):
        pm=float(row['projected_minutes']); return float(np.clip(pm,0,3420)),0.92,'manual'
    hist=_num(row,'minutes'); fvm=_num(row,'fvm_1000',np.nan); q=_num(row,'quotation',np.nan)
    if hist>0:
        prior=np.clip(hist*.94,450,3200); conf=min(.9,.42+hist/5000)
        # market information nudges role certainty, but never dominates history
        if not np.isnan(fvm): prior=np.clip(prior*(.92+.16*min(1,fvm/250)),300,3300)
        return float(prior),float(conf),'history+market' if not np.isnan(fvm) else 'history'
    # newcomer: cautious market-derived prior. Explicitly low-confidence.
    market=fvm if not np.isnan(fvm) else (q*8 if not np.isnan(q) else 20)
    pm=500+min(2200,max(0,market)*6.2)
    return float(np.clip(pm,350,2700)),.30,'market_prior_no_serie_a_history'

def project_player(row:pd.Series,rules:LeagueRules)->dict:
    role=str(row.get('role','C')).upper(); pm,min_conf,min_src=estimate_minutes(row); apps90=pm/90
    goals90,assists90=safe_rate(row,'goals'),safe_rate(row,'assists'); xg90,xa90=safe_rate(row,'xg'),safe_rate(row,'xa')
    hist=_num(row,'minutes'); sample=min(1,hist/1800)
    # more expected-stat shrinkage for smaller samples
    realized_w=.35+.25*sample
    pred_g90=realized_w*goals90+(1-realized_w)*xg90
    pred_a90=realized_w*assists90+(1-realized_w)*xa90
    # if no Serie A history, avoid pretending zero xG means zero ability; neutral role prior
    if hist<=0:
        priors={'P':(0.0,0.0),'D':(.045,.045),'C':(.11,.11),'A':(.28,.10)}
        pred_g90,pred_a90=priors.get(role,(.1,.1))
    base_vote=_num(row,'avg_vote',6.0); vote_component=(base_vote-6)*apps90*rules.base_vote_weight
    goal_pts=pred_g90*apps90*getattr(rules,ROLE_GOAL_FIELD.get(role,'goal_mid')); assist_pts=pred_a90*apps90*rules.assist
    card_pts=safe_rate(row,'yellow_cards')*apps90*rules.yellow+safe_rate(row,'red_cards')*apps90*rules.red
    clean_prob=_num(row,'clean_sheet_prob',.28); clean_pts=(clean_prob*apps90*rules.clean_sheet_gk if role=='P' else clean_prob*apps90*rules.clean_sheet_def if role=='D' else 0)
    modifier=0.0
    if rules.defense_modifier and role in {'P','D'}: modifier=max(0,base_vote-5.8)*apps90*.22*rules.defense_modifier_strength
    total=vote_component+goal_pts+assist_pts+card_pts+clean_pts+modifier
    data_conf=_num(row,'data_confidence',.35); reliability=float(np.clip(.55*min_conf+.45*data_conf,0,1))
    return {'projected_minutes':pm,'minutes_confidence':min_conf,'minutes_source':min_src,'pred_goal90':pred_g90,'pred_assist90':pred_a90,
            'independent_points':total,'reliability':reliability,'modifier_marginal':modifier}

def add_projections(df:pd.DataFrame,rules:LeagueRules)->pd.DataFrame:
    rows=[project_player(r,rules) for _,r in df.iterrows()]; return pd.concat([df.reset_index(drop=True),pd.DataFrame(rows)],axis=1)

def _robust_scale(s:pd.Series):
    x=pd.to_numeric(s,errors='coerce'); lo,hi=x.quantile(.05),x.quantile(.95)
    return ((x-lo)/(hi-lo if hi>lo else 1)*100).clip(0,100)

def add_market_comparison(df:pd.DataFrame)->pd.DataFrame:
    out=df.copy(); out['independent_score']=out.groupby('role')['independent_points'].transform(_robust_scale)
    if 'fvm_1000' in out:
        out['market_score']=out.groupby('role')['fvm_1000'].transform(_robust_scale)
        out['edge_vs_market']=out['independent_score']-out['market_score']
        out['edge_confidence_adjusted']=out['edge_vs_market']*out.get('reliability',1)
    return out
