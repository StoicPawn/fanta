from __future__ import annotations

import streamlit as st

from .persistence import (
    SLOT_COUNT,
    autosave_active_slot,
    bootstrap_active_slot,
    clear_work_state,
    delete_all_slots,
    delete_slot,
    list_slots,
    load_slot,
    save_slot,
    set_active_slot,
)


def apply_theme():
    st.markdown('''
    <style>
    .block-container{padding-top:1.1rem;padding-bottom:3rem;max-width:1540px}
    [data-testid="stSidebar"]{border-right:1px solid rgba(127,127,127,.12)}
    [data-testid="stMetric"]{padding:12px 14px;border:1px solid rgba(127,127,127,.14);border-radius:14px;background:rgba(127,127,127,.045)}
    [data-testid="stMetricValue"]{font-size:1.55rem}
    [data-testid="stDataFrame"]{border:1px solid rgba(127,127,127,.12);border-radius:12px;overflow:hidden}
    .fal-hero{padding:20px 22px;border-radius:18px;border:1px solid rgba(127,127,127,.16);background:linear-gradient(120deg,rgba(127,127,127,.085),rgba(127,127,127,.018));margin-bottom:14px}
    .fal-hero h1{margin:0;font-size:2rem;line-height:1.15}
    .fal-hero p{margin:.45rem 0 0 0;opacity:.72;max-width:1000px}
    .fal-section{margin-top:.8rem;margin-bottom:.25rem;font-size:1.12rem;font-weight:650}
    .fal-chip{display:inline-block;padding:4px 9px;border-radius:999px;border:1px solid rgba(127,127,127,.18);background:rgba(127,127,127,.06);font-size:.78rem;margin-right:5px;margin-bottom:5px}
    .fal-good{border-left:4px solid #2da44e;padding:10px 12px;background:rgba(45,164,78,.07);border-radius:8px}
    .fal-warn{border-left:4px solid #bf8700;padding:10px 12px;background:rgba(191,135,0,.08);border-radius:8px}
    .fal-bad{border-left:4px solid #cf222e;padding:10px 12px;background:rgba(207,34,46,.07);border-radius:8px}
    div[data-testid="stButton"] button{border-radius:10px;font-weight:600}
    </style>
    ''', unsafe_allow_html=True)


def page_header(title:str, subtitle:str, eyebrow:str|None=None):
    e=f'<div style="font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;opacity:.55;margin-bottom:6px">{eyebrow}</div>' if eyebrow else ''
    st.markdown(f'<div class="fal-hero">{e}<h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def section(title:str, caption:str|None=None):
    st.markdown(f'<div class="fal-section">{title}</div>', unsafe_allow_html=True)
    if caption: st.caption(caption)


def status_box(text:str, level:str='info'):
    cls={'success':'fal-good','warning':'fal-warn','error':'fal-bad'}.get(level,'fal-warn')
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def empty_state(title:str, body:str):
    st.info(f'**{title}**\n\n{body}')


def _slot_label(row:dict)->str:
    slot=row['slot']
    if row.get('error'):
        return f'Slot {slot} · ERRORE'
    if not row.get('exists'):
        return f'Slot {slot} · vuoto'
    saved=str(row.get('saved_at') or '').replace('T',' ')[:16]
    return f'Slot {slot} · {saved}' if saved else f'Slot {slot} · salvato'


def _save_slot_sidebar():
    # Resume the last active slot on a brand-new Streamlit/browser session.
    bootstrap_active_slot(st.session_state)

    # This captures the completed state from the previous rerun. Pages that mutate
    # durable state also call autosave at their end, so the last interaction is saved.
    try:
        autosave_active_slot(st.session_state)
    except Exception as exc:
        st.session_state['_fanta_save_error']=str(exc)

    rows=list_slots(); by_slot={row['slot']:row for row in rows}
    active=st.session_state.get('_fanta_active_slot')

    st.divider()
    st.markdown('**Salvataggi asta**')
    if active:
        st.success(f'Slot {active} attivo')
    else:
        st.caption('Nessuno slot attivo · lavoro non ancora salvato')

    default_slot=int(active) if active else 1
    if '_fanta_save_selected_slot' not in st.session_state:
        st.session_state['_fanta_save_selected_slot']=default_slot
    selected=st.selectbox(
        'Slot',range(1,SLOT_COUNT+1),key='_fanta_save_selected_slot',
        format_func=lambda x:_slot_label(by_slot[x])
    )

    if '_fanta_autosave' not in st.session_state:
        st.session_state['_fanta_autosave']=True
    st.toggle('Autosave slot attivo',key='_fanta_autosave',help='Quando uno slot è attivo, le modifiche principali vengono riscritte automaticamente sul disco locale.')

    a,b=st.columns(2)
    if a.button('Carica',use_container_width=True,key='_fanta_load_slot'):
        try:
            info=load_slot(int(selected),st.session_state)
            st.session_state['_fanta_flash']=f"Slot {selected} caricato · {info.get('saved_at','')}"
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if b.button('Salva ora',use_container_width=True,key='_fanta_save_slot'):
        try:
            info=save_slot(int(selected),st.session_state)
            st.session_state['_fanta_active_slot']=int(selected)
            st.session_state['_fanta_autosave']=True
            st.session_state['_fanta_flash']=f"Salvato nello Slot {selected} · {info['saved_at']}"
            st.rerun()
        except Exception as exc:
            st.error(f'Salvataggio non riuscito: {exc}')

    if st.button('Nuovo / pulisci lavoro corrente',use_container_width=True,key='_fanta_new_work'):
        clear_work_state(st.session_state)
        set_active_slot(None)
        st.session_state['_fanta_state_bootstrapped']=True
        st.session_state['_fanta_flash']='Nuovo lavoro vuoto. I salvataggi esistenti non sono stati cancellati.'
        st.rerun()

    with st.expander('Elimina salvataggi'):
        st.caption('Operazioni distruttive: non modificano gli altri slot salvo dove indicato.')
        confirm=st.checkbox('Confermo eliminazione',key='_fanta_delete_confirm')
        if st.button('Elimina slot selezionato',use_container_width=True,disabled=not confirm,key='_fanta_delete_slot'):
            delete_slot(int(selected))
            if st.session_state.get('_fanta_active_slot')==int(selected):
                st.session_state.pop('_fanta_active_slot',None)
            st.session_state['_fanta_flash']=f'Slot {selected} eliminato.'
            st.rerun()
        if st.button('Elimina TUTTI gli slot',use_container_width=True,disabled=not confirm,key='_fanta_delete_all'):
            delete_all_slots()
            st.session_state.pop('_fanta_active_slot',None)
            st.session_state['_fanta_flash']='Tutti i salvataggi sono stati eliminati.'
            st.rerun()

    if st.session_state.get('_fanta_save_error'):
        st.warning('Autosave non riuscito: '+str(st.session_state.pop('_fanta_save_error')))
    if st.session_state.get('_fanta_flash'):
        st.info(str(st.session_state.pop('_fanta_flash')))
    st.caption('Gli slot sono locali a questo PC e non salvano token/API key.')


def common_sidebar():
    with st.sidebar:
        st.caption('FANTA AUCTION LAB')
        st.markdown('**Flusso consigliato**')
        st.caption('1. Data Sources → 2. Formazione → 3. Ranking → 4. Command Center')
        players=st.session_state.get('players')
        purchases=st.session_state.get('purchases',[])
        if players is not None and hasattr(players,'empty') and not players.empty:
            st.success(f'Dataset attivo · {len(players)} giocatori')
        else:
            st.warning('Dataset non caricato')
        if purchases:
            st.caption(f'Asta: {len(purchases)} vendite registrate')
        _save_slot_sidebar()
