# file: server/pages/10_Pianificazione_Turni.py (Versione 16.6 - Corretto Input Custom)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    # Importiamo solo il service layer, che gestisce tutto
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare i moduli: {e}")
    if 'shift_service' in str(e):
        st.error("Dettaglio: Assicurati che 'core/shift_service.py' esista e non contenga errori di sintassi.")
    st.stop()

st.set_page_config(page_title="Pianificazione Turni", page_icon="📅", layout="wide")
st.title("📅 Pianificazione Turni e Squadre")
st.markdown("Assegna rapidamente intere squadre ai turni di lavoro per attività specifiche.")

# --- DIAGNOSTICA CACHE ---
with st.sidebar:
    st.divider()
    if st.button("Pulisci Cache Dati", help="Forza il ricaricamento dei dati da DB"):
        st.cache_data.clear()
        st.success("Cache pulita. Ricaricamento pagina...")
        st.rerun()
    st.divider()
# --- FINE DIAGNOSTICA ---

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=30)
def load_data():
    """Carica i dati necessari dai database tramite il service layer."""
    print("--- [Pagina 10] Esecuzione load_data() ---")
    turni = shift_service.get_turni_standard()
    squadre = shift_service.get_squadre()
    df_dipendenti = shift_service.get_dipendenti_df(solo_attivi=True)
    
    print(f"  > Turni standard caricati: {len(turni)}")
    print(f"  > Squadre caricate: {len(squadre)}")
    
    dipendenti_map = {index: f"{row['cognome']} {row['nome']}" for index, row in df_dipendenti.iterrows()}

    df_schedule = st.session_state.get('df_schedule', pd.DataFrame())
    if df_schedule.empty:
        try:
            schedule_data = schedule_db_manager.get_schedule_data()
            df_schedule = pd.DataFrame(schedule_data)
            st.session_state.df_schedule = df_schedule
        except Exception as e_sched:
             print(f"Errore caricamento schedule_db: {e_sched}")
             df_schedule = pd.DataFrame()
             st.session_state.df_schedule = df_schedule

    return turni, squadre, df_schedule, dipendenti_map

try:
    lista_turni, lista_squadre, df_schedule, dipendenti_map = load_data()
except Exception as e:
    st.error(f"Impossibile caricare i dati dai database: {e}")
    st.stop()

# --- INTERFACCIA DI PIANIFICAZIONE ---
st.subheader("🗓️ Crea una nuova pianificazione")

if not lista_turni:
    st.error("🚨 ERRORE: Nessun **Turno Standard** trovato nel database.")
elif not lista_squadre:
    st.warning("⚠️ ATTENZIONE: Nessuna **Squadra** configurata nel database.")
    st.info("Vai alla pagina 'Gestisci Squadre' per crearne almeno una.")
elif not dipendenti_map:
    st.warning("⚠️ ATTENZIONE: Nessun **Dipendente attivo** trovato nell'anagrafica.")
    st.info("Vai alla pagina 'Gestisci Anagrafica' per aggiungere personale.")
else:
    # Se i dati ci sono, mostra il form
    with st.form("planning_form"):
        
        st.markdown("##### 1. Tipo Inserimento")
        tipo_inserimento = st.radio(
            "Seleziona il tipo di inserimento",
            ["Standard (da Turni Predefiniti)", "Custom (Orario Manuale)"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        st.markdown("##### 2. Dettagli Turno")
        col1, col2 = st.columns(2)
        
        data_ora_inizio_effettiva = None
        data_ora_fine_effettiva = None
        
        # Variabili per input custom
        data_inizio_custom = date.today()
        ora_inizio_custom = time(8, 0)
        data_fine_custom = date.today()
        ora_fine_custom = time(13, 0) # Default 5 ore

        with col1:
            if tipo_inserimento == "Standard (da Turni Predefiniti)":
                data_selezionata = st.date_input("Seleziona la data di inizio turno", date.today())
                opzioni_turni = {t['id_turno']: f"{t['nome_turno']} ({t['ora_inizio']} - {t['ora_fine']})" for t in lista_turni}
                turno_selezionato_id = st.selectbox(
                    "Seleziona il Turno Standard",
                    options=opzioni_turni.keys(),
                    format_func=lambda x: opzioni_turni[x]
                )
            else:
                # ★ MODIFICA CHIAVE: Input separati per Data e Ora Custom ★
                st.markdown("**Massima Flessibilità (per Viaggi, ecc.)**")
                subcol1, subcol2 = st.columns(2)
                with subcol1:
                    data_inizio_custom = st.date_input("Data Inizio Custom", value=date.today())
                    data_fine_custom = st.date_input("Data Fine Custom", value=date.today())
                with subcol2:
                    ora_inizio_custom = st.time_input("Ora Inizio Custom", value=time(8, 0))
                    ora_fine_custom = st.time_input("Ora Fine Custom", value=time(13, 0))


        with col2:
            opzioni_attivita = {
                "VIAGGIO": "VIAGGIO (Trasferta)",
                "STRAORDINARIO": "STRAORDINARIO (Generico)",
                "OFFICINA": "OFFICINA (Lavoro Interno)",
                "-1": "--- NESSUNA ATTIVITÀ SPECIFICA ---"
            }

            if not df_schedule.empty and 'data_fine' in df_schedule.columns and 'id_attivita' in df_schedule.columns:
                try:
                    attività_attive = df_schedule[pd.to_datetime(df_schedule['data_fine']).dt.date >= date.today()]
                    opzioni_attivita.update({
                        row['id_attivita']: f"({row['id_attivita']}) - {row.get('descrizione', 'N/D')}"
                        for _, row in attività_attive.iterrows() if pd.notna(row.get('id_attivita'))
                    })
                except Exception as e:
                    st.warning(f"Impossibile filtrare le attività: {e}")
            
            attivita_selezionata_id = st.selectbox(
                "Seleziona Attività (o Viaggio/Straordinario)",
                options=opzioni_attivita.keys(),
                format_func=lambda x: opzioni_attivita.get(x, x)
            )

            opzioni_squadre = {s['id_squadra']: s['nome_squadra'] for s in lista_squadre}
            squadra_selezionata_id = st.selectbox(
                "Seleziona la Squadra",
                options=opzioni_squadre.keys(),
                format_func=lambda x: opzioni_squadre[x]
            )

        st.markdown("##### 3. Note e Invio")
        note_pianificazione = st.text_input("Note (visibili a tutti i membri del turno)")
        
        # Il bottone di submit E' PRESENTE DENTRO IL FORM
        submitted = st.form_submit_button("🚀 Pianifica Turno", type="primary", use_container_width=True)

    # --- LOGICA DI ELABORAZIONE ---
    if submitted:
        if not squadra_selezionata_id:
             st.error("Errore interno: ID squadra non valido.")
        else:
            try:
                # --- ★ LOGICA DINAMICA PER ORARI (CORRETTA) ★ ---
                if tipo_inserimento == "Standard (da Turni Predefiniti)":
                    turno_obj = next((t for t in lista_turni if t['id_turno'] == turno_selezionato_id), None)
                    if not turno_obj:
                         st.error(f"Errore: Turno standard con ID '{turno_selezionato_id}' non trovato."); st.stop()

                    ora_inizio = datetime.strptime(turno_obj['ora_inizio'], '%H:%M:%S').time()
                    ora_fine = datetime.strptime(turno_obj['ora_fine'], '%H:%M:%S').time()
                    scavalca_mezzanotte = turno_obj['scavalca_mezzanotte']
                    
                    data_ora_inizio_effettiva = datetime.combine(data_selezionata, ora_inizio)
                    giorno_fine = data_selezionata
                    if scavalca_mezzanotte:
                        giorno_fine += timedelta(days=1)
                    data_ora_fine_effettiva = datetime.combine(giorno_fine, ora_fine)
                
                else: # Modalità Custom
                    # ★ MODIFICA CHIAVE: Combina date e ore dagli input custom ★
                    data_ora_inizio_effettiva = datetime.combine(data_inizio_custom, ora_inizio_custom)
                    data_ora_fine_effettiva = datetime.combine(data_fine_custom, ora_fine_custom)
                    
                    if data_ora_inizio_effettiva >= data_ora_fine_effettiva:
                        st.error("Errore: In modalità Custom, data/ora di fine deve essere successiva a data/ora di inizio."); st.stop()
                
                # --- Logica comune (da qui invariato) ---

                # 2. Recupera membri squadra
                membri_ids = shift_service.get_membri_squadra(squadra_selezionata_id)
                if not membri_ids:
                    st.error(f"La squadra '{opzioni_squadre[squadra_selezionata_id]}' non ha membri assegnati."); st.stop()

                # 4. CONTROLLO SOVRAPPOSIZIONI
                conflitti = []
                for id_dip in membri_ids:
                    if shift_service.check_for_master_overlaps(id_dip, data_ora_inizio_effettiva, data_ora_fine_effettiva):
                        conflitti.append(dipendenti_map.get(id_dip, f"ID Sconosciuto ({id_dip})"))

                if conflitti:
                    st.error("⛔ Impossibile pianificare il turno. I seguenti operai hanno già una sovrapposizione:")
                    st.markdown("\n".join([f"- **{nome}**" for nome in conflitti])); st.stop()

                # 5. Prepara il batch
                registrazioni_batch = []
                nomi_membri_coinvolti = []
                
                # Pulisci l'ID attività se è un placeholder
                id_attivita_db = attivita_selezionata_id if attivita_selezionata_id != "-1" else None
                
                for id_dipendente in membri_ids:
                    registrazioni_batch.append({
                        "id_dipendente": id_dipendente,
                        "id_attivita": id_attivita_db,
                        "data_ora_inizio": data_ora_inizio_effettiva,
                        "data_ora_fine": data_ora_fine_effettiva,
                        "note": note_pianificazione
                    })
                    nomi_membri_coinvolti.append(dipendenti_map.get(id_dipendente, f"ID Sconosciuto ({id_dipendente})"))

                # 6. Inserisci nel DB
                num_inseriti = shift_service.create_shifts_batch(registrazioni_batch)

                st.cache_data.clear()
                st.success(f"✅ Turno pianificato con successo! Inserite {num_inseriti} registrazioni ore.")

                with st.container(border=True):
                    st.subheader("Riepilogo Inserimento")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Squadra:** {opzioni_squadre[squadra_selezionata_id]}")
                        st.write(f"**Attività:** {opzioni_attivita.get(attivita_selezionata_id, 'N/D')}")
                        st.write(f"**Inizio:** {data_ora_inizio_effettiva.strftime('%d/%m/%Y %H:%M')}")
                        st.write(f"**Fine:** {data_ora_fine_effettiva.strftime('%d/%m/%Y %H:%M')}")
                    with c2:
                        st.write(f"**Operai Coinvolti ({len(nomi_membri_coinvolti)}):**")
                        st.markdown("\n".join([f"- {nome}" for nome in nomi_membri_coinvolti]))

            except Exception as e:
                st.error(f"Si è verificato un errore durante la pianificazione: {e}")
                import traceback
                st.code(traceback.format_exc())

if not lista_turni or not lista_squadre:
     st.sidebar.warning("Se il problema persiste dopo aver creato turni/squadre, controlla il file `data/crm.db`.")