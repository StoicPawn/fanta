import pandas as pd
from fanta_lab.sources.understat import UnderstatSource


def test_extract_players_payload_hex_escaped():
    html="""<script>var playersData = JSON.parse('\\x5B\\x7B\\x22player_name\\x22\\x3A\\x22Test Player\\x22\\x2C\\x22xG\\x22\\x3A\\x221.25\\x22\\x7D\\x5D');</script>"""
    data=UnderstatSource._extract_players_payload(html)
    assert data[0]['player_name']=='Test Player'
    assert data[0]['xG']=='1.25'


def test_extract_players_payload_plain_json_escape():
    html="""<script>playersData = JSON.parse('[{\"player_name\":\"Mario Rossi\",\"xA\":\"2.0\"}]')</script>"""
    data=UnderstatSource._extract_players_payload(html)
    assert data[0]['player_name']=='Mario Rossi'


def test_normalize_mirror_schema():
    raw=pd.DataFrame([{'player_name':'Test','team_title':'Roma','time':'900','xG':'4.2','xA':'1.5','league':'Serie_A','year':2023}])
    out=UnderstatSource._normalize(raw,2023,'understat-github-mirror')
    assert out.iloc[0].player=='Test'
    assert out.iloc[0].team_understat=='Roma'
    assert out.iloc[0].minutes==900
    assert out.iloc[0].xg==4.2
    assert out.iloc[0].source_stats=='understat-github-mirror'


def test_league_players_falls_back_to_mirror(monkeypatch):
    src=UnderstatSource()
    UnderstatSource._DIRECT_DISABLED_REASON=None
    UnderstatSource._MIRROR_CACHE=None
    monkeypatch.setattr(src,'_league_players_direct',lambda year: (_ for _ in ()).throw(RuntimeError('blocked')))
    mirror=pd.DataFrame([
        {'player_name':'A','team_title':'Inter','time':1000,'xG':5,'xA':2,'league':'Serie_A','year':2022},
        {'player_name':'B','team_title':'Milan','time':900,'xG':4,'xA':1,'league':'Serie_A','year':2023},
        {'player_name':'C','team_title':'Arsenal','time':900,'xG':4,'xA':1,'league':'EPL','year':2022},
    ])
    monkeypatch.setattr(src,'_load_mirror',lambda: mirror)
    out=src.league_players(2022)
    assert out.player.tolist()==['A']
    assert out.source_stats.iloc[0]=='understat-github-mirror'
    assert 'blocked' in out.understat_direct_error.iloc[0]
