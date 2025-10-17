# file: server/pages/11_👨‍💼_Anagrafica.py

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
                    st.cache_data.clear() # Pulisce la cache per aggiornare la tabella
                except Exception as e:
                    st.error(f"Errore durante l'inserimento: {e}")

st.divider()

# --- 2. Gestisci Dipendenti Esistenti ---
st.subheader("Elenco Personale")
st.markdown("Modifica i dati direttamente nella tabella. Spunta la casella 'attivo' per rimuovere un dipendente dalle selezioni future senza cancellarlo.")

@st.cache_data(ttl=60) # Cache per 60 secondi
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
            num_rows="dynamic", # Permette di aggiungere/eliminare, ma lo gestiamo noi
            disabled=["id_dipendente"], # Non far modificare l'ID
            column_config={
                "id_dipendente": st.column_config.NumberColumn("ID", disabled=True),
                "nome": st.column_config.TextColumn("Nome", required=True),
                "cognome": st.column_config.TextColumn("Cognome", required=True),
                "ruolo": st.column_config.TextColumn("Ruolo"),
                "attivo": st.column_config.CheckboxColumn("Attivo?"),
            }
        )
        
        # Logica per salvare le modifiche
        # st.data_editor non ha un "on_submit", quindi dobbiamo confrontare i dataframe
        # Questo è un pattern comune per salvare le modifiche
        
        if not edited_df.equals(df_personale):
            # Trova le differenze (un modo semplice)
            # Per un'app complessa, si userebbe session_state per tracciare le modifiche
            # Ma per semplicità, ricarichiamo e applichiamo
            st.warning("Modifiche rilevate. In attesa di applicazione...")
            if st.button("Salva Modifiche Tabella"):
                try:
                    # Un modo semplice per aggiornare: confronta riga per riga
                    # Questo è didattico, per produzioni si usa un diff più smart
                    updates = 0
                    for id, row in edited_df.iterrows():
                        original_row = df_personale.loc[id]
                        if not row.equals(original_row):
                            for col in df_personale.columns:
                                if row[col] != original_row[col]:
                                    crm_db_manager.update_dipendente_from_df(id, col, row[col])
                                    updates += 1
                    
                    st.success(f"Aggiornamenti salvati con successo!")
                    st.cache_data.clear() # Pulisce la cache
                    st.rerun() # Ricarica la pagina per mostrare i dati puliti
                except Exception as e:
                    st.error(f"Errore durante il salvataggio: {e}")

except Exception as e:
    st.error(f"Impossibile caricare l'anagrafica: {e}")