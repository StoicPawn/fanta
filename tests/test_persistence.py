import pandas as pd

from fanta_lab.models import AuctionPurchase, LeagueRules
import fanta_lab.persistence as persistence


def _state():
    return {
        'rules': LeagueRules(budget=700, managers=10),
        'players': pd.DataFrame([
            {'player':'A','team':'Inter','role':'A','quotation':20},
            {'player':'B','team':'Milan','role':'C','quotation':10},
        ]),
        'purchases': [AuctionPurchase('Io','A','A',71.0,note='top')],
        'manager_names': ['Io']+[f'Team {i}' for i in range(1,10)],
        'my_manager': 'Io',
        'manager_notes': {'Team 1':'aggressivo'},
        # Must never be persisted because it is derived.
        'scored': pd.DataFrame([{'x':1}]),
        # Simulate a widget/runtime secret-like key: not on the whitelist.
        'FOOTBALL_DATA_TOKEN': 'secret',
    }


def test_slot_roundtrip_and_whitelist(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence,'SAVE_DIR',tmp_path/'.fanta_saves')
    state=_state()
    persistence.save_slot(2,state)

    state['rules'].budget=123
    state['players']=pd.DataFrame()
    persistence.load_slot(2,state)

    assert state['rules'].budget==700
    assert len(state['players'])==2
    assert state['purchases'][0].player=='A'
    assert state['manager_notes']['Team 1']=='aggressivo'
    assert 'scored' not in state
    assert 'FOOTBALL_DATA_TOKEN' not in state
    assert state['_fanta_active_slot']==2


def test_bootstrap_resumes_last_active_slot(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence,'SAVE_DIR',tmp_path/'.fanta_saves')
    persistence.save_slot(4,_state())
    fresh={}
    slot=persistence.bootstrap_active_slot(fresh)
    assert slot==4
    assert fresh['rules'].budget==700
    assert len(fresh['purchases'])==1


def test_delete_slots_keeps_operations_independent(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence,'SAVE_DIR',tmp_path/'.fanta_saves')
    persistence.save_slot(1,_state())
    persistence.save_slot(2,_state())
    persistence.delete_slot(1)
    rows={x['slot']:x for x in persistence.list_slots()}
    assert not rows[1]['exists']
    assert rows[2]['exists']
    persistence.delete_all_slots()
    assert not any(x['exists'] for x in persistence.list_slots())
