from __future__ import annotations

import streamlit as st


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
