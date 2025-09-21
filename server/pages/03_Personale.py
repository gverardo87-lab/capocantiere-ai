from __future__ import annotations

import os
import sys
import pandas as pd
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.db import db_manager

st.title("👷‍♂️ Gestione Personale")
st.markdown("Aggiungi e visualizza i lavoratori presenti in anagrafica.")

# --- Form per Aggiungere Nuovo Personale ---
with st.form("new_personale_form", clear_on_submit=True):
    st.subheader("Aggiungi Nuovo Lavoratore")
    nome_completo = st.text_input("Nome Completo", placeholder="Es. Mario Rossi")
    qualifica = st.text_input("Qualifica", placeholder="Es. Carpentiere")
    submitted = st.form_submit_button("Aggiungi Lavoratore")

    if submitted:
        if not nome_completo:
            st.warning("Il campo 'Nome Completo' è obbligatorio.")
        else:
            try:
                db_manager.add_personale(nome_completo=nome_completo, qualifica=qualifica)
                st.success(f"Lavoratore '{nome_completo}' aggiunto con successo!")
            except Exception as e:
                st.error(f"Errore durante l'aggiunta: {e}")

st.divider()

# --- Tabella Personale Esistente ---
st.subheader("Elenco Personale")
try:
    personale_list = db_manager.list_personale()
    if personale_list:
        df = pd.DataFrame(personale_list).drop(columns=['id'], errors='ignore')
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nessun lavoratore presente in anagrafica. Aggiungine uno usando il modulo qui sopra.")
except Exception as e:
    st.error(f"Impossibile caricare l'elenco del personale: {e}")
