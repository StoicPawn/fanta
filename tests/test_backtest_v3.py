import pandas as pd
from fanta_lab.backtest_v3 import apply_family_score, evaluate_candidate, select_families, _attach_previous_season


def frame(n=80):
    x=pd.DataFrame({
        'player':[f'p{i}' for i in range(n)],
        'role':['A']*n,
        'independent_points':list(range(n)),
        'prior_total_proxy':list(range(n)),
        'actual_total_proxy':list(range(n)),
        'multiseason_signal':list(range(n)),
        'xg_regression_signal':[0.0]*n,
        'availability_trend_signal':[0.0]*n,
        'vote_stability_signal':[0.0]*n,
    })
    return x


def test_family_score_does_not_use_outcome():
    a=frame(); x=apply_family_score(a,('multiseason',))
    b=a.copy(); b['actual_total_proxy']=999
    y=apply_family_score(b,('multiseason',))
    pd.testing.assert_series_equal(x,y)


def test_evaluation_is_finite():
    m=evaluate_candidate(frame(),())
    assert m['spearman'] > .99


def test_selection_returns_tuple_and_audit():
    selected,audit=select_families([frame(),frame()])
    assert isinstance(selected,tuple)
    assert isinstance(audit,pd.DataFrame)


def test_previous_season_attach_preserves_current_outcome(monkeypatch):
    current=pd.DataFrame({'player':['Mario Rossi'],'actual_total_proxy':[123.0]})
    previous=pd.DataFrame({
        'player':['Mario Rossi'],'role_target':['A'],'actual_fantamedia':[7.0],
        'actual_avg_vote':[6.2],'actual_appearances':[30],'actual_goals':[10],
        'actual_assists':[5],'actual_total_proxy':[210.0],
    })
    monkeypatch.setattr('fanta_lab.backtest_v3.load_historical_outcomes',lambda year: previous.copy())
    out=_attach_previous_season(current,2024)
    assert float(out.loc[0,'actual_total_proxy']) == 123.0
    assert float(out.loc[0,'prev_total_proxy']) == 210.0
