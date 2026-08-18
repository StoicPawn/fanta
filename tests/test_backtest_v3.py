import pandas as pd
from fanta_lab.backtest_v3 import apply_family_score, evaluate_candidate, select_families


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
