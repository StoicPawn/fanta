import time
import pandas as pd

from src.fanta_lab import cache
from src.fanta_lab.source_registry import refresh_plan, registry_frame


def test_registry_contains_critical_roster_and_market():
    r=registry_frame()
    assert 'football-data.org' in set(r.name)
    assert 'Fantacalcio.it/Listone' in set(r.name)
    assert r[r.name.eq('football-data.org')].iloc[0].critical


def test_refresh_plan_flags_missing_critical_layers():
    df=pd.DataFrame([{'player':'X','team':'A','role':'A'}])
    p=refresh_plan(df)
    market=p[p.source.eq('Fantacalcio.it/Listone')].iloc[0]
    assert market.action == 'required'
    assert market.coverage_pct == 0.0


def test_dataframe_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cache,'CACHE_DIR',tmp_path)
    calls={'n':0}
    def loader():
        calls['n']+=1
        return pd.DataFrame([{'x':1}])
    a,s1=cache.cached_dataframe('test','x',60,loader)
    b,s2=cache.cached_dataframe('test','x',60,loader)
    assert a.equals(b)
    assert calls['n']==1
    assert s2['cache']=='hit'


def test_stale_cache_can_fallback_on_source_error(tmp_path, monkeypatch):
    monkeypatch.setattr(cache,'CACHE_DIR',tmp_path)
    cache.write_dataframe('test','stale',pd.DataFrame([{'x':2}]))
    # force metadata old enough to be stale
    meta,_=cache._paths('test','stale')
    import json
    data=json.loads(meta.read_text()); data['created_at']=time.time()-1000; meta.write_text(json.dumps(data))
    out,status=cache.cached_dataframe('test','stale',1,lambda: (_ for _ in ()).throw(RuntimeError('down')))
    assert out.iloc[0].x==2
    assert status['cache']=='stale-fallback'
