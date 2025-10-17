# file: server/pages/11_👨‍💼_Anagrafica.py (Versione 2.0 - FIX SALVATAGGIO)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.crm_db import crm_db_manager
except ImportError:
    st.error("Errore critico: Impossibile importare `core.crm_db`.")
    st.stop()

st.set_page_config(page_title="Anagrafica Dipendenti", page_icon="👨‍💼", layout="wide")
st.title("👨‍💼 Anagrafica Dipendenti")
st.markdown("Gestisci il personale che opera in cantiere.")

# --- 1. Aggiungi Nuovo Dipendente ---
with st.expander("➕ Aggiungi Nuovo Dipendente", expanded=False):
    with st.form("new_dipendente_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            nome = st.text_input("Nome", key="nome")
        with col2:
            cognome = st.text_input("Cognome", key="cognome")
        with col3:
            ruolo = st.text_input("Ruolo (es. Saldatore, Carpentiere)", key="ruolo")
        
        submitted = st.form_submit_button("Salva Nuovo Dipendente")
        if submitted:
            if not nome or not cognome:
                st.warning("Nome e Cognome sono obbligatori.")
            else:
                try:
                    new_id = crm_db_manager.add_dipendente(nome, cognome, ruolo)
                    st.success(f"Dipendente {nome} {cognome} (ID: {new_id}) aggiunto con successo!")
                    st.cache_data.clear()  # Pulisce la cache per aggiornare la tabella
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore durante l'inserimento: {e}")

st.divider()

# --- 2. Gestisci Dipendenti Esistenti ---
st.subheader("Elenco Personale")
st.markdown("Modifica i dati direttamente nella tabella. Spunta la casella 'attivo' per rimuovere un dipendente dalle selezioni future senza cancellarlo.")

@st.cache_data(ttl=60)  # Cache per 60 secondi
def get_personale_df():
    return crm_db_manager.get_dipendenti_df(solo_attivi=False)

try:
    df_personale = get_personale_df()

    if df_personale.empty:
        st.info("Nessun dipendente trovato. Inizia aggiungendone uno dal modulo qui sopra.")
    else:
        # Usiamo st.data_editor per modifiche live
        edited_df = st.data_editor(
            df_personale,
            key="editor_personale",
            use_container_width=True,
            num_rows="fixed",  # Non permettere aggiunte/eliminazioni da qui
            disabled=["id_dipendente"],  # Non far modificare l'ID
            column_config={
                "id_dipendente": st.column_config.NumberColumn("ID", disabled=True),
                "nome": st.column_config.TextColumn("Nome", required=True),
                "cognome": st.column_config.TextColumn("Cognome", required=True),
                "ruolo": st.column_config.TextColumn("Ruolo"),
                "attivo": st.column_config.CheckboxColumn("Attivo?"),
            }
        )
        
        # Salva le modifiche quando l'utente clicca il pulsante
        if st.button("Salva Modifiche Tabella", type="primary"):
            try:
                updates = []
                
                # Confronta dataframe modificato con originale
                for id_dip in edited_df.index:
                    for col in ['nome', 'cognome', 'ruolo', 'attivo']:
                        if edited_df.loc[id_dip, col] != df_personale.loc[id_dip, col]:
                            updates.append((id_dip, col, edited_df.loc[id_dip, col]))
                
                if not updates:
                    st.info("Nessuna modifica rilevata")
                else:
                    # ✅ USA IL NUOVO METODO
                    for id_dip, field, new_val in updates:
                        crm_db_manager.update_dipendente_field(id_dip, field, new_val)
                    
                    st.success(f"✅ {len(updates)} modifiche salvate!")
                    st.cache_data.clear()  # Pulisce la cache
                    st.rerun()  # Ricarica la pagina per mostrare i dati puliti
                    
            except Exception as e:
                st.error(f"Errore durante il salvataggio: {e}")

except Exception as e:
    st.error(f"Impossibile caricare l'anagrafica: {e}")