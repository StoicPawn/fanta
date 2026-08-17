import os

from src.fanta_lab.config import get_secret, secret_status
from src.fanta_lab.sources.football_data import FootballDataSource


def test_explicit_secret_wins(monkeypatch):
    monkeypatch.setenv('FOOTBALL_DATA_TOKEN','from-env')
    assert get_secret('FOOTBALL_DATA_TOKEN','from-session') == 'from-session'


def test_environment_secret(monkeypatch):
    monkeypatch.setenv('FOOTBALL_DATA_TOKEN','from-env')
    assert get_secret('FOOTBALL_DATA_TOKEN') == 'from-env'
    assert secret_status('FOOTBALL_DATA_TOKEN') in {'environment','streamlit-secret'}


def test_client_never_requires_committed_token(monkeypatch):
    monkeypatch.setenv('FOOTBALL_DATA_TOKEN','runtime-only')
    client=FootballDataSource()
    assert client.token == 'runtime-only'


def test_rate_header_extraction():
    h={'X-RequestCounter-Reset':'42','Retry-After':'60','Other':'x'}
    out=FootballDataSource._rate_headers(h)
    assert 'Other' not in out
    assert out['Retry-After'] == 60
