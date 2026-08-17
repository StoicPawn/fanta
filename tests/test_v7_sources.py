import pandas as pd

from src.fanta_lab.sources.football_data_uk import FootballDataUKSource
from src.fanta_lab.sources.bigballs import BigBallsSource
from src.fanta_lab.sources.fantacalcio_dev import FantacalcioDevSource
from src.fanta_lab.sources.api_football import APIFootballSource


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


def test_api_football_flatten():
    item={
        'player':{'id':7,'name':'Test Player','age':25,'nationality':'Italy','height':'180 cm','weight':'75 kg','injured':True},
        'statistics':[{'games':{'appearences':20,'lineups':15,'minutes':1400,'rating':'6.8'},'shots':{'total':40,'on':20},
                       'goals':{'total':8,'assists':4,'conceded':0,'saves':0},'passes':{'key':22,'accuracy':83},
                       'tackles':{'total':10,'interceptions':4},'dribbles':{'attempts':30,'success':18},
                       'fouls':{'drawn':25,'committed':12},'cards':{'yellow':3,'red':0},
                       'penalty':{'won':1,'commited':0,'scored':2,'missed':1,'saved':0}}]
    }
    x=APIFootballSource._flatten_player(item)
    assert x['player']=='Test Player'
    assert x['af_minutes']==1400
    assert x['af_key_passes']==22
    assert x['currently_injured'] is True


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
