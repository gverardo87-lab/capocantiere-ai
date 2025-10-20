# file: server/pages/10_Pianificazione_Turni.py (Versione 16.1 - Diagnostica Aggiunta)

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
    # Mostra un suggerimento utile se l'errore è relativo a shift_service
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
# Usiamo un TTL più breve per ridurre problemi di cache
@st.cache_data(ttl=30)
def load_data():
    """Carica i dati necessari dai database tramite il service layer."""
    print("--- [Pagina 10] Esecuzione load_data() ---") # Debug
    turni = shift_service.get_turni_standard()
    squadre = shift_service.get_squadre()
    df_dipendenti = shift_service.get_dipendenti_df(solo_attivi=True)
    
    print(f"  > Turni standard caricati: {len(turni)}") # Debug
    print(f"  > Squadre caricate: {len(squadre)}") # Debug
    
    dipendenti_map = {index: f"{row['cognome']} {row['nome']}" for index, row in df_dipendenti.iterrows()}

    df_schedule = st.session_state.get('df_schedule', pd.DataFrame())
    if df_schedule.empty:
        try:
            schedule_data = schedule_db_manager.get_schedule_data()
            df_schedule = pd.DataFrame(schedule_data)
            st.session_state.df_schedule = df_schedule
        except Exception as e_sched:
             print(f"Errore caricamento schedule_db: {e_sched}") # Debug non bloccante
             df_schedule = pd.DataFrame() # Inizializza vuoto se c'è errore
             st.session_state.df_schedule = df_schedule

    return turni, squadre, df_schedule, dipendenti_map

try:
    lista_turni, lista_squadre, df_schedule, dipendenti_map = load_data()
except Exception as e:
    st.error(f"Impossibile caricare i dati dai database: {e}")
    st.stop()

# --- INTERFACCIA DI PIANIFICAZIONE ---
st.subheader("🗓️ Crea una nuova pianificazione")

# ★ CONTROLLO SPECIFICO ★
if not lista_turni:
    st.error("🚨 ERRORE: Nessun **Turno Standard** trovato nel database.")
    st.warning("Azione richiesta: Controlla la tabella `turni_standard` nel file `data/crm.db`. Dovrebbe contenere almeno 'GIORNO_08_18' e 'NOTTE_20_06'. Se è vuota, prova a riavviare l'applicazione per far rieseguire l'inizializzazione.")
elif not lista_squadre:
    st.warning("⚠️ ATTENZIONE: Nessuna **Squadra** configurata nel database.")
    st.info("Vai alla pagina 'Gestisci Squadre' per crearne almeno una.")
elif not dipendenti_map:
    st.warning("⚠️ ATTENZIONE: Nessun **Dipendente attivo** trovato nell'anagrafica.")
    st.info("Vai alla pagina 'Gestisci Anagrafica' per aggiungere personale.")
else:
    # Se i dati ci sono, mostra il form
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

            if not df_schedule.empty and 'data_fine' in df_schedule.columns and 'id_attivita' in df_schedule.columns:
                try:
                    # Filtra attività non ancora concluse
                    attività_attive = df_schedule[pd.to_datetime(df_schedule['data_fine']).dt.date >= date.today()]
                    opzioni_attivita.update({
                        row['id_attivita']: f"({row['id_attivita']}) - {row.get('descrizione', 'N/D')}"
                        for _, row in attività_attive.iterrows() if pd.notna(row.get('id_attivita')) # Aggiunto controllo per ID non nullo
                    })
                except Exception as e:
                    st.warning(f"Impossibile filtrare le attività: {e}")
            elif not df_schedule.empty:
                 st.warning("Cronoprogramma caricato ma mancano colonne 'data_fine' o 'id_attivita'.")
            else:
                 st.info("Nessun dato di cronoprogramma caricato.")

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
        # Verifica ID selezionati prima di procedere
        if not turno_selezionato_id or not squadra_selezionata_id:
             st.error("Errore interno: ID turno o squadra non valido.")
        else:
            try:
                # 1. Recupera dettagli turno
                turno_obj = next((t for t in lista_turni if t['id_turno'] == turno_selezionato_id), None)
                if not turno_obj:
                     st.error(f"Errore: Turno standard con ID '{turno_selezionato_id}' non trovato."); st.stop()

                ora_inizio = datetime.strptime(turno_obj['ora_inizio'], '%H:%M:%S').time()
                ora_fine = datetime.strptime(turno_obj['ora_fine'], '%H:%M:%S').time()
                scavalca_mezzanotte = turno_obj['scavalca_mezzanotte']

                # 2. Recupera membri squadra
                membri_ids = shift_service.get_membri_squadra(squadra_selezionata_id)
                if not membri_ids:
                    st.error(f"La squadra '{opzioni_squadre[squadra_selezionata_id]}' non ha membri assegnati."); st.stop()

                # 3. Calcola timestamp
                data_ora_inizio = datetime.combine(data_selezionata, ora_inizio)
                giorno_fine = data_selezionata
                if scavalca_mezzanotte:
                    giorno_fine += timedelta(days=1)
                data_ora_fine = datetime.combine(giorno_fine, ora_fine)

                # 4. CONTROLLO SOVRAPPOSIZIONI
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

                # 6. Inserisci nel DB
                num_inseriti = shift_service.create_shifts_batch(registrazioni_batch)

                # Pulisce la cache DOPO l'inserimento
                st.cache_data.clear()
                st.success(f"✅ Turno pianificato con successo! Inserite {num_inseriti} registrazioni ore.")

                # Mostra Riepilogo (opzionale, ma utile)
                with st.container(border=True):
                    st.subheader("Riepilogo Inserimento")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Squadra:** {opzioni_squadre[squadra_selezionata_id]}")
                        st.write(f"**Attività:** {opzioni_attivita.get(attivita_selezionata_id, 'N/D')}") # Usiamo get per sicurezza
                        st.write(f"**Inizio:** {data_ora_inizio.strftime('%d/%m/%Y %H:%M')}")
                        st.write(f"**Fine:** {data_ora_fine.strftime('%d/%m/%Y %H:%M')}")
                    with c2:
                        st.write(f"**Operai Coinvolti ({len(nomi_membri_coinvolti)}):**")
                        st.markdown("\n".join([f"- {nome}" for nome in nomi_membri_coinvolti]))

                # Aggiungiamo un rerun esplicito per essere sicuri che la cache pulita venga usata
                # Potrebbe non essere strettamente necessario ma aiuta in caso di dubbi
                # st.rerun() # Attenzione: se decommentato, il riepilogo potrebbe sparire subito

            except Exception as e:
                st.error(f"Si è verificato un errore durante la pianificazione: {e}")
                import traceback
                st.code(traceback.format_exc())

# Aggiunta finale per sicurezza: se ci sono ancora problemi dopo le modifiche, suggerisci controllo DB
if not lista_turni or not lista_squadre:
     st.sidebar.warning("Se il problema persiste dopo aver creato turni/squadre, controlla il file `data/crm.db` con uno strumento come DB Browser for SQLite.")