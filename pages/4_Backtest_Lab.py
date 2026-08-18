from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

from src.fanta_lab.ui import apply_theme, page_header, common_sidebar, empty_state, section

st.set_page_config(page_title='Backtest Lab · Fanta Auction Lab',page_icon='🧪',layout='wide')
apply_theme(); common_sidebar()
page_header('Backtest Lab','Validazione temporale del modello indipendente. V1 è one-season-ahead; V2 testa il blending walk-forward; V3 seleziona famiglie di feature con ablation e lascia 2025/26 completamente fuori dalla selezione.','EVIDENCE')

v1_root=Path('backtests/latest'); v2_root=Path('backtests/v2'); v3_root=Path('backtests/v3')
v1_path=v1_root/'summary_all.csv'; v2_path=v2_root/'summary_v2.csv'; v3_path=v3_root/'summary_v3.csv'

if not v1_path.exists():
    empty_state('Backtest non ancora persistito','Il workflow historical-backtests salva qui automaticamente il report aggregato.')
    st.stop()

v1=pd.read_csv(v1_path)
if v1.empty:
    st.warning('Il report V1 esiste ma non contiene stagioni valide.'); st.stop()

v1_tab,v2_tab,v3_tab=st.tabs(['V1 · baseline storica','V2 · walk-forward OOS','V3 · feature ablation'])

with v1_tab:
    model_sp=pd.to_numeric(v1.model_spearman,errors='coerce').mean(); base_sp=pd.to_numeric(v1.persistence_spearman,errors='coerce').mean(); lift=pd.to_numeric(v1.spearman_lift,errors='coerce').mean(); top_lift=pd.to_numeric(v1.top20_lift,errors='coerce').mean()
    k=st.columns(5); k[0].metric('Stagioni',len(v1)); k[1].metric('Spearman V1',f'{model_sp:.3f}'); k[2].metric('Persistenza',f'{base_sp:.3f}'); k[3].metric('Lift rank',f'{lift:+.3f}'); k[4].metric('Lift Top 20%',f'{top_lift:+.3f}')
    if lift>0.02:st.success('V1 batte la persistenza in media.')
    elif lift>-0.02:st.warning('V1 è sostanzialmente allineato alla persistenza: non è ancora evidenza di vantaggio.')
    else:st.error('V1 sottoperforma la persistenza.')
    section('Risultati per stagione','Forecast one-season-ahead usando solo dati della stagione precedente.')
    st.dataframe(v1,use_container_width=True,hide_index=True,height=420)
    st.line_chart(v1[['target_season','model_spearman','persistence_spearman']].set_index('target_season'))

with v2_tab:
    if not v2_path.exists():
        empty_state('V2 non disponibile','Il workflow walkforward-v2 non ha ancora persistito risultati.')
    else:
        v2=pd.read_csv(v2_path)
        final=v2[v2.is_final_holdout.astype(str).str.lower().isin(['true','1'])] if 'is_final_holdout' in v2 else pd.DataFrame()
        mean_lift=pd.to_numeric(v2.v2_lift_vs_persistence,errors='coerce').mean(); mean_v2=pd.to_numeric(v2.v2_spearman,errors='coerce').mean()
        k=st.columns(5); k[0].metric('Fold walk-forward',len(v2)); k[1].metric('Spearman V2 medio',f'{mean_v2:.3f}'); k[2].metric('Lift medio vs persistenza',f'{mean_lift:+.3f}')
        if len(final):
            f=final.iloc[0]; k[3].metric('OOS 2025/26 V2',f"{float(f.v2_spearman):.3f}"); k[4].metric('OOS lift',f"{float(f.v2_lift_vs_persistence):+.3f}")
            if float(f.v2_lift_vs_persistence)>0.02:st.success('Il holdout finale batte la persistenza con margine utile.')
            elif float(f.v2_lift_vs_persistence)>0:st.info('Il holdout finale batte la persistenza, ma il margine è piccolo.')
            else:st.error('Il holdout finale non batte la persistenza: V2 non va promosso.')
        st.dataframe(v2,use_container_width=True,hide_index=True,height=430)
        st.line_chart(v2[['target_season','v2_spearman','v1_spearman','persistence_spearman']].set_index('target_season'))

with v3_tab:
    if not v3_path.exists():
        empty_state('V3 in esecuzione','Il workflow ablation-v3 sta testando multiseason, regressione xG, trend di disponibilità e stabilità del voto. Una famiglia entra solo se migliora i fold di training.')
        st.info('2025/26 resta holdout finale: non viene usato per scegliere nessuna famiglia di feature.')
    else:
        v3=pd.read_csv(v3_path)
        final=v3[v3.is_final_holdout.astype(str).str.lower().isin(['true','1'])] if 'is_final_holdout' in v3 else pd.DataFrame()
        k=st.columns(5)
        k[0].metric('Fold V3',len(v3)); k[1].metric('Understat fold',int(v3.understat_available.astype(str).str.lower().isin(['true','1']).sum()))
        if len(final):
            f=final.iloc[0]
            k[2].metric('OOS V3',f"{float(f.v3_spearman):.3f}"); k[3].metric('Lift vs V1',f"{float(f.v3_lift_vs_v1):+.3f}"); k[4].metric('Lift vs pers.',f"{float(f.v3_lift_vs_persistence):+.3f}")
            st.caption(f"Feature selezionate sul training: {f.selected_families}")
            if float(f.v3_lift_vs_v1)>0 and float(f.v3_lift_vs_persistence)>0:st.success('V3 migliora entrambe le baseline sul holdout finale.')
            else:st.warning('V3 non ha ancora superato entrambe le baseline sul holdout: non va promossa automaticamente.')
        st.dataframe(v3,use_container_width=True,hide_index=True,height=430)
        st.line_chart(v3[['target_season','v3_spearman','v1_spearman','persistence_spearman']].set_index('target_season'))
        report=v3_root/'report_v3.md'
        if report.exists():
            with st.expander('Report V3 Markdown',expanded=False):st.markdown(report.read_text(encoding='utf-8'))

section('Principio di promozione','Una nuova versione entra nel motore live solo se migliora sul fold finale senza averlo usato per scegliere pesi o feature. FVM/quotazioni restano fuori dalla valutazione sportiva.')
