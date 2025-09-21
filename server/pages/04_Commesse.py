from __future__ import annotations

import os
import sys
import pandas as pd
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.db import db_manager

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
st.markdown("Puoi modificare lo stato di una commessa direttamente dalla tabella qui sotto.")

try:
    commesse_list = db_manager.list_commesse()
    if not commesse_list:
        st.info("Nessuna commessa presente in anagrafica. Aggiungine una usando il modulo qui sopra.")
    else:
        # Trasformiamo la lista di dizionari in un DataFrame di pandas
        df_commesse = pd.DataFrame(commesse_list)

        # Salviamo una copia originale per il confronto dopo la modifica
        if 'original_commesse' not in st.session_state:
            st.session_state.original_commesse = df_commesse.copy()

        # Usiamo il data_editor per rendere la tabella modificabile
        edited_df = st.data_editor(
            df_commesse,
            column_config={
                "id": None,  # Nascondiamo la colonna ID
                "created_at": st.column_config.DatetimeColumn("Data Creazione", disabled=True),
                "nome": st.column_config.TextColumn("Nome Commessa", disabled=True),
                "cliente": st.column_config.TextColumn("Cliente", disabled=True),
                "stato": st.column_config.SelectboxColumn(
                    "Stato",
                    options=["Attiva", "In Pausa", "Completata", "Annullata"],
                    required=True,
                )
            },
            hide_index=True,
            use_container_width=True
        )

        # Confrontiamo il dataframe modificato con l'originale per trovare le differenze
        if not edited_df.equals(st.session_state.original_commesse):
            st.info("Rilevate modifiche. Clicca il pulsante per salvarle.")
            if st.button("Salva Modifiche Stato", type="primary"):
                # Troviamo le righe modificate
                diff = edited_df.merge(st.session_state.original_commesse, on='id', how='outer', suffixes=('_new', '_old'))
                changed_rows = diff[diff['stato_new'] != diff['stato_old']]

                with st.spinner("Salvataggio in corso..."):
                    for _, row in changed_rows.iterrows():
                        commessa_id = row['id']
                        new_stato = row['stato_new']
                        db_manager.update_commessa(commessa_id, {"stato": new_stato})

                st.success("Modifiche salvate con successo!")
                # Puliamo lo stato e rieseguiamo per ricaricare i dati aggiornati
                del st.session_state.original_commesse
                st.rerun()

except Exception as e:
    st.error(f"Impossibile caricare l'elenco delle commesse: {e}")
