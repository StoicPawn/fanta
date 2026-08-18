import pandas as pd
from fanta_lab.backtest_v2 import apply_blend, fit_alphas


def _frame(role='A'):
    return pd.DataFrame({
        'player':[f'p{i}' for i in range(20)],
        'role':[role]*20,
        'independent_points':list(range(20)),
        'prior_total_proxy':list(range(19,-1,-1)),
        'actual_total_proxy':list(range(20)),
    })


def test_fit_prefers_model_when_model_is_perfect():
    frames=[_frame('A'),_frame('A'),_frame('A'),_frame('A')]
    a=fit_alphas(frames)
    assert a['A'] >= .8


def test_apply_blend_does_not_use_actual_outcome():
    df=_frame('C')
    x=apply_blend(df,{'C':.6})
    df2=df.copy(); df2['actual_total_proxy']=df2['actual_total_proxy']*0+999
    y=apply_blend(df2,{'C':.6})
    pd.testing.assert_series_equal(x,y)
