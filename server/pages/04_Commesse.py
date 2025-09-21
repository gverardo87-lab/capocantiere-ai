from __future__ import annotations

import os
import sys
import pandas as pd
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.db import db_manager

st.set_page_config(page_title="Gestione Commesse", page_icon="🏗️")

st.title("🏗️ Gestione Commesse")
st.markdown("Aggiungi e visualizza le commesse (progetti) attive.")

# --- Form per Aggiungere Nuova Commessa ---
with st.form("new_commessa_form", clear_on_submit=True):
    st.subheader("Aggiungi Nuova Commessa")
    nome_commessa = st.text_input("Nome Commessa", placeholder="Es. Riparazione Nave Y")
    cliente = st.text_input("Cliente", placeholder="Es. Marina Mercantile S.p.A.")
    submitted = st.form_submit_button("Aggiungi Commessa")

    if submitted:
        if not nome_commessa:
            st.warning("Il campo 'Nome Commessa' è obbligatorio.")
        else:
            try:
                db_manager.add_commessa(nome=nome_commessa, cliente=cliente)
                st.success(f"Commessa '{nome_commessa}' aggiunta con successo!")
            except Exception as e:
                st.error(f"Errore durante l'aggiunta: {e}")

st.divider()

# --- Tabella Commesse Esistenti ---
st.subheader("Elenco Commesse")
try:
    commesse_list = db_manager.list_commesse()
    if commesse_list:
        df = pd.DataFrame(commesse_list).drop(columns=['id'], errors='ignore')
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nessuna commessa presente in anagrafica. Aggiungine una usando il modulo qui sopra.")
except Exception as e:
    st.error(f"Impossibile caricare l'elenco delle commesse: {e}")
