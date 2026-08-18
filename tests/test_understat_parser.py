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
