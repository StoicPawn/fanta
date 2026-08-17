import pandas as pd

from src.fanta_lab.sources.football_data_uk import FootballDataUKSource
from src.fanta_lab.sources.bigballs import BigBallsSource
from src.fanta_lab.sources.fantacalcio_dev import FantacalcioDevSource


def test_football_data_uk_season_code():
    assert FootballDataUKSource.season_code(2025) == '2526'
    assert FootballDataUKSource.season_code(2026) == '2627'


def test_bigballs_requires_key():
    try:
        BigBallsSource('')
        assert False
    except ValueError:
        assert True


def test_fantacalcio_dev_column_normalizer():
    assert FantacalcioDevSource._norm('Voto Medio') == 'voto medio'


def test_team_context_formula_shape(monkeypatch):
    raw=pd.DataFrame([
        {'HomeTeam':'A','AwayTeam':'B','FTHG':2,'FTAG':1,'HS':10,'AS':8,'HST':5,'AST':3,'HC':4,'AC':2,'HY':1,'AY':2,'HR':0,'AR':0},
        {'HomeTeam':'B','AwayTeam':'A','FTHG':0,'FTAG':1,'HS':7,'AS':9,'HST':2,'AST':4,'HC':3,'AC':5,'HY':2,'AY':1,'HR':0,'AR':0},
    ])
    src=FootballDataUKSource()
    monkeypatch.setattr(src,'matches',lambda start_year,division='I1': raw)
    out=src.team_features(2025)
    assert set(out.team)=={'A','B'}
    assert 'team_attack_strength' in out
    assert 'team_defense_strength' in out
    assert out.matches.eq(2).all()
