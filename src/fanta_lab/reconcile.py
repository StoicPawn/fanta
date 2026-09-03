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
    """Build the auction universe from the official Fantacalcio list only.

    ``roster`` and every other provider are enrichment sources.  They may add fields to
    an official player but can never add a player to the auction universe.  This keeps
    the application aligned with the exact list used at the auction table.
    """
    roster=pd.DataFrame() if roster is None else roster.copy()
    fantasy=pd.DataFrame() if fantasy is None else fantasy.copy()
    team_col='team_fanta' if 'team_fanta' in fantasy else 'team' if 'team' in fantasy else None
    report=CoverageReport(teams=int(fantasy[team_col].nunique()) if team_col else 0,
                          roster_players=len(roster), fantasy_players=len(fantasy))
    if fantasy.empty:
        report.unmatched_roster=roster.player.astype(str).tolist() if 'player' in roster else []
        report.notes.append('Listone Fantacalcio corrente assente: universo d\'asta non costruito.')
        return pd.DataFrame(), report

    fantasy['_norm']=fantasy.player.map(norm_name)
    roster['_norm']=roster.player.map(norm_name) if 'player' in roster else pd.Series(dtype=str)
    r_index={n:i for i,n in roster.get('_norm',pd.Series(dtype=str)).items() if n}
    choices=list(r_index.keys()); used=set(); rows=[]
    for fidx,fr in fantasy.iterrows():
        d={c:fr[c] for c in fantasy.columns if c!='_norm'}
        d['player']=fr['player']
        official_team=fr.get('team_fanta',fr.get('team'))
        official_role=fr.get('role_fanta',fr.get('role'))
        d['team']=fr.get('team') if pd.isna(official_team) else official_team
        d['role']=fr.get('role') if pd.isna(official_role) else official_role
        d['fantasy_eligible']=True
        d['official_listone']=True
        n=fr['_norm']; ridx=r_index.get(n); score=100 if ridx is not None else 0
        if ridx is None and n and choices:
            hit=process.extractOne(n,choices,scorer=fuzz.token_sort_ratio)
            if hit and hit[1]>=90: ridx=r_index[hit[0]]; score=hit[1]
        if ridx is not None:
            used.add(ridx); rr=roster.loc[ridx]
            for c in roster.columns:
                if c in {'player','_norm'}: continue
                target=c if c not in d and c not in {'team','role','source'} else c+'_roster'
                d[target]=rr[c]
            d['roster_match_score']=score
        else:
            d['roster_match_score']=0
            report.unmatched_fantasy.append(str(fr['player']))
        rows.append(d)

    if 'player' in roster:
        report.unmatched_roster=roster.loc[~roster.index.isin(used),'player'].astype(str).tolist()
    out=pd.DataFrame(rows)
    dup=out.assign(_n=out.player.map(norm_name)).duplicated(['_n','team'],keep=False)
    report.duplicate_players=out.loc[dup,'player'].astype(str).tolist()
    report.master_players=len(out); report.matched_fantasy=len(used)
    if report.teams==20 and not report.duplicate_players and report.fantasy_players>=350:
        report.certification='CERTIFIED'
        if report.unmatched_fantasy:
            report.notes.append(f'{len(report.unmatched_fantasy)} giocatori del listone non hanno match nel roster esterno: restano inclusi, con enrichment eventualmente incompleto.')
        if report.unmatched_roster:
            report.notes.append(f'{len(report.unmatched_roster)} elementi del roster esterno non risultano nel listone: esclusi dall\'universo d\'asta.')
    else:
        report.notes.append('Gate fallito: il listone ufficiale deve avere 20 squadre, almeno 350 giocatori e zero duplicati ambigui.')
    return out, report


def coverage_report(df: pd.DataFrame, expected_teams: int=20):
    r=CoverageReport(teams=int(df['team'].nunique()) if 'team' in df else 0, roster_players=len(df), master_players=len(df))
    if r.teams==expected_teams and len(df)>=350: r.certification='BACKBONE_OK'
    return r

def assert_certified(report):
    if getattr(report,'teams',0)!=20 or getattr(report,'fantasy_players',0)<350:
        raise RuntimeError(f'Copertura Listone non valida: {getattr(report,"teams",0)}/20 squadre, {getattr(report,"fantasy_players",0)} giocatori')
