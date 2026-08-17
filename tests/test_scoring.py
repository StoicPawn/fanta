import sys
sys.path.append('src')
import pandas as pd
from fanta_lab.scoring import add_scores

def test_score_bounds():
    d=pd.DataFrame([{'player':'x','role':'A','minutes':1000,'goals':10,'assists':3}])
    x=add_scores(d)
    assert 0 <= x.fanta_score.iloc[0] <= 100
