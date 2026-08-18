from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import _ndcg, _norm_name, _spearman, _top_fraction_overlap, load_historical_outcomes, run_backtest, season_slug
from .models import LeagueRules
from .sources.understat import UnderstatSource

FEATURE_FAMILIES = ('multiseason','xg_regression','availability_trend','vote_stability')


def _z_by_role(df: pd.DataFrame, s: pd.Series) -> pd.Series:
    x=pd.to_numeric(s,errors='coerce')
    mean=x.groupby(df['role']).transform('mean')
    std=x.groupby(df['role']).transform('std').replace(0,np.nan)
    return ((x-mean)/std).fillna(0.0)


def _attach_previous_season(frame: pd.DataFrame, prior_year: int) -> pd.DataFrame:
    if prior_year <= 2017:
        return frame.copy()
    prev=load_historical_outcomes(prior_year-1).copy()
    prev['_name_key']=prev.player.map(_norm_name)
    prev=prev.rename(columns={
        'actual_fantamedia':'prev_fantamedia',
        'actual_avg_vote':'prev_avg_vote',
        'actual_appearances':'prev_appearances',
        'actual_goals':'prev_goals',
        'actual_assists':'prev_assists',
        'actual_total_proxy':'prev_total_proxy',
    })
    keep=['_name_key','prev_fantamedia','prev_avg_vote','prev_appearances','prev_goals','prev_assists','prev_total_proxy']
    prev=prev[keep].drop_duplicates('_name_key')
    out=frame.copy(); out['_name_key']=out.player.map(_norm_name)
    # Previous-season columns are renamed before the merge so the current target
    # columns (actual_*) remain untouched for evaluation.
    return out.merge(prev,on='_name_key',how='left')


def _attach_understat_diagnostics(frame: pd.DataFrame, prior_year: int) -> tuple[pd.DataFrame,bool]:
    try:
        us=UnderstatSource().league_players(prior_year)
    except Exception:
        return frame.copy(),False
    if us.empty:
        return frame.copy(),False
    u=us.copy(); u['_name_key']=u.player.map(_norm_name)
    cols=['_name_key']+[c for c in ['xg','xa','goals','assists','minutes'] if c in u]
    u=u[cols].drop_duplicates('_name_key')
    out=frame.copy()
    if '_name_key' not in out: out['_name_key']=out.player.map(_norm_name)
    out=out.merge(u,on='_name_key',how='left',suffixes=('','_us'))
    return out,True


def build_feature_frame(prior_year:int,rules:LeagueRules|None=None)->tuple[pd.DataFrame,dict]:
    metrics,details,meta=run_backtest(prior_year,rules or LeagueRules())
    df=_attach_previous_season(details.copy(),prior_year)
    df,us_ok=_attach_understat_diagnostics(df,prior_year)
    meta=dict(meta); meta['understat_v3_available']=us_ok

    cur_total=pd.to_numeric(df.get('prior_total_proxy'),errors='coerce')
    prev_total=pd.to_numeric(df.get('prev_total_proxy'),errors='coerce')
    cur_apps=pd.to_numeric(df.get('prior_appearances'),errors='coerce')
    prev_apps=pd.to_numeric(df.get('prev_appearances'),errors='coerce')
    cur_vote=pd.to_numeric(df.get('avg_vote'),errors='coerce')
    prev_vote=pd.to_numeric(df.get('prev_avg_vote'),errors='coerce')

    df['multiseason_signal']=_z_by_role(df,.72*cur_total + .28*prev_total.fillna(cur_total))
    df['availability_trend_signal']=_z_by_role(df,(cur_apps-prev_apps).fillna(0))
    df['vote_stability_signal']=_z_by_role(df,(-((cur_vote-prev_vote).abs())).fillna(0) + .35*cur_vote.fillna(6.0))

    xg=pd.to_numeric(df.get('xg'),errors='coerce')
    goals=pd.to_numeric(df.get('goals'),errors='coerce')
    xa=pd.to_numeric(df.get('xa'),errors='coerce')
    assists=pd.to_numeric(df.get('assists'),errors='coerce')
    mins=pd.to_numeric(df.get('minutes'),errors='coerce').replace(0,np.nan)
    xg_resid=((xg-goals).fillna(0) + .65*(xa-assists).fillna(0)) * (90/mins).clip(upper=.2).fillna(0)
    df['xg_regression_signal']=_z_by_role(df,xg_resid)
    return df,meta


def apply_family_score(frame:pd.DataFrame, families:tuple[str,...]) -> pd.Series:
    base=_z_by_role(frame,pd.to_numeric(frame.independent_points,errors='coerce'))
    score=base.copy()
    weights={'multiseason':.18,'xg_regression':.10,'availability_trend':.07,'vote_stability':.06}
    for fam in families:
        col=f'{fam}_signal'
        if col in frame:
            score=score+weights[fam]*pd.to_numeric(frame[col],errors='coerce').fillna(0)
    return score


def _objective(df:pd.DataFrame,pred_col:str)->float:
    sp=_spearman(df[pred_col],df.actual_total_proxy)
    top=_top_fraction_overlap(df,pred_col,'actual_total_proxy')
    nd=_ndcg(df,pred_col,'actual_total_proxy')
    return .60*sp+.20*top+.20*nd


def evaluate_candidate(df:pd.DataFrame,families:tuple[str,...])->dict:
    x=df.copy(); x['_pred']=apply_family_score(x,families)
    return {
        'spearman':_spearman(x._pred,x.actual_total_proxy),
        'top20':_top_fraction_overlap(x,'_pred','actual_total_proxy'),
        'ndcg50':_ndcg(x,'_pred','actual_total_proxy'),
        'objective':_objective(x,'_pred'),
    }


def select_families(training_frames:list[pd.DataFrame])->tuple[tuple[str,...],pd.DataFrame]:
    selected:tuple[str,...]=()
    audit=[]
    if not training_frames:return selected,pd.DataFrame()
    train=pd.concat(training_frames,ignore_index=True)
    base=evaluate_candidate(train,selected)['objective']
    remaining=list(FEATURE_FAMILIES)
    while remaining:
        trials=[]
        for fam in remaining:
            cand=selected+(fam,)
            m=evaluate_candidate(train,cand)
            trials.append((fam,m['objective'],m))
        fam,best_obj,best_metrics=max(trials,key=lambda t:t[1])
        gain=best_obj-base
        audit.append({'step':len(selected)+1,'candidate':fam,'gain':gain,'objective':best_obj,'accepted':gain>=.002})
        if gain < .002:break
        selected=selected+(fam,); remaining.remove(fam); base=best_obj
    return selected,pd.DataFrame(audit)


def run_ablation(start_prior_year:int=2019,final_prior_year:int=2024,min_training_folds:int=2,rules:LeagueRules|None=None):
    rules=rules or LeagueRules()
    cache={}; metas={}
    for y in range(start_prior_year,final_prior_year+1):
        cache[y],metas[y]=build_feature_frame(y,rules)
    rows=[]; audits={}
    for test_year in range(start_prior_year+min_training_folds,final_prior_year+1):
        train_years=list(range(start_prior_year,test_year))
        selected,audit=select_families([cache[y] for y in train_years])
        audits[test_year]=audit
        test=cache[test_year].copy(); test['_v3']=apply_family_score(test,selected)
        rows.append({
            'prior_season':season_slug(test_year),'target_season':season_slug(test_year+1),'training_folds':len(train_years),
            'evaluated_players':len(test),'selected_families':'+'.join(selected) if selected else 'none',
            'v1_spearman':_spearman(test.independent_points,test.actual_total_proxy),
            'persistence_spearman':_spearman(test.prior_total_proxy,test.actual_total_proxy),
            'v3_spearman':_spearman(test._v3,test.actual_total_proxy),
            'v3_top20':_top_fraction_overlap(test,'_v3','actual_total_proxy'),
            'v1_top20':_top_fraction_overlap(test,'independent_points','actual_total_proxy'),
            'persistence_top20':_top_fraction_overlap(test,'prior_total_proxy','actual_total_proxy'),
            'v3_ndcg50':_ndcg(test,'_v3','actual_total_proxy'),
            'persistence_ndcg50':_ndcg(test,'prior_total_proxy','actual_total_proxy'),
            'understat_available':bool(metas[test_year].get('understat_v3_available')),
            'is_final_holdout':test_year==final_prior_year,
        })
    out=pd.DataFrame(rows)
    out['v3_lift_vs_v1']=out.v3_spearman-out.v1_spearman
    out['v3_lift_vs_persistence']=out.v3_spearman-out.persistence_spearman
    return out,audits,metas


def write_ablation(out_dir:str|Path='artifacts/backtest-v3')->pd.DataFrame:
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    summary,audits,metas=run_ablation()
    summary.to_csv(out/'summary_v3.csv',index=False)
    for y,a in audits.items(): a.to_csv(out/f'ablation_{y}.csv',index=False)
    payload={'method':'greedy pre-holdout ablation; 2025/26 final holdout','feature_families':FEATURE_FAMILIES,'metas':metas}
    (out/'metadata_v3.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    final=summary[summary.is_final_holdout]
    lines=['# V3 feature ablation','', 'Families are accepted only on training folds; 2025/26 is never used for selection.','']
    if len(final):
        f=final.iloc[0]
        lines += [f"Final families: **{f.selected_families}**",f"V3 Spearman: **{f.v3_spearman:.3f}**",f"V1: **{f.v1_spearman:.3f}**",f"Persistence: **{f.persistence_spearman:.3f}**",f"Lift vs V1: **{f.v3_lift_vs_v1:+.3f}**",f"Lift vs persistence: **{f.v3_lift_vs_persistence:+.3f}**",'']
    lines += [summary.to_markdown(index=False)]
    (out/'report_v3.md').write_text('\n'.join(lines),encoding='utf-8')
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--out-dir',default='artifacts/backtest-v3'); args=p.parse_args(argv)
    df=write_ablation(args.out_dir); print(df.to_string(index=False)); return 0


if __name__=='__main__':
    raise SystemExit(main())
