from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import os
import pickle
from typing import Any, MutableMapping


# Keep saves outside the downloaded application folder so they survive replacing
# fanta-main with a freshly downloaded ZIP/version.
SAVE_DIR = Path.home() / '.fanta_auction_lab' / 'saves'
SLOT_COUNT = 5
SAVE_VERSION = 1

# Only durable work state is persisted. Widget internals, derived rankings and secrets
# are deliberately excluded.
PERSISTED_KEYS = (
    'rules',
    'players',
    'purchases',
    'manager_names',
    'my_manager',
    'manager_notes',
    'coverage',
)
DERIVED_KEYS = ('scored',)


def _ensure_dir() -> None:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


def _slot_path(slot: int) -> Path:
    if slot < 1 or slot > SLOT_COUNT:
        raise ValueError(f'Slot non valido: {slot}')
    return SAVE_DIR / f'slot_{slot}.pkl'


def _active_path() -> Path:
    return SAVE_DIR / 'active.json'


def _snapshot(session_state: MutableMapping[str, Any]) -> dict[str, Any]:
    return {key: session_state[key] for key in PERSISTED_KEYS if key in session_state}


def _read_payload(slot: int) -> dict[str, Any]:
    path = _slot_path(slot)
    if not path.exists():
        raise FileNotFoundError(f'Lo Slot {slot} è vuoto.')
    with path.open('rb') as handle:
        payload = pickle.load(handle)
    if not isinstance(payload, dict) or payload.get('version') != SAVE_VERSION or 'state' not in payload:
        raise ValueError(f'Slot {slot} non compatibile o danneggiato.')
    return payload


def save_slot(slot: int, session_state: MutableMapping[str, Any]) -> dict[str, Any]:
    """Atomically persist the durable application state into one local slot."""
    _ensure_dir()
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    payload = {
        'version': SAVE_VERSION,
        'slot': slot,
        'saved_at': now,
        'state': _snapshot(session_state),
    }
    target = _slot_path(slot)
    temp = target.with_suffix('.tmp')
    with temp.open('wb') as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(temp, target)
    set_active_slot(slot)
    return {'slot': slot, 'saved_at': now}


def load_slot(slot: int, session_state: MutableMapping[str, Any]) -> dict[str, Any]:
    """Replace the current Streamlit state with a saved slot and mark it active."""
    payload = _read_payload(slot)
    clear_work_state(session_state)
    for key, value in payload['state'].items():
        session_state[key] = value
    session_state['_fanta_active_slot'] = slot
    session_state['_fanta_autosave'] = True
    session_state['_fanta_state_bootstrapped'] = True
    set_active_slot(slot)
    return {'slot': slot, 'saved_at': payload.get('saved_at')}


def list_slots() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slot in range(1, SLOT_COUNT + 1):
        path = _slot_path(slot)
        if not path.exists():
            rows.append({'slot': slot, 'exists': False, 'saved_at': None, 'error': None})
            continue
        try:
            payload = _read_payload(slot)
            rows.append({'slot': slot, 'exists': True, 'saved_at': payload.get('saved_at'), 'error': None})
        except Exception as exc:
            rows.append({'slot': slot, 'exists': True, 'saved_at': None, 'error': str(exc)})
    return rows


def delete_slot(slot: int) -> None:
    path = _slot_path(slot)
    if path.exists():
        path.unlink()
    if get_active_slot() == slot:
        set_active_slot(None)


def delete_all_slots() -> None:
    for slot in range(1, SLOT_COUNT + 1):
        path = _slot_path(slot)
        if path.exists():
            path.unlink()
    set_active_slot(None)


def clear_work_state(session_state: MutableMapping[str, Any]) -> None:
    """Clear the current browser/session work without touching saved slot files."""
    for key in list(session_state.keys()):
        del session_state[key]


def set_active_slot(slot: int | None) -> None:
    _ensure_dir()
    path = _active_path()
    if slot is None:
        if path.exists():
            path.unlink()
        return
    if slot < 1 or slot > SLOT_COUNT:
        raise ValueError(f'Slot non valido: {slot}')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps({'slot': slot}), encoding='utf-8')
    os.replace(temp, path)


def get_active_slot() -> int | None:
    path = _active_path()
    if not path.exists():
        return None
    try:
        slot = int(json.loads(path.read_text(encoding='utf-8')).get('slot'))
        if 1 <= slot <= SLOT_COUNT and _slot_path(slot).exists():
            return slot
    except Exception:
        pass
    return None


def bootstrap_active_slot(session_state: MutableMapping[str, Any]) -> int | None:
    """On a fresh Streamlit session, automatically resume the last active slot."""
    if session_state.get('_fanta_state_bootstrapped'):
        return session_state.get('_fanta_active_slot')
    session_state['_fanta_state_bootstrapped'] = True
    slot = get_active_slot()
    if slot is None:
        return None
    try:
        load_slot(slot, session_state)
        return slot
    except Exception:
        set_active_slot(None)
        return None


def autosave_active_slot(session_state: MutableMapping[str, Any]) -> dict[str, Any] | None:
    slot = session_state.get('_fanta_active_slot')
    enabled = bool(session_state.get('_fanta_autosave', True))
    if not slot or not enabled:
        return None
    return save_slot(int(slot), session_state)
