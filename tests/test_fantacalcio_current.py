import pandas as pd

from fanta_lab.independent_model import build_independent_valuation
from fanta_lab.models import LeagueRules
from fanta_lab.projection import project_player
from fanta_lab.reconcile import CoverageReport
from fanta_lab.sources.fantacalcio import (
    FantacalcioCurrentStatsSource,
    FantacalcioPublicSource,
)


LISTONE_HTML = """
<html><body><table><tbody>
<tr class="player-row" data-filter-keywords="Malen" data-filter-role-classic="a">
  <th class="player-name"><span>Malen</span></th>
  <td data-col-key="sq">ROM</td><td data-col-key="c_qi">34</td>
  <td data-col-key="c_qa">38</td><td data-col-key="c_fvm">450</td>
</tr>
</tbody></table></body></html>
"""


STATS_HTML = """
<html><body><table><tbody>
<tr class="player-row" data-filter-keywords="Malen" data-filter-role-classic="a">
  <td data-col-key="sq">ROM</td><td data-col-key="pg">2</td>
  <td data-col-key="mv">8,25</td><td data-col-key="mfv">15,50</td>
  <td data-col-key="gol">5</td><td data-col-key="gs">0</td>
  <td data-col-key="rig">1 / 1</td><td data-col-key="rp">0</td>
  <td data-col-key="ass">0</td><td data-col-key="amm">1</td>
  <td data-col-key="esp">0</td>
</tr>
<tr class="player-row" data-filter-keywords="Altro" data-filter-role-classic="c">
  <td data-col-key="sq">INT</td><td data-col-key="pg">1</td>
  <td data-col-key="mv">6,0</td><td data-col-key="mfv">6,0</td>
  <td data-col-key="gol">0</td><td data-col-key="gs">0</td>
  <td data-col-key="rig">0 / 0</td><td data-col-key="rp">0</td>
  <td data-col-key="ass">0</td><td data-col-key="amm">0</td>
  <td data-col-key="esp">0</td>
</tr>
</tbody></table></body></html>
"""


def test_public_listone_parser_reads_semantic_player_cells():
    out=FantacalcioPublicSource._parse_public_rows(LISTONE_HTML).iloc[0]
    assert out.player=='Malen'
    assert out.team_fanta=='ROM'
    assert out.role_fanta=='A'
    assert out.quotation==38
    assert out.fvm_1000==450


def test_current_stats_parser_reads_opening_matchdays():
    out=FantacalcioCurrentStatsSource._parse_public_rows(STATS_HTML).set_index('player')
    assert out.loc['Malen','current_appearances']==2
    assert out.loc['Malen','current_avg_vote']==8.25
    assert out.loc['Malen','current_goals']==5
    assert out.loc['Malen','current_penalties_attempted']==1
    assert out.current_league_matchdays.eq(2).all()


def test_current_official_evidence_gives_majority_low_confidence_predictions():
    players=pd.DataFrame([
        {
            'player':f'P{i}','team':'T','role':'A','minutes':0,
            'current_appearances':1 if i<6 else 0,'current_league_matchdays':2,
            'current_goals':1 if i==0 else 0,'current_assists':0,
            'current_avg_vote':6.0,'data_confidence':.30,'fvm_1000':20+i,
        }
        for i in range(10)
    ])
    rules=LeagueRules(budget=100,managers=1,slots_gk=0,slots_def=0,slots_mid=0,slots_fwd=1)
    out=build_independent_valuation(players,rules)
    available=out.prediction_available.fillna(False)
    assert int(available.sum())==6
    assert float(available.mean())>.50
    assert out.loc[available,'prediction_confidence'].eq('BASSA').all()
    assert out.loc[~available,'independent_fair_price'].isna().all()


def test_two_game_hot_streak_is_strongly_shrunk():
    row=pd.Series({
        'role':'A','minutes':0,'current_appearances':2,'current_league_matchdays':2,
        'current_goals':5,'current_assists':0,'current_avg_vote':8.25,
        'data_confidence':.30,
    })
    result=project_player(row,LeagueRules())
    raw_current_rate=5*90/(2*70)
    assert result['prediction_available']
    assert result['prediction_confidence']=='BASSA'
    assert .28 < result['pred_goal90'] < raw_current_rate*.30


def test_prediction_majority_gate_is_explicit():
    report=CoverageReport(prediction_total=590,prediction_eligible=339,prediction_coverage=339/590)
    assert report.prediction_majority_ready
    report.prediction_coverage=.50
    assert not report.prediction_majority_ready
    report.prediction_coverage=.49
    assert not report.prediction_majority_ready
