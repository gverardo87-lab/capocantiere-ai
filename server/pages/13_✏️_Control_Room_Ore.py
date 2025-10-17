# file: server/pages/13_✏️_Control_Room_Ore.py (Versione 11.0 - Logica di Salvataggio Corretta)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime, date, time

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.crm_db import crm_db_manager
    from core.schedule_db import schedule_db_manager
except ImportError:
    st.error("Errore critico: Impossibile importare i moduli del database.")
    st.stop()

st.set_page_config(page_title="Control Room Ore", page_icon="✏️", layout="wide")
st.title("✏️ Control Room - Gestione Eccezioni")
st.markdown("Visualizza, modifica, o cancella le singole registrazioni ore. Gestisci le interruzioni di cantiere.")

# --- 1. Selettore data e caricamento dati ---
st.subheader("Filtro Giornaliero")
selected_date = st.date_input("Seleziona il giorno da visualizzare", date.today(), key="control_room_date")

@st.cache_data(ttl=30)
def load_registrazioni(giorno: date):
    """Carica le registrazioni per il giorno selezionato."""
    df = crm_db_manager.get_registrazioni_giorno_df(giorno)
    
    # Carica anche le attività per il selectbox
    df_schedule = st.session_state.get('df_schedule', pd.DataFrame())
    if df_schedule.empty:
        schedule_data = schedule_db_manager.get_schedule_data()
        df_schedule = pd.DataFrame(schedule_data)
        st.session_state.df_schedule = df_schedule
        
    opzioni_attivita = {"-1": "N/A (es. Officina)"}
    
    if not df_schedule.empty and 'id_attivita' in df_schedule.columns:
        opzioni_attivita.update({
            row['id_attivita']: f"({row['id_attivita']}) {row['descrizione'][:30]}..." 
            for _, row in df_schedule.iterrows()
        })
    if not df.empty and 'id_attivita' in df.columns:
        for id_att in df['id_attivita'].unique():
            if id_att and id_att not in opzioni_attivita:
                opzioni_attivita[id_att] = f"({id_att}) - ATTIVITÀ PASSATA"
            
    return df, opzioni_attivita

try:
    df_registrazioni, opzioni_attivita = load_registrazioni(selected_date)
    
    # Salva una copia in sessione
    if 'original_df_to_compare' not in st.session_state or \
       st.session_state.get('current_date') != selected_date:
        st.session_state.original_df_to_compare = df_registrazioni.copy()
        st.session_state.current_date = selected_date

except Exception as e:
    st.error(f"Errore nel caricamento delle registrazioni: {e}")
    st.stop()

# --- 2. Tabella Modificabile (Data Editor) ---
st.subheader(f"Registrazioni per il {selected_date.strftime('%d/%m/%Y')}")

if df_registrazioni.empty:
    st.info("Nessuna registrazione trovata per questo giorno. Pianifica un turno dalla pagina 'Pianificazione Turni'.")
else:
    df_registrazioni_copy = df_registrazioni.copy()
    df_registrazioni_copy['elimina'] = False
    
    edited_df = st.data_editor(
        df_registrazioni_copy,
        key="editor_registrazioni",
        use_container_width=True,
        num_rows="dynamic", 
        column_config={
            "id_registrazione": st.column_config.NumberColumn("ID", disabled=True),
            "cognome": st.column_config.TextColumn("Cognome", disabled=True),
            "nome": st.column_config.TextColumn("Nome", disabled=True),
            "ruolo": st.column_config.TextColumn("Ruolo", disabled=True),
            "data_ora_inizio": st.column_config.DatetimeColumn("Inizio", format="DD/MM/YYYY HH:mm", required=True),
            "data_ora_fine": st.column_config.DatetimeColumn("Fine", format="DD/MM/YYYY HH:mm", required=True),
            "id_attivita": st.column_config.SelectboxColumn("Attività", options=opzioni_attivita.keys(), help="Seleziona l'ID dell'attività."),
            "note": st.column_config.TextColumn("Note"),
            "durata_ore": st.column_config.NumberColumn("Ore", format="%.2f h", disabled=True),
            "id_dipendente": None, 
            "elimina": st.column_config.CheckboxColumn("Elimina?", default=False)
        },
        disabled=["id_dipendente", "cognome", "nome", "ruolo", "durata_ore"]
    )

    # --- MODIFICA CHIAVE: Logica di Salvataggio V11 (Robusta) ---
    if st.button("Salva Modifiche ed Eliminazioni", type="primary"):
        try:
            original_df = st.session_state.original_df_to_compare
            eliminati_count = 0
            aggiornati_count = 0
            errori_count = 0

            # 1. Gestisci eliminazioni
            da_eliminare_ids = edited_df[edited_df['elimina'] == True].index
            for id_reg in da_eliminare_ids:
                if id_reg in original_df.index: 
                    crm_db_manager.delete_registrazione(int(id_reg))
                    eliminati_count += 1
            
            # 2. Gestisci modifiche (SOVRASCRIVI TUTTO)
            df_modifiche = edited_df[edited_df['elimina'] == False].drop(columns=['elimina'])
            
            for id_reg, edited_row in df_modifiche.iterrows():
                try:
                    if id_reg not in original_df.index:
                        continue 
                    
                    # Prendi i valori direttamente dallo schermo
                    edit_start = pd.to_datetime(edited_row['data_ora_inizio'])
                    edit_end = pd.to_datetime(edited_row['data_ora_fine'])
                    
                    if pd.isna(edit_start) or pd.isna(edit_end):
                        st.warning(f"Errore riga {id_reg} ({edited_row.get('cognome', 'N/A')}): Data Inizio o Fine non valida. Riga non salvata.")
                        errori_count += 1
                        continue 

                    # Chiamata di aggiornamento "brute force"
                    crm_db_manager.update_full_registrazione(
                        id_reg=int(id_reg),
                        start_time=edit_start,
                        end_time=edit_end,
                        id_att=edited_row.get('id_attivita'),
                        note=edited_row.get('note')
                    )
                    aggiornati_count += 1
                        
                except Exception as e:
                    st.warning(f"Errore generico riga {id_reg}: {e}. Riga non salvata.")
                    errori_count += 1
            
            st.success(f"Salvataggio completato! {aggiornati_count} record aggiornati, {eliminati_count} record eliminati.")
            if errori_count > 0:
                st.warning(f"{errori_count} righe non sono state salvate a causa di errori.")
            
            # Pulisci la cache di TUTTE le pagine
            st.cache_data.clear()
            st.session_state.pop('original_df_to_compare', None) 
            st.rerun()

        except Exception as e:
            st.error(f"Errore critico durante il salvataggio: {e}")
            print(f"Errore salvataggio: {e}") 
    # --- FINE MODIFICA ---

st.divider()

# --- 3. Gestione Interruzioni di Massa ---
st.subheader("🛑 Gestione Interruzioni di Cantiere")
if df_registrazioni.empty:
    st.info("Nessuna registrazione da modificare.")
else:
    with st.form("interruzione_form"):
        opzioni_dipendenti = {}
        for idx, row in edited_df[edited_df['elimina'] == False].iterrows():
            if pd.isna(row['data_ora_inizio']) or pd.isna(row['data_ora_fine']):
                orario_str = "(Orario non valido)"
            else:
                orario_str = f"({row['data_ora_inizio'].strftime('%H:%M')} - {row['data_ora_fine'].strftime('%H:%M')})"
            opzioni_dipendenti[idx] = f"{row['cognome']} {row['nome']} {orario_str}"

        ids_selezionati = st.multiselect("Seleziona registrazioni da splittare", options=opzioni_dipendenti.keys(), format_func=lambda x: opzioni_dipendenti.get(x, "N/A"))
        col1, col2 = st.columns(2)
        with col1:
            ora_inizio_interruzione = st.time_input("Ora Inizio Interruzione", time(14, 0))
        with col2:
            ora_fine_interruzione = st.time_input("Ora Fine Interruzione", time(15, 0))
        submitted_interruzione = st.form_submit_button("Applica Interruzione", use_container_width=True)
        
        if submitted_interruzione:
            if not ids_selezionati:
                st.warning("Nessuna registrazione selezionata."); st.stop()
            if ora_inizio_interruzione >= ora_fine_interruzione:
                st.warning("L'ora di fine interruzione deve essere successiva all'ora di inizio."); st.stop()
            
            dt_inizio_interruzione = datetime.combine(selected_date, ora_inizio_interruzione)
            dt_fine_interruzione = datetime.combine(selected_date, ora_fine_interruzione)
            success_count = 0; fail_count = 0
            
            with st.spinner("Applicazione interruzioni in corso..."):
                for id_reg in ids_selezionati:
                    try:
                        crm_db_manager.split_registrazione_interruzione(int(id_reg), dt_inizio_interruzione, dt_fine_interruzione)
                        success_count += 1
                    except Exception as e:
                        st.error(f"Errore su record {id_reg}: {e}"); fail_count += 1
            
            st.success(f"Interruzione applicata! {success_count} record splittati con successo. {fail_count} falliti.")
            # Pulisci la cache di TUTTE le pagine
            st.cache_data.clear()
            st.session_state.pop('original_df_to_compare', None); st.rerun()