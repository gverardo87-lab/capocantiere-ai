# file: server/pages/10_📅_Pianificazione_Turni.py (Versione 16.0 - Architettura Service)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    # ★ IMPORT CORRETTO ★
    # Importiamo solo il service layer, che gestisce tutto
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare i moduli: {e}")
    st.stop()

st.set_page_config(page_title="Pianificazione Turni", page_icon="📅", layout="wide")
st.title("📅 Pianificazione Turni e Squadre")
st.markdown("Assegna rapidamente intere squadre ai turni di lavoro per attività specifiche.")

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=60)
def load_data():
    """Carica i dati necessari dai database tramite il service layer."""
    # ★ CHIAMATE CORRETTE al service ★
    turni = shift_service.get_turni_standard()
    squadre = shift_service.get_squadre()
    df_dipendenti = shift_service.get_dipendenti_df(solo_attivi=True)
    
    dipendenti_map = {index: f"{row['cognome']} {row['nome']}" for index, row in df_dipendenti.iterrows()}

    # Il cronoprogramma è separato, quindi va bene
    df_schedule = st.session_state.get('df_schedule', pd.DataFrame())
    if df_schedule.empty:
        schedule_data = schedule_db_manager.get_schedule_data()
        df_schedule = pd.DataFrame(schedule_data)
        st.session_state.df_schedule = df_schedule
        
    return turni, squadre, df_schedule, dipendenti_map

try:
    lista_turni, lista_squadre, df_schedule, dipendenti_map = load_data()
except Exception as e:
    st.error(f"Impossibile caricare i dati dai database: {e}")
    st.stop()

# --- INTERFACCIA DI PIANIFICAZIONE ---
st.subheader("🗓️ Crea una nuova pianificazione")

if not lista_turni or not lista_squadre:
    st.warning("Non ci sono turni standard o squadre configurati nel database.")
elif not dipendenti_map:
    st.warning("Non ci sono dipendenti nell'anagrafica. Aggiungine almeno uno prima di pianificare.")
else:
    with st.form("planning_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            data_selezionata = st.date_input("Seleziona la data di inizio turno", date.today())
            
            opzioni_turni = {t['id_turno']: f"{t['nome_turno']} ({t['ora_inizio']} - {t['ora_fine']})" for t in lista_turni}
            turno_selezionato_id = st.selectbox(
                "Seleziona il Turno Standard",
                options=opzioni_turni.keys(),
                format_func=lambda x: opzioni_turni[x]
            )

        with col2:
            opzioni_attivita = {"-1": "Nessuna attività specifica (es. Officina)"}
            
            if not df_schedule.empty and 'data_fine' in df_schedule.columns:
                try:
                    attività_attive = df_schedule[pd.to_datetime(df_schedule['data_fine']).dt.date >= date.today()]
                    opzioni_attivita.update({
                        row['id_attivita']: f"({row['id_attivita']}) - {row['descrizione']}" 
                        for _, row in attività_attive.iterrows()
                    })
                except Exception as e:
                    st.warning(f"Impossibile filtrare le attività: {e}")
            
            attivita_selezionata_id = st.selectbox(
                "Seleziona Attività del Cronoprogramma",
                options=opzioni_attivita.keys(),
                format_func=lambda x: opzioni_attivita.get(x, x) 
            )

            opzioni_squadre = {s['id_squadra']: s['nome_squadra'] for s in lista_squadre}
            squadra_selezionata_id = st.selectbox(
                "Seleziona la Squadra",
                options=opzioni_squadre.keys(),
                format_func=lambda x: opzioni_squadre[x]
            )

        note_pianificazione = st.text_input("Note (visibili a tutti i membri del turno)")
        
        submitted = st.form_submit_button("🚀 Pianifica Turno", type="primary", use_container_width=True)

    # --- LOGICA DI ELABORAZIONE ---
    if submitted:
        try:
            # 1. Recupera dettagli turno
            turno_obj = next(t for t in lista_turni if t['id_turno'] == turno_selezionato_id)
            ora_inizio = datetime.strptime(turno_obj['ora_inizio'], '%H:%M:%S').time()
            ora_fine = datetime.strptime(turno_obj['ora_fine'], '%H:%M:%S').time()
            scavalca_mezzanotte = turno_obj['scavalca_mezzanotte']

            # 2. Recupera membri squadra (★ CHIAMATA CORRETTA ★)
            membri_ids = shift_service.get_membri_squadra(squadra_selezionata_id)
            if not membri_ids:
                st.error(f"La squadra '{opzioni_squadre[squadra_selezionata_id]}' non ha membri assegnati."); st.stop()

            # 3. Calcola timestamp
            data_ora_inizio = datetime.combine(data_selezionata, ora_inizio)
            giorno_fine = data_selezionata
            if scavalca_mezzanotte:
                giorno_fine += timedelta(days=1)
            data_ora_fine = datetime.combine(giorno_fine, ora_fine)

            # 4. CONTROLLO SOVRAPPOSIZIONI (★ CHIAMATA CORRETTA ★)
            conflitti = []
            for id_dip in membri_ids:
                if shift_service.check_for_master_overlaps(id_dip, data_ora_inizio, data_ora_fine):
                    conflitti.append(dipendenti_map.get(id_dip, f"ID Sconosciuto ({id_dip})"))
            
            if conflitti:
                st.error("⛔ Impossibile pianificare il turno. I seguenti operai hanno già una sovrapposizione:")
                st.markdown("\n".join([f"- **{nome}**" for nome in conflitti])); st.stop()

            # 5. Prepara il batch
            registrazioni_batch = []
            nomi_membri_coinvolti = []
            for id_dipendente in membri_ids:
                registrazioni_batch.append({
                    "id_dipendente": id_dipendente,
                    "id_attivita": attivita_selezionata_id if attivita_selezionata_id != "-1" else None,
                    "data_ora_inizio": data_ora_inizio,
                    "data_ora_fine": data_ora_fine,
                    "note": note_pianificazione
                })
                nomi_membri_coinvolti.append(dipendenti_map.get(id_dipendente, f"ID Sconosciuto ({id_dipendente})"))

            # 6. Inserisci nel DB (★ CHIAMATA CORRETTA ★)
            num_inseriti = shift_service.create_shifts_batch(registrazioni_batch)
            
            st.cache_data.clear()
            st.success(f"✅ Turno pianificato con successo! Inserite {num_inseriti} registrazioni ore.")
            
            with st.container(border=True):
                st.subheader("Riepilogo Inserimento")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Squadra:** {opzioni_squadre[squadra_selezionata_id]}")
                    st.write(f"**Attività:** {opzioni_attivita[attivita_selezionata_id]}")
                    st.write(f"**Inizio:** {data_ora_inizio.strftime('%d/%m/%Y %H:%M')}")
                    st.write(f"**Fine:** {data_ora_fine.strftime('%d/%m/%Y %H:%M')}")
                with c2:
                    st.write(f"**Operai Coinvolti ({len(nomi_membri_coinvolti)}):**")
                    st.markdown("\n".join([f"- {nome}" for nome in nomi_membri_coinvolti]))

        except Exception as e:
            st.error(f"Si è verificato un errore durante la pianificazione: {e}")
            import traceback
            st.code(traceback.format_exc())
