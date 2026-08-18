from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from .independent_model import build_independent_valuation
from .models import LeagueRules
from .sources.fantacalcio_dev import FantacalcioDevSource
from .sources.understat import UnderstatSource


def season_slug(start_year: int) -> str:
    return f"{int(start_year)}-{str(int(start_year)+1)[-2:]}"


def _norm_name(value: object) -> str:
    text=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode('ascii').lower()
    text=re.sub(r"[^a-z0-9 ]+"," ",text)
    return re.sub(r"\s+"," ",text).strip()


def _role(value: object) -> str | None:
    s=str(value or '').strip().lower()
    if not s:return None
    if s in {'p','gk'} or 'portier' in s:return 'P'
    if s in {'d','df'} or 'difensor' in s:return 'D'
    if s in {'c','m','mf'} or 'centrocamp' in s or 'midfield' in s:return 'C'
    if s in {'a','f','fw'} or 'attac' in s or 'forward' in s:return 'A'
    return None


def _coalesce(df: pd.DataFrame, *cols: str, default=np.nan) -> pd.Series:
    out=pd.Series(default,index=df.index,dtype='object')
    for c in cols:
        if c in df:
            x=df[c]
            mask=out.isna() | out.astype(str).eq('nan')
            out=out.where(~mask,x)
    return out


def _numeric(series: pd.Series, default=0.0) -> pd.Series:
    return pd.to_numeric(series,errors='coerce').fillna(default)


def _fuzzy_attach(left: pd.DataFrame, right: pd.DataFrame, threshold: int=94) -> pd.DataFrame:
    """Attach right rows to left by normalized exact names, then conservative unique fuzzy match."""
    l=left.copy(); r=right.copy()
    l['_name_key']=l.player.map(_norm_name); r['_name_key']=r.player.map(_norm_name)
    exact=l.merge(r.drop_duplicates('_name_key'),on='_name_key',how='left',suffixes=('','_target'))
    if 'player_target' not in exact:return exact
    missing=exact.player_target.isna(); choices=r['_name_key'].dropna().drop_duplicates().tolist()
    lookup=r.drop_duplicates('_name_key').set_index('_name_key')
    for idx in exact.index[missing]:
        key=exact.at[idx,'_name_key']
        if not key or not choices:continue
        match=process.extractOne(key,choices,scorer=fuzz.WRatio,score_cutoff=threshold)
        if not match:continue
        candidate,score,_=match
        # Require a unique high-quality candidate; false joins are worse than dropped rows.
        near=process.extract(key,choices,scorer=fuzz.WRatio,limit=2,score_cutoff=threshold)
        if len(near)>1 and near[0][1]-near[1][1] < 3:continue
        row=lookup.loc[candidate]
        for c in r.columns:
            if c=='_name_key':continue
            dest=c if c not in exact.columns else f'{c}_target'
            if dest in exact.columns: exact.at[idx,dest]=row[c]
        exact.at[idx,'_match_score']=score
    exact['_match_score']=exact.get('_match_score',pd.Series(np.nan,index=exact.index)).fillna(100.0)
    return exact


def load_historical_features(prior_year: int) -> tuple[pd.DataFrame, dict]:
    """Build features using ONLY the season ending before the forecast target season."""
    slug=season_slug(prior_year)
    dev=FantacalcioDevSource().season(slug)
    if dev.empty:raise RuntimeError(f'fantacalcio.dev returned no data for {slug}')
    try:
        us=UnderstatSource().league_players(prior_year)
    except Exception:
        us=pd.DataFrame()

    d=dev.copy(); d['_name_key']=d.player.map(_norm_name)
    if not us.empty:
        u=us.copy(); u['_name_key']=u.player.map(_norm_name)
        merged=d.merge(u.drop_duplicates('_name_key'),on='_name_key',how='outer',suffixes=('_dev',''))
        merged['player']=_coalesce(merged,'player','player_dev')
    else:
        merged=d.copy(); merged['player']=merged['player']

    role_source=_coalesce(merged,'dev_role','position')
    merged['role']=role_source.map(_role)
    # Historical inputs only. If Understat minutes are unavailable, use a transparent
    # appearance-to-minutes proxy rather than any market/FVM signal.
    apps=_numeric(_coalesce(merged,'dev_appearances'),0)
    minutes=_numeric(_coalesce(merged,'minutes'),np.nan)
    minutes=minutes.where(minutes.notna() & minutes.gt(0), apps*72.0)
    merged['minutes']=minutes.fillna(0)
    merged['goals']=_numeric(_coalesce(merged,'goals','dev_goals'),0)
    merged['assists']=_numeric(_coalesce(merged,'assists','dev_assists'),0)
    merged['xg']=pd.to_numeric(_coalesce(merged,'xg'),errors='coerce')
    merged['xa']=pd.to_numeric(_coalesce(merged,'xa'),errors='coerce')
    merged['avg_vote']=_numeric(_coalesce(merged,'dev_avg_vote'),6.0)
    merged['yellow_cards']=_numeric(_coalesce(merged,'yellow_cards'),0)
    merged['red_cards']=_numeric(_coalesce(merged,'red_cards'),0)
    merged['data_confidence']=(.42 + (merged.minutes.clip(0,3000)/3000)*.48).clip(.25,.90)
    merged['team_attack_strength']=1.0; merged['team_defense_strength']=1.0; merged['team_elo_factor']=1.0; merged['schedule_ease_factor']=1.0
    merged['prior_fantamedia']=_numeric(_coalesce(merged,'dev_fantamedia'),0)
    merged['prior_appearances']=apps
    merged['prior_total_proxy']=merged.prior_fantamedia*merged.prior_appearances
    keep=['player','role','minutes','goals','assists','xg','xa','avg_vote','yellow_cards','red_cards','data_confidence','team_attack_strength','team_defense_strength','team_elo_factor','schedule_ease_factor','prior_fantamedia','prior_appearances','prior_total_proxy']
    out=merged[keep].copy().dropna(subset=['player','role']).drop_duplicates('player')
    meta={'prior_season':slug,'feature_players':len(out),'understat_available':not us.empty,'dev_players':len(dev),'understat_players':len(us)}
    return out,meta


def load_historical_outcomes(target_year: int) -> pd.DataFrame:
    slug=season_slug(target_year); dev=FantacalcioDevSource().season(slug)
    if dev.empty:raise RuntimeError(f'fantacalcio.dev returned no outcomes for {slug}')
    out=dev.copy(); out['role_target']=out.get('dev_role',pd.Series(index=out.index)).map(_role)
    out['actual_fantamedia']=_numeric(out.get('dev_fantamedia',pd.Series(index=out.index)),0)
    out['actual_avg_vote']=_numeric(out.get('dev_avg_vote',pd.Series(index=out.index)),0)
    out['actual_appearances']=_numeric(out.get('dev_appearances',pd.Series(index=out.index)),0)
    out['actual_goals']=_numeric(out.get('dev_goals',pd.Series(index=out.index)),0)
    out['actual_assists']=_numeric(out.get('dev_assists',pd.Series(index=out.index)),0)
    out['actual_total_proxy']=out.actual_fantamedia*out.actual_appearances
    return out[['player','role_target','actual_fantamedia','actual_avg_vote','actual_appearances','actual_goals','actual_assists','actual_total_proxy']].drop_duplicates('player')


def _spearman(a: pd.Series,b: pd.Series) -> float:
    x=pd.to_numeric(a,errors='coerce'); y=pd.to_numeric(b,errors='coerce'); mask=x.notna() & y.notna()
    if mask.sum()<3:return float('nan')
    xr=x[mask].rank(method='average'); yr=y[mask].rank(method='average')
    return float(xr.corr(yr))


def _top_fraction_overlap(frame: pd.DataFrame,pred: str,actual: str,fraction=.20) -> float:
    vals=[]
    for _,g in frame.groupby('role'):
        if len(g)<10:continue
        k=max(1,int(math.ceil(len(g)*fraction)))
        p=set(g.nlargest(k,pred).player); a=set(g.nlargest(k,actual).player)
        vals.append(len(p&a)/k)
    return float(np.mean(vals)) if vals else float('nan')


def _ndcg(frame: pd.DataFrame,pred: str,actual: str,k=50) -> float:
    if frame.empty:return float('nan')
    d=frame.copy(); rel=d[actual].rank(pct=True).clip(0,1)
    d=d.assign(_rel=rel).sort_values(pred,ascending=False).head(k)
    gains=(2**d._rel.to_numpy()-1); discounts=np.log2(np.arange(2,len(d)+2)); dcg=float((gains/discounts).sum())
    ideal=frame.assign(_rel=rel).sort_values('_rel',ascending=False).head(k); ig=(2**ideal._rel.to_numpy()-1); idcg=float((ig/np.log2(np.arange(2,len(ideal)+2))).sum())
    return dcg/idcg if idcg>0 else float('nan')


@dataclass
class BacktestMetrics:
    prior_season:str
    target_season:str
    matched_players:int
    evaluated_players:int
    model_spearman:float
    persistence_spearman:float
    spearman_lift:float
    score_spearman:float
    top20_overlap:float
    persistence_top20_overlap:float
    top20_lift:float
    ndcg50:float
    persistence_ndcg50:float
    mae_total_proxy:float
    understat_available:bool


def run_backtest(prior_year: int,rules: LeagueRules | None=None,min_target_apps: int=5) -> tuple[BacktestMetrics,pd.DataFrame,dict]:
    rules=rules or LeagueRules()
    features,meta=load_historical_features(prior_year)
    outcomes=load_historical_outcomes(prior_year+1)
    scored=build_independent_valuation(features.copy(),rules)
    joined=_fuzzy_attach(scored,outcomes)
    # After merge, target columns keep their names unless colliding.
    if 'actual_total_proxy' not in joined:
        raise RuntimeError('historical target join did not produce actual_total_proxy')
    joined=joined[pd.to_numeric(joined.actual_appearances,errors='coerce').fillna(0)>=min_target_apps].copy()
    joined=joined[joined.actual_total_proxy.notna()].copy()
    model_sp=_spearman(joined.independent_points,joined.actual_total_proxy)
    persistence_sp=_spearman(joined.prior_total_proxy,joined.actual_total_proxy)
    score_sp=_spearman(joined.independent_score_v1,joined.actual_total_proxy)
    top_model=_top_fraction_overlap(joined,'independent_points','actual_total_proxy')
    top_persist=_top_fraction_overlap(joined,'prior_total_proxy','actual_total_proxy')
    nd_model=_ndcg(joined,'independent_points','actual_total_proxy')
    nd_persist=_ndcg(joined,'prior_total_proxy','actual_total_proxy')
    mae=float((pd.to_numeric(joined.independent_points,errors='coerce')-pd.to_numeric(joined.actual_total_proxy,errors='coerce')).abs().mean())
    metrics=BacktestMetrics(
        prior_season=season_slug(prior_year),target_season=season_slug(prior_year+1),matched_players=int(joined.player.nunique()),evaluated_players=len(joined),
        model_spearman=model_sp,persistence_spearman=persistence_sp,spearman_lift=model_sp-persistence_sp,
        score_spearman=score_sp,top20_overlap=top_model,persistence_top20_overlap=top_persist,top20_lift=top_model-top_persist,
        ndcg50=nd_model,persistence_ndcg50=nd_persist,mae_total_proxy=mae,understat_available=bool(meta['understat_available'])
    )
    role_rows=[]
    for role,g in joined.groupby('role'):
        role_rows.append({'role':role,'n':len(g),'model_spearman':_spearman(g.independent_points,g.actual_total_proxy),'persistence_spearman':_spearman(g.prior_total_proxy,g.actual_total_proxy),'top20_overlap':_top_fraction_overlap(g,'independent_points','actual_total_proxy')})
    meta['role_metrics']=role_rows
    return metrics,joined,meta


def write_backtest(prior_year:int,out_dir:str|Path,rules:LeagueRules|None=None) -> BacktestMetrics:
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    metrics,details,meta=run_backtest(prior_year,rules)
    pd.DataFrame([asdict(metrics)]).to_csv(out/'summary.csv',index=False)
    details.to_csv(out/'players.csv',index=False)
    (out/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    report=(
        f"# Backtest {metrics.prior_season} → {metrics.target_season}\n\n"
        f"Evaluated players: **{metrics.evaluated_players}**  \n"
        f"Model Spearman: **{metrics.model_spearman:.3f}**  \n"
        f"Persistence Spearman: **{metrics.persistence_spearman:.3f}**  \n"
        f"Lift: **{metrics.spearman_lift:+.3f}**  \n"
        f"Top-20% overlap: **{metrics.top20_overlap:.3f}** vs **{metrics.persistence_top20_overlap:.3f}** persistence  \n"
        f"NDCG@50: **{metrics.ndcg50:.3f}** vs **{metrics.persistence_ndcg50:.3f}** persistence  \n"
        f"Understat prior-season data: **{metrics.understat_available}**\n"
    )
    (out/'report.md').write_text(report,encoding='utf-8')
    return metrics


def aggregate_backtests(root:str|Path,out_dir:str|Path) -> pd.DataFrame:
    root=Path(root); frames=[]
    for p in root.rglob('summary.csv'):
        try:frames.append(pd.read_csv(p))
        except Exception:continue
    if not frames:raise RuntimeError(f'No summary.csv files under {root}')
    df=pd.concat(frames,ignore_index=True).drop_duplicates(['prior_season','target_season']).sort_values('prior_season')
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True); df.to_csv(out/'summary_all.csv',index=False)
    numeric=['model_spearman','persistence_spearman','spearman_lift','top20_overlap','persistence_top20_overlap','top20_lift','ndcg50','persistence_ndcg50']
    avg={c:float(pd.to_numeric(df[c],errors='coerce').mean()) for c in numeric if c in df}
    md=['# Historical backtest aggregate','',f"Seasons: **{len(df)}**",'']
    for k,v in avg.items():md.append(f'- {k}: **{v:.3f}**')
    md += ['', '## Per-season results', '', df.to_markdown(index=False)]
    (out/'report_all.md').write_text('\n'.join(md),encoding='utf-8')
    return df


def main(argv=None):
    parser=argparse.ArgumentParser(description='Leak-free historical Fanta Auction Lab backtest')
    parser.add_argument('--prior-year',type=int)
    parser.add_argument('--out-dir',default='artifacts/backtest')
    parser.add_argument('--aggregate-root')
    args=parser.parse_args(argv)
    if args.aggregate_root:
        df=aggregate_backtests(args.aggregate_root,args.out_dir); print(df.to_string(index=False)); return 0
    if args.prior_year is None:parser.error('--prior-year is required unless --aggregate-root is used')
    m=write_backtest(args.prior_year,args.out_dir); print(json.dumps(asdict(m),indent=2)); return 0


if __name__=='__main__':
    raise SystemExit(main())
