from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

from src.fanta_lab.ui import apply_theme, page_header, common_sidebar, empty_state, section

st.set_page_config(page_title='Backtest Lab · Fanta Auction Lab',page_icon='🧪',layout='wide')
apply_theme(); common_sidebar()
page_header('Backtest Lab','Validazione temporale del modello indipendente: una stagione serve solo come input e la successiva come outcome. Nessun FVM entra nel modello sportivo.','EVIDENCE')

root=Path('backtests/latest')
summary_path=root/'summary_all.csv'
report_path=root/'report_all.md'

if not summary_path.exists():
    empty_state('Backtest in esecuzione o non ancora persistito','Il workflow historical-backtests salva qui automaticamente il report aggregato quando almeno una stagione termina.')
    st.info('Metriche principali: Spearman del modello vs outcome stagionale, baseline di persistenza, overlap Top 20%, NDCG@50 e lift rispetto alla baseline.')
    st.stop()

summary=pd.read_csv(summary_path)
if summary.empty:
    st.warning('Il report esiste ma non contiene stagioni valide.')
    st.stop()

model_sp=pd.to_numeric(summary.model_spearman,errors='coerce').mean()
base_sp=pd.to_numeric(summary.persistence_spearman,errors='coerce').mean()
lift=pd.to_numeric(summary.spearman_lift,errors='coerce').mean()
top_lift=pd.to_numeric(summary.top20_lift,errors='coerce').mean()

k=st.columns(5)
k[0].metric('Stagioni validate',len(summary))
k[1].metric('Spearman modello',f'{model_sp:.3f}')
k[2].metric('Baseline persistenza',f'{base_sp:.3f}')
k[3].metric('Lift rank',f'{lift:+.3f}')
k[4].metric('Lift Top 20%',f'{top_lift:+.3f}')

if lift>0.02:
    st.success('Il modello sta battendo la semplice persistenza storica in media sul ranking.')
elif lift>-0.02:
    st.warning('Il modello è circa allineato alla persistenza: serve calibrazione prima di considerarlo superiore.')
else:
    st.error('Il modello sottoperforma la persistenza: i pesi vanno rivisti prima di usarlo come vantaggio informativo.')

section('Risultati per stagione','Ogni riga è un forecast one-season-ahead costruito esclusivamente con la stagione precedente.')
st.dataframe(summary,use_container_width=True,hide_index=True,height=430)

chart=summary[['target_season','model_spearman','persistence_spearman']].copy().set_index('target_season')
st.line_chart(chart)

c1,c2=st.columns(2)
with c1:
    section('Lift di ranking')
    st.bar_chart(summary.set_index('target_season')[['spearman_lift']])
with c2:
    section('Lift Top 20%')
    st.bar_chart(summary.set_index('target_season')[['top20_lift']])

section('Interpretazione','Il benchmark non è casuale: la baseline assume che il valore fantasy dell’anno precedente persista. Per essere davvero utile il modello deve batterla in modo stabile, non soltanto in una singola stagione.')
if report_path.exists():
    with st.expander('Report aggregato Markdown',expanded=False):
        st.markdown(report_path.read_text(encoding='utf-8'))

st.download_button('Scarica risultati CSV',summary.to_csv(index=False).encode('utf-8'),file_name='fanta_backtest_summary.csv',mime='text/csv',use_container_width=True)
