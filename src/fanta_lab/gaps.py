from __future__ import annotations
import pandas as pd

CORE_FIELDS = {
    'identity': ['player','team','role'],
    'fantasy_market': ['fvm_1000','quotation'],
    'minutes': ['minutes'],
    'production': ['goals','assists'],
    'expected_stats': ['xg','xa'],
    'discipline': ['yellow_cards','red_cards'],
    'fantasy_history': ['avg_vote'],
    'team_context': ['team_attack_strength','team_defense_strength'],
    'availability': ['starting_probability','injury_risk'],
    'set_pieces': ['penalty_share','set_piece_share'],
}


def _present(df: pd.DataFrame, field: str) -> pd.Series:
    if field not in df:
        return pd.Series(False,index=df.index)
    x=df[field]
    if pd.api.types.is_numeric_dtype(x):
        return pd.to_numeric(x,errors='coerce').notna()
    return x.notna() & x.astype(str).str.strip().ne('')


def player_gap_matrix(df: pd.DataFrame) -> pd.DataFrame:
    out=df[[c for c in ['player','team','role','data_confidence'] if c in df]].copy()
    missing=[]
    for group,fields in CORE_FIELDS.items():
        ok=pd.Series(True,index=df.index)
        for f in fields: ok &= _present(df,f)
        out[f'has_{group}']=ok
        missing.append((group,ok))
    out['gap_count']=sum((~ok).astype(int) for _,ok in missing)
    weights={'fantasy_market':1.2,'minutes':1.5,'production':1.0,'expected_stats':1.6,'discipline':.5,
             'fantasy_history':1.0,'team_context':1.0,'availability':1.3,'set_pieces':.8,'identity':2.0}
    out['gap_severity']=sum((~ok).astype(float)*weights.get(group,1.0) for group,ok in missing)
    out['missing_layers']=[', '.join(group for group,ok in missing if not bool(ok.iloc[i])) for i in range(len(df))]
    return out.sort_values(['gap_severity','data_confidence'] if 'data_confidence' in out else ['gap_severity'],ascending=[False,True] if 'data_confidence' in out else [False])


def gap_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    n=max(1,len(df))
    for group,fields in CORE_FIELDS.items():
        ok=pd.Series(True,index=df.index)
        for f in fields: ok &= _present(df,f)
        rows.append({'layer':group,'covered':int(ok.sum()),'missing':int((~ok).sum()),'coverage_pct':round(100*float(ok.mean()),1),'fields':', '.join(fields)})
    return pd.DataFrame(rows).sort_values('coverage_pct')


def source_priority_for_gaps(gaps: pd.DataFrame) -> pd.DataFrame:
    mapping={
        'expected_stats':'Understat / BigBalls',
        'availability':'API-Football / manual enrichment',
        'set_pieces':'API-Football + user/manual verification',
        'fantasy_history':'fantacalcio.dev / Fantacalcio-Online',
        'team_context':'football-data.co.uk / ClubElo',
        'fantasy_market':'current Fantacalcio list',
        'minutes':'Understat / API-Football / BigBalls',
        'production':'Understat / API-Football / BigBalls',
        'discipline':'API-Football / football-data.co.uk',
        'identity':'football-data.org / current fantasy list',
    }
    counts={k:int((~gaps[f'has_{k}']).sum()) for k in CORE_FIELDS if f'has_{k}' in gaps}
    return pd.DataFrame([{'gap':k,'missing_players':v,'recommended_source':mapping.get(k,'manual')} for k,v in counts.items() if v>0]).sort_values('missing_players',ascending=False)
