import pandas as pd
from src.fanta_lab.gaps import player_gap_matrix, gap_summary
from src.fanta_lab.sources.openfootball import OpenFootballItalySource, schedule_difficulty


def test_gap_analyzer_flags_missing_layers():
    df=pd.DataFrame([{'player':'X','team':'A','role':'A','fvm_1000':100,'quotation':20,'minutes':1000,'goals':5,'assists':2,'xg':4.5,'xa':2.2,'yellow_cards':2,'red_cards':0,'avg_vote':6.3,'team_attack_strength':1.1,'team_defense_strength':1.0}])
    g=player_gap_matrix(df)
    assert g.iloc[0].gap_count>=2
    assert 'availability' in g.iloc[0].missing_layers
    assert 'set_pieces' in g.iloc[0].missing_layers
    s=gap_summary(df)
    assert 'availability' in set(s.layer)


def test_openfootball_parser_minimal(monkeypatch):
    txt='''= Italian Serie A 2026/27\n▪ Matchday 1\n  Sun Aug 23 2026\n    18:30  Team A   v Team B\n           Team C   v Team D\n▪ Matchday 2\n    Team B   v Team A\n'''
    src=OpenFootballItalySource()
    monkeypatch.setattr(src,'season_text',lambda y:txt)
    out=src.fixtures(2026)
    assert len(out)==3
    assert set(out.matchday)=={1,2}


def test_schedule_difficulty_uses_elo():
    fx=pd.DataFrame([{'matchday':1,'home_team':'A','away_team':'B'},{'matchday':2,'home_team':'C','away_team':'A'}])
    elo=pd.DataFrame([{'team':'A','team_elo':1600},{'team':'B','team_elo':1800},{'team':'C','team_elo':1400}])
    d=schedule_difficulty(fx,elo,2)
    row=d[d.team=='A'].iloc[0]
    assert row.schedule_horizon==2
    assert 0.88 <= row.schedule_ease_factor <= 1.12
