from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import timedelta

import pandas as pd


@dataclass(frozen=True)
class SourceSpec:
    name: str
    layer: str
    access: str
    ttl_seconds: int
    priority: int
    critical: bool
    fields: tuple[str, ...]


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec('football-data.org','roster','free-token',6*3600,100,True,('player','team','role')),
    SourceSpec('Fantacalcio.it/Listone','fantasy-market','public-or-user-file',6*3600,95,True,('quotation','fvm_1000','role_fanta')),
    SourceSpec('Understat','expected-stats','public',7*24*3600,90,False,('minutes','xg','xa','npxg','xg_chain','xg_buildup')),
    SourceSpec('fantacalcio.dev','fantasy-history','public',7*24*3600,75,False,('avg_vote','dev_fantamedia','dev_appearances')),
    SourceSpec('football-data.co.uk','team-context','public-csv',7*24*3600,72,False,('team_attack_strength','team_defense_strength')),
    SourceSpec('ClubElo','team-strength','public',12*3600,80,False,('team_elo','team_elo_factor')),
    SourceSpec('OpenFootball','schedule','cc0',12*3600,70,False,('schedule_ease_factor','schedule_home_share')),
    SourceSpec('Fantacalcio-Online','fantasy-crosscheck','public',24*3600,65,False,('fco_avg_vote','fco_fantamedia')),
    SourceSpec('Fantacalcio-Online aste','auction-prior','public',24*3600,85,False,('market_auction_price',)),
    SourceSpec('API-Football','availability-detail','free-token',6*3600,92,False,('starting_probability','currently_injured','injury_reason','af_rating')),
    SourceSpec('BigBalls','foreign-history','free-token',7*24*3600,82,False,('external_minutes','external_xg','external_xa')),
)


def registry_frame() -> pd.DataFrame:
    rows=[]
    for s in SOURCES:
        d=asdict(s)
        d['ttl_hours']=round(s.ttl_seconds/3600,1)
        d['fields']=', '.join(s.fields)
        rows.append(d)
    return pd.DataFrame(rows).sort_values(['critical','priority'],ascending=[False,False])


def source_for_field(field: str) -> list[SourceSpec]:
    return sorted([s for s in SOURCES if field in s.fields], key=lambda s:s.priority, reverse=True)


def refresh_plan(df: pd.DataFrame | None = None) -> pd.DataFrame:
    rows=[]
    for s in SOURCES:
        if df is None or df.empty:
            coverage=0.0
        else:
            present=[]
            for f in s.fields:
                if f not in df:
                    present.append(pd.Series(False,index=df.index))
                else:
                    x=df[f]
                    present.append(pd.to_numeric(x,errors='coerce').notna() if pd.api.types.is_numeric_dtype(x) else x.notna())
            ok=present[0].copy()
            for p in present[1:]: ok &= p
            coverage=float(ok.mean()) if len(ok) else 0.0
        action='required' if s.critical and coverage < .98 else 'refresh-if-stale' if coverage >= .75 else 'fill-gaps'
        rows.append({'source':s.name,'layer':s.layer,'coverage_pct':round(coverage*100,1),'priority':s.priority,'action':action,'ttl_hours':round(s.ttl_seconds/3600,1)})
    return pd.DataFrame(rows).sort_values(['action','priority'],ascending=[True,False])
