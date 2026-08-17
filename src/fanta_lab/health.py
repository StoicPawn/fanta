from __future__ import annotations
import pandas as pd

CRITICAL_COLUMNS=('player','team','role')
IMPORTANT_COLUMNS=('fvm_1000','quotation','minutes','xg','xa')
VALID_ROLES={'P','D','C','A'}


def dataset_health(df:pd.DataFrame, expected_teams:int=20)->dict:
    if df is None or df.empty:
        return {'status':'EMPTY','score':0,'issues':['dataset vuoto'],'metrics':{}}
    issues=[]; metrics={}
    metrics['players']=int(len(df))
    metrics['teams']=int(df['team'].nunique()) if 'team' in df else 0
    metrics['duplicates']=int(df.duplicated(['player','team']).sum()) if {'player','team'}.issubset(df.columns) else 0
    for c in CRITICAL_COLUMNS:
        miss=1.0 if c not in df else float(df[c].isna().mean())
        metrics[f'missing_{c}']=round(miss,4)
        if miss>0: issues.append(f'{c}: {miss:.1%} mancanti')
    if 'role' in df:
        invalid=~df['role'].astype(str).str.upper().isin(VALID_ROLES)
        metrics['invalid_roles']=int(invalid.sum())
        if invalid.any(): issues.append(f'{int(invalid.sum())} ruoli non validi')
    if metrics['teams']!=expected_teams: issues.append(f"squadre osservate {metrics['teams']}/{expected_teams}")
    if metrics['duplicates']>0: issues.append(f"{metrics['duplicates']} duplicati player/team")
    coverage=[]
    for c in IMPORTANT_COLUMNS:
        cov=0.0 if c not in df else float(df[c].notna().mean())
        metrics[f'coverage_{c}']=round(cov,4); coverage.append(cov)
    base=100
    base-=min(35,abs(expected_teams-metrics['teams'])*8)
    base-=min(20,metrics['duplicates']*2)
    base-=sum(20*metrics.get(f'missing_{c}',1) for c in CRITICAL_COLUMNS)
    base-=max(0,25-25*(sum(coverage)/max(1,len(coverage))))
    score=int(max(0,min(100,round(base))))
    status='READY' if score>=90 and metrics['teams']==expected_teams and metrics['duplicates']==0 else 'USABLE_WITH_WARNINGS' if score>=70 else 'NOT_READY'
    return {'status':status,'score':score,'issues':issues,'metrics':metrics}


def auction_health(state)->dict:
    issues=[]
    overspent=[m for m in state.manager_names if state.spent(m)>state.rules.budget]
    if overspent: issues.append('budget superato: '+', '.join(overspent))
    overflow=[]
    for m in state.manager_names:
        counts={r:0 for r in state.rules.slots()}
        for p in state.roster(m): counts[p.role]=counts.get(p.role,0)+1
        for r,n in counts.items():
            if n>state.rules.slots().get(r,0): overflow.append(f'{m}:{r}')
    if overflow: issues.append('slot superati: '+', '.join(overflow))
    duplicate_players=[]
    seen=set()
    for p in state.purchases:
        if p.player in seen: duplicate_players.append(p.player)
        seen.add(p.player)
    if duplicate_players: issues.append('giocatori venduti due volte: '+', '.join(sorted(set(duplicate_players))))
    return {'status':'OK' if not issues else 'INVALID','issues':issues}
