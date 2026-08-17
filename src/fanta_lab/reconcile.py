from __future__ import annotations
from dataclasses import dataclass, field
import re, unicodedata
import pandas as pd
from rapidfuzz import fuzz, process


def norm_name(s: str) -> str:
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii','ignore').decode().lower()
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    return ' '.join(s.split())

@dataclass
class CoverageReport:
    teams: int = 0
    roster_players: int = 0
    fantasy_players: int = 0
    master_players: int = 0
    matched_fantasy: int = 0
    unmatched_roster: list[str] = field(default_factory=list)
    unmatched_fantasy: list[str] = field(default_factory=list)
    duplicate_players: list[str] = field(default_factory=list)
    certification: str = 'UNVERIFIED'
    notes: list[str] = field(default_factory=list)

    @property
    def certified(self) -> bool:
        return self.certification == 'CERTIFIED'


def fuzzy_join(left: pd.DataFrame, right: pd.DataFrame, suffix: str, threshold: int = 88):
    if right is None or right.empty:
        return left.copy(), []
    l = left.copy(); r = right.copy()
    l['_norm'] = l['player'].map(norm_name); r['_norm'] = r['player'].map(norm_name)
    rcols = [c for c in r.columns if c not in {'player','_norm'}]
    exact = {n:i for i,n in enumerate(r['_norm']) if n}
    choices = list(exact.keys())
    rows=[]; used=set()
    for _, row in l.iterrows():
        d=row.to_dict(); n=row['_norm']; idx=exact.get(n); score=100 if idx is not None else 0
        if idx is None and n and choices:
            hit=process.extractOne(n, choices, scorer=fuzz.token_sort_ratio)
            if hit and hit[1] >= threshold: idx=exact[hit[0]]; score=hit[1]
        if idx is not None:
            used.add(idx); rr=r.iloc[idx]
            for c in rcols: d[c if c not in d else c+suffix]=rr[c]
            d['match_score'+suffix]=score
        rows.append(d)
    out=pd.DataFrame(rows).drop(columns=['_norm'],errors='ignore')
    unmatched=r.loc[~r.index.isin(used),'player'].astype(str).tolist()
    return out, unmatched


def build_master_roster(roster: pd.DataFrame, fantasy: pd.DataFrame | None) -> tuple[pd.DataFrame,CoverageReport]:
    roster=roster.copy()
    fantasy=pd.DataFrame() if fantasy is None else fantasy.copy()
    report=CoverageReport(teams=int(roster['team'].nunique()) if 'team' in roster else 0,
                          roster_players=len(roster), fantasy_players=len(fantasy))
    if roster.empty:
        report.notes.append('Roster backbone vuoto.')
        return roster, report
    roster['_norm']=roster.player.map(norm_name)
    if fantasy.empty:
        report.master_players=len(roster); report.unmatched_roster=roster.player.astype(str).tolist()
        report.notes.append('Listone Fantacalcio corrente assente: impossibile certificare eleggibilità fantasy.')
        return roster.drop(columns='_norm'), report
    fantasy['_norm']=fantasy.player.map(norm_name)
    f_index={n:i for i,n in fantasy['_norm'].items() if n}
    choices=list(f_index.keys()); used=set(); rows=[]
    for _, rr in roster.iterrows():
        d=rr.to_dict(); n=rr['_norm']; idx=f_index.get(n); score=100 if idx is not None else 0
        if idx is None and choices:
            hit=process.extractOne(n,choices,scorer=fuzz.token_sort_ratio)
            if hit and hit[1]>=90: idx=f_index[hit[0]]; score=hit[1]
        if idx is not None:
            used.add(idx); fr=fantasy.loc[idx]
            for c in fantasy.columns:
                if c not in {'player','_norm'}: d[c]=fr[c]
            d['fantasy_eligible']=True; d['roster_match_score']=score
        else:
            d['fantasy_eligible']=False; report.unmatched_roster.append(str(rr.player))
        rows.append(d)
    for idx,fr in fantasy.iterrows():
        if idx in used: continue
        rows.append({'player':fr['player'],'team':fr.get('team_fanta'),'team_tla':fr.get('team_fanta'),
                     'position_raw':None,'role':fr.get('role'),'source':'fantacalcio.it-public',
                     **{c:fr[c] for c in fantasy.columns if c not in {'player','_norm'}},
                     'fantasy_eligible':True,'roster_match_score':0})
        report.unmatched_fantasy.append(str(fr['player']))
    out=pd.DataFrame(rows).drop(columns=['_norm'],errors='ignore')
    if 'role_fanta' in out:
        out['role']=out['role_fanta'].fillna(out.get('role'))
    dup=out.assign(_n=out.player.map(norm_name)).duplicated(['_n','team'],keep=False)
    report.duplicate_players=out.loc[dup,'player'].astype(str).tolist()
    report.master_players=len(out); report.matched_fantasy=len(used)
    if report.teams==20 and not report.duplicate_players and report.fantasy_players>=350:
        report.certification='CERTIFIED'
        if report.unmatched_fantasy:
            report.notes.append(f'{len(report.unmatched_fantasy)} giocatori sono presenti solo nel listone: inclusi nel master come nuovi/da riconciliare.')
        if report.unmatched_roster:
            report.notes.append(f'{len(report.unmatched_roster)} elementi del roster non risultano nel listone: mantenuti ma non marcati fantasy_eligible.')
    else:
        report.notes.append('Gate fallito: servono 20 squadre, listone plausibilmente completo e zero duplicati ambigui.')
    return out, report


def coverage_report(df: pd.DataFrame, expected_teams: int=20):
    r=CoverageReport(teams=int(df['team'].nunique()) if 'team' in df else 0, roster_players=len(df), master_players=len(df))
    if r.teams==expected_teams and len(df)>=350: r.certification='BACKBONE_OK'
    return r

def assert_certified(report):
    if getattr(report,'teams',0)!=20 or getattr(report,'roster_players',0)<350:
        raise RuntimeError(f'Copertura roster non valida: {getattr(report,"teams",0)}/20 squadre, {getattr(report,"roster_players",0)} giocatori')
