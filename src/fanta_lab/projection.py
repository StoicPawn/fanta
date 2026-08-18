from __future__ import annotations
import numpy as np
import pandas as pd
from .models import LeagueRules

ROLE_GOAL_FIELD={'P':'goal_gk','D':'goal_def','C':'goal_mid','A':'goal_fwd'}

def _num(row,col,default=0.0):
    try:
        x=float(row.get(col,default)); return default if np.isnan(x) else x
    except Exception:return default

def safe_rate(row,col,minutes_col='minutes'):
    m=max(_num(row,minutes_col),90.0); return _num(row,col)*90.0/m

def _external_rate(row,col):
    m=_num(row,'external_minutes',0); return _num(row,'external_'+col,0)*90/max(90,m) if m>0 else np.nan

def estimate_minutes(row:pd.Series)->tuple[float,float,str]:
    """Estimate season minutes without fantasy-market information.

    FVM/quotation are intentionally excluded.  The independent model can use observed
    football history, foreign history, explicit starting probability and availability;
    when none exist it falls back to a conservative role prior with low confidence.
    """
    if pd.notna(row.get('projected_minutes',np.nan)):
        pm=float(row['projected_minutes']); return float(np.clip(pm,0,3420)),.95,'manual'
    hist=_num(row,'minutes'); ext=_num(row,'external_minutes'); start_prob=_num(row,'starting_probability',np.nan)
    explicit_injury=row.get('injury_risk',np.nan)
    if pd.notna(explicit_injury):injury_risk=float(np.clip(_num(row,'injury_risk',0),0,.95)); injury_src='injury_risk'
    elif bool(row.get('currently_injured',False)):injury_risk=.45; injury_src='current_injury_flag'
    else:injury_risk=0.0; injury_src=''
    availability=float(np.clip(1-injury_risk,.35,1))
    if hist>0:
        prior=np.clip(hist*.94,450,3200)
        if not np.isnan(start_prob):prior=.65*prior+.35*(3420*np.clip(start_prob,0,1))
        prior*=availability; conf=min(.92,.45+hist/5000)
        src='history'
        if not np.isnan(start_prob):src+='+starting_probability'
        if injury_src:src+='+'+injury_src
        return float(prior),float(conf),src
    if ext>0:
        league_factor=float(np.clip(_num(row,'external_league_factor',.88),.55,1.15)); prior=np.clip(ext*.92*league_factor,350,3000)*availability
        if not np.isnan(start_prob):prior=.60*prior+.40*(3420*np.clip(start_prob,0,1))
        return float(prior),float(min(.72,.35+ext/6500)),'external_history'+('+'+injury_src if injury_src else '')
    role=str(row.get('role','C')).upper()
    role_prior={'P':1650.0,'D':1450.0,'C':1450.0,'A':1350.0}.get(role,1400.0)
    pm=role_prior*availability
    if not np.isnan(start_prob):
        pm=.35*pm+.65*(3420*np.clip(start_prob,0,1))*availability
        conf=.38
        src='starting_probability_prior'
    else:
        conf=.22
        src='role_prior_no_history'
    if injury_src:src+='+'+injury_src
    return float(np.clip(pm,250,2850)),conf,src

def project_player(row:pd.Series,rules:LeagueRules)->dict:
    role=str(row.get('role','C')).upper(); pm,min_conf,min_src=estimate_minutes(row); apps90=pm/90; hist=_num(row,'minutes'); ext=_num(row,'external_minutes')
    goals90,assists90=safe_rate(row,'goals'),safe_rate(row,'assists'); xg90,xa90=safe_rate(row,'xg'),safe_rate(row,'xa')
    if hist<=0 and ext>0:
        league_factor=float(np.clip(_num(row,'external_league_factor',.88),.55,1.15)); eg=_external_rate(row,'goals'); ea=_external_rate(row,'assists'); exg=_external_rate(row,'xg'); exa=_external_rate(row,'xa')
        goals90=(0 if np.isnan(eg) else eg)*league_factor; assists90=(0 if np.isnan(ea) else ea)*league_factor; xg90=(goals90 if np.isnan(exg) else exg*league_factor); xa90=(assists90 if np.isnan(exa) else exa*league_factor)
    sample=min(1,max(hist,ext*.75)/1800); realized_w=.35+.25*sample; pred_g90=realized_w*goals90+(1-realized_w)*xg90; pred_a90=realized_w*assists90+(1-realized_w)*xa90
    if hist<=0 and ext<=0:
        priors={'P':(0,0),'D':(.045,.045),'C':(.11,.11),'A':(.28,.10)}; pred_g90,pred_a90=priors.get(role,(.1,.1))
    attack_strength=float(np.clip(_num(row,'team_attack_strength',1.0),.65,1.35)); defense_strength=float(np.clip(_num(row,'team_defense_strength',1.0),.65,1.35)); elo_factor=float(np.clip(_num(row,'team_elo_factor',1.0),.72,1.38)); elo_blend=float(np.sqrt(elo_factor)); schedule=float(np.clip(_num(row,'schedule_ease_factor',1.0),.88,1.12))
    attack_strength=float(np.clip(attack_strength*elo_blend*(.6+.4*schedule),.60,1.45)); defense_strength=float(np.clip(defense_strength*elo_blend*(.7+.3*schedule),.60,1.45))
    pred_g90*=attack_strength; pred_a90*=attack_strength
    penalty_share=float(np.clip(_num(row,'penalty_share',0),0,1)); set_piece_share=float(np.clip(_num(row,'set_piece_share',0),0,1)); pred_g90+=.10*penalty_share; pred_a90+=.035*set_piece_share
    base_vote=_num(row,'avg_vote',6.0); vote_points=base_vote*apps90*rules.base_vote_weight; goal_pts=pred_g90*apps90*getattr(rules,ROLE_GOAL_FIELD.get(role,'goal_mid')); assist_pts=pred_a90*apps90*rules.assist
    card_pts=safe_rate(row,'yellow_cards')*apps90*rules.yellow+safe_rate(row,'red_cards')*apps90*rules.red; own_goal_pts=safe_rate(row,'own_goals')*apps90*rules.own_goal
    clean_prob=float(np.clip(_num(row,'clean_sheet_prob',.28)*defense_strength,.05,.65)); clean_pts=clean_prob*apps90*(rules.clean_sheet_gk if role=='P' else rules.clean_sheet_def if role=='D' else 0)
    conceded_pts=saved_pen_pts=0.0
    if role=='P':
        gc90=_num(row,'goals_conceded_per90',1.25)/defense_strength; conceded_pts=gc90*apps90*rules.goal_conceded_gk; saved_pen_pts=safe_rate(row,'penalties_faced')*apps90*np.clip(_num(row,'penalty_save_rate',.18),0,1)*rules.penalty_saved
    penalty_miss_pts=safe_rate(row,'penalties_missed')*apps90*rules.penalty_missed
    modifier=0.0
    total=vote_points+goal_pts+assist_pts+card_pts+own_goal_pts+clean_pts+conceded_pts+saved_pen_pts+penalty_miss_pts
    data_conf=_num(row,'data_confidence',.35); reliability=float(np.clip(.55*min_conf+.45*data_conf,0,1)); uncertainty=max(6.0,abs(total)*(.08+.28*(1-reliability))); p10=total-1.2816*uncertainty; p90=total+1.2816*uncertainty
    return {'projected_minutes':pm,'minutes_confidence':min_conf,'minutes_source':min_src,'pred_goal90':pred_g90,'pred_assist90':pred_a90,'independent_points':total,'projected_points_p10':p10,'projected_points_p50':total,'projected_points_p90':p90,'reliability':reliability,'modifier_marginal':modifier,'vote_points':vote_points,'bonus_points':total-vote_points,'team_context_factor':attack_strength,'team_defense_factor':defense_strength,'schedule_factor_used':schedule}

def add_projections(df:pd.DataFrame,rules:LeagueRules)->pd.DataFrame:
    rows=[project_player(r,rules) for _,r in df.iterrows()]; return pd.concat([df.reset_index(drop=True),pd.DataFrame(rows)],axis=1)

def _robust_scale(s:pd.Series):
    x=pd.to_numeric(s,errors='coerce'); lo,hi=x.quantile(.05),x.quantile(.95); return ((x-lo)/(hi-lo if hi>lo else 1)*100).clip(0,100)

def add_market_comparison(df:pd.DataFrame)->pd.DataFrame:
    out=df.copy(); out['independent_score']=out.groupby('role')['independent_points'].transform(_robust_scale)
    if 'fvm_1000' in out:
        out['market_score']=out.groupby('role')['fvm_1000'].transform(_robust_scale); out['edge_vs_market']=out['independent_score']-out['market_score']; out['edge_confidence_adjusted']=out['edge_vs_market']*out.get('reliability',1)
    return out
