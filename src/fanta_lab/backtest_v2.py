from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import _spearman, _top_fraction_overlap, _ndcg, run_backtest, season_slug
from .models import LeagueRules


ALPHA_GRID = np.round(np.linspace(0.0, 1.0, 21), 2)
ROLES = ('P','D','C','A')


def _role_standardize(frame: pd.DataFrame, col: str) -> pd.Series:
    x = pd.to_numeric(frame[col], errors='coerce')
    mean = x.groupby(frame['role']).transform('mean')
    std = x.groupby(frame['role']).transform('std').replace(0, np.nan)
    return ((x-mean)/std).fillna(0.0)


def apply_blend(frame: pd.DataFrame, alphas: dict[str,float]) -> pd.Series:
    """Blend model and prior-season persistence on a role-standardized scale."""
    m = _role_standardize(frame, 'independent_points')
    p = _role_standardize(frame, 'prior_total_proxy')
    a = frame['role'].map(alphas).fillna(float(np.mean(list(alphas.values())) if alphas else .5))
    return a*m + (1-a)*p


def _objective(frame: pd.DataFrame, pred: pd.Series) -> float:
    tmp=frame.copy(); tmp['_pred']=pred
    sp=_spearman(tmp['_pred'],tmp['actual_total_proxy'])
    top=_top_fraction_overlap(tmp,'_pred','actual_total_proxy')
    nd=_ndcg(tmp,'_pred','actual_total_proxy')
    vals=[v for v in [sp,top,nd] if pd.notna(v)]
    if not vals:return -1e9
    # Ranking is primary; top-end identification and NDCG regularise it.
    return .60*(sp if pd.notna(sp) else 0)+.20*(top if pd.notna(top) else 0)+.20*(nd if pd.notna(nd) else 0)


def fit_alphas(training_frames: list[pd.DataFrame]) -> dict[str,float]:
    if not training_frames:
        return {r:.5 for r in ROLES}
    train=pd.concat(training_frames,ignore_index=True)
    alphas={}
    for role in ROLES:
        g=train[train.role.eq(role)].copy()
        if len(g)<60:
            alphas[role]=.5; continue
        best=(None,-1e9)
        for alpha in ALPHA_GRID:
            score=_objective(g,apply_blend(g,{role:float(alpha)}))
            # Conservative tie-break: prefer more persistence when indistinguishable.
            if score>best[1]+1e-9 or (abs(score-best[1])<=1e-9 and (best[0] is None or alpha<best[0])):
                best=(float(alpha),score)
        alphas[role]=best[0]
    return alphas


@dataclass
class WalkForwardResult:
    prior_season:str
    target_season:str
    training_folds:int
    evaluated_players:int
    v1_spearman:float
    persistence_spearman:float
    v2_spearman:float
    v2_lift_vs_v1:float
    v2_lift_vs_persistence:float
    v1_top20:float
    persistence_top20:float
    v2_top20:float
    v2_ndcg50:float
    persistence_ndcg50:float
    is_final_holdout:bool
    alpha_p:float
    alpha_d:float
    alpha_c:float
    alpha_a:float


def build_fold(prior_year:int,rules:LeagueRules|None=None)->pd.DataFrame:
    _,details,_=run_backtest(prior_year,rules or LeagueRules())
    keep=['player','role','independent_points','prior_total_proxy','actual_total_proxy']
    return details[[c for c in keep if c in details]].dropna(subset=['role','actual_total_proxy']).copy()


def run_walkforward(start_prior_year:int=2019, final_prior_year:int=2024, min_training_folds:int=2, rules:LeagueRules|None=None):
    rules=rules or LeagueRules()
    cache={year:build_fold(year,rules) for year in range(start_prior_year,final_prior_year+1)}
    rows=[]; detail_out={}
    for test_year in range(start_prior_year+min_training_folds,final_prior_year+1):
        train_years=list(range(start_prior_year,test_year))
        alphas=fit_alphas([cache[y] for y in train_years])
        test=cache[test_year].copy(); test['v2_score']=apply_blend(test,alphas)
        v1=_spearman(test.independent_points,test.actual_total_proxy)
        pers=_spearman(test.prior_total_proxy,test.actual_total_proxy)
        v2=_spearman(test.v2_score,test.actual_total_proxy)
        r=WalkForwardResult(
            prior_season=season_slug(test_year),target_season=season_slug(test_year+1),training_folds=len(train_years),evaluated_players=len(test),
            v1_spearman=v1,persistence_spearman=pers,v2_spearman=v2,
            v2_lift_vs_v1=v2-v1,v2_lift_vs_persistence=v2-pers,
            v1_top20=_top_fraction_overlap(test,'independent_points','actual_total_proxy'),
            persistence_top20=_top_fraction_overlap(test,'prior_total_proxy','actual_total_proxy'),
            v2_top20=_top_fraction_overlap(test,'v2_score','actual_total_proxy'),
            v2_ndcg50=_ndcg(test,'v2_score','actual_total_proxy'),
            persistence_ndcg50=_ndcg(test,'prior_total_proxy','actual_total_proxy'),
            is_final_holdout=test_year==final_prior_year,
            alpha_p=alphas['P'],alpha_d=alphas['D'],alpha_c=alphas['C'],alpha_a=alphas['A'],
        )
        rows.append(asdict(r)); detail_out[test_year]=test
    return pd.DataFrame(rows),detail_out


def write_walkforward(out_dir:str|Path='artifacts/walkforward-v2', **kwargs)->pd.DataFrame:
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    summary,details=run_walkforward(**kwargs)
    summary.to_csv(out/'summary_v2.csv',index=False)
    for year,df in details.items():df.to_csv(out/f'players_{year}.csv',index=False)
    final=summary[summary.is_final_holdout]
    payload={'method':'nested walk-forward role-wise blend; 2025/26 final holdout','alpha_grid':ALPHA_GRID.tolist(),'rows':summary.to_dict('records')}
    (out/'metadata_v2.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# V2 nested walk-forward backtest','', 'The final 2025/26 fold is never used to choose blend weights.','']
    if len(final):
        f=final.iloc[0]
        lines += [f"Final holdout V2 Spearman: **{f.v2_spearman:.3f}**",f"Persistence: **{f.persistence_spearman:.3f}**",f"Lift vs persistence: **{f.v2_lift_vs_persistence:+.3f}**",f"Lift vs V1: **{f.v2_lift_vs_v1:+.3f}**",'']
    lines += [summary.to_markdown(index=False)]
    (out/'report_v2.md').write_text('\n'.join(lines),encoding='utf-8')
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--out-dir',default='artifacts/walkforward-v2'); args=p.parse_args(argv)
    df=write_walkforward(args.out_dir); print(df.to_string(index=False)); return 0


if __name__=='__main__':
    raise SystemExit(main())
