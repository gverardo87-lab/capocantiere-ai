from __future__ import annotations

import os
import sys
import pandas as pd
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.db import db_manager

st.set_page_config(page_title="Riepilogo Generale", page_icon="📊")

st.title("📊 Riepilogo Generale")
st.markdown("Una vista d'insieme dei dati aggregati presenti nel sistema.")

try:
    summary_data = db_manager.get_summary_data()
    if not summary_data:
        st.info("Nessun dato disponibile per il riepilogo. Carica un rapportino per iniziare.")
    else:
        df = pd.DataFrame(summary_data)

        # --- Metriche Principali ---
        st.header("Metriche Chiave")
        col1, col2, col3 = st.columns(3)
        total_hours = df['ore_totali'].sum()
        total_workers = df['operaio'].nunique()
        total_jobs = df['commessa'].nunique()

        col1.metric("Ore Totali Registrate", f"{total_hours:,.2f}")
        col2.metric("Numero Lavoratori Attivi", total_workers)
        col3.metric("Numero Commesse Attive", total_jobs)

        st.divider()

        # --- Grafici di Riepilogo ---
        st.header("Analisi Ore per Lavoratore e Commessa")

        # Ore per Lavoratore
        hours_per_worker = df.groupby('operaio')['ore_totali'].sum().sort_values(ascending=False)
        st.subheader("Ore Totali per Lavoratore")
        st.bar_chart(hours_per_worker)

        # Ore per Commessa
        hours_per_job = df.groupby('commessa')['ore_totali'].sum().sort_values(ascending=False)
        st.subheader("Ore Totali per Commessa")
        st.bar_chart(hours_per_job)

        st.divider()

        # --- Dati Grezzi Aggregati ---
        with st.expander("Mostra Dati di Riepilogo Dettagliati"):
            st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Impossibile generare il riepilogo: {e}")
