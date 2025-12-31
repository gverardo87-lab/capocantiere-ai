# file: server/pages/10_Pianificazione_Turni.py (Versione 31.0 - Storicizzazione UI)
# Include: Custom Mode, HR Transfer, Conflict Policy, Team History

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare i moduli: {e}")
    st.stop()

st.set_page_config(page_title="Pianificazione Turni", page_icon="📅", layout="wide")
st.title("📅 Pianificazione Turni & Cicli")
st.markdown("Gestione integrata: Pianificazione Ordinaria (Squadre/Custom) e Gestione HR (Trasferimenti/Cambi Ciclo).")

# --- DIAGNOSTICA CACHE ---
with st.sidebar:
    st.divider()
    if st.button("Pulisci Cache Dati", help="Forza il ricaricamento dei dati da DB"):
        st.cache_data.clear()
        st.success("Cache pulita. Ricaricamento pagina...")
        st.rerun()
    st.divider()

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=30)
def load_data():
    turni = shift_service.get_turni_standard()
    squadre = shift_service.get_squadre()
    df_dip = shift_service.get_dipendenti_df(solo_attivi=True)
    
    # Map per visualizzazione nomi
    dip_map = {index: f"{row['cognome']} {row['nome']}" for index, row in df_dip.iterrows()}

    df_sched = st.session_state.get('df_schedule', pd.DataFrame())
    if df_sched.empty:
        try:
            s_data = schedule_db_manager.get_schedule_data()
            df_sched = pd.DataFrame(s_data)
            st.session_state.df_schedule = df_sched
        except Exception as e:
            print(f"Errore schedule: {e}")
            df_sched = pd.DataFrame()

    return turni, squadre, df_dip, dip_map, df_sched

try:
    lista_turni, lista_squadre, df_dipendenti, dipendenti_map, df_schedule = load_data()
except Exception as e:
    st.error(f"Errore caricamento dati: {e}")
    st.stop()

# --- TAB SYSTEM ---
tab_ord, tab_trans = st.tabs(["📆 Pianificazione Ordinaria", "✈️ Trasferimento & Cambio Ciclo"])

# ==============================================================================
# TAB 1: PIANIFICAZIONE ORDINARIA (Con Storicizzazione Squadra)
# ==============================================================================
with tab_ord:
    st.subheader("Inserimento Turno (Squadra)")
    
    if not lista_turni or not lista_squadre:
        st.warning("Configurazione incompleta (mancano turni o squadre).")
    else:
        # Selettore Modalità
        tipo_inserimento = st.radio(
            "Modalità Inserimento",
            ["Standard (da Turni Predefiniti)", "Custom (Orario Manuale)"],
            horizontal=True,
            label_visibility="collapsed",
            key="tipo_ins_ord"
        )

        with st.form("planning_form_ord"):
            c1, c2 = st.columns(2)
            
            # Variabili default per Custom
            d_custom_start = date.today()
            t_custom_start = time(8, 0)
            d_custom_end = date.today()
            t_custom_end = time(13, 0)

            with c1:
                if tipo_inserimento == "Standard (da Turni Predefiniti)":
                    d_sel = st.date_input("Data Inizio", date.today())
                    opts_t = {t['id_turno']: f"{t['nome_turno']} ({t['ora_inizio']}-{t['ora_fine']})" for t in lista_turni}
                    t_sel_id = st.selectbox("Turno Standard", options=opts_t.keys(), format_func=lambda x: opts_t[x])
                else:
                    st.markdown("**Orario Manuale**")
                    sc1, sc2 = st.columns(2)
                    with sc1:
                        d_custom_start = st.date_input("Data Inizio", date.today(), key="d_cs")
                        d_custom_end = st.date_input("Data Fine", date.today(), key="d_ce")
                    with sc2:
                        t_custom_start = st.time_input("Ora Inizio", time(8,0), key="t_cs")
                        t_custom_end = st.time_input("Ora Fine", time(13,0), key="t_ce")

            with c2:
                # Caricamento Attività
                opts_att = {
                    "VIAGGIO": "VIAGGIO (Trasferta)",
                    "STRAORDINARIO": "STRAORDINARIO (Generico)",
                    "OFFICINA": "OFFICINA (Lavoro Interno)",
                    "-1": "--- NESSUNA ATTIVITÀ SPECIFICA ---"
                }
                if not df_schedule.empty:
                    opts_att.update({r['id_attivita']: f"({r['id_attivita']}) {r.get('descrizione','N/D')}" for _, r in df_schedule.iterrows()})
                
                a_sel_id = st.selectbox("Attività", options=opts_att.keys(), format_func=lambda x: opts_att.get(x, x))
                
                # Selezione Squadra
                opts_sq = {s['id_squadra']: s['nome_squadra'] for s in lista_squadre}
                s_sel_id = st.selectbox("Squadra", options=opts_sq.keys(), format_func=lambda x: opts_sq[x])

            note_ord = st.text_input("Note Pianificazione")
            
            # --- POLICY CONFLITTI ---
            st.markdown("---")
            st.markdown("**⚠️ Gestione Conflitti (Se un operaio ha già un turno in questo orario):**")
            conflict_mode = st.radio(
                "Policy Conflitti",
                ["🛑 Blocca tutto (Errore)", "⏭️ Salta chi è occupato", "✏️ Sovrascrivi (Forza Inserimento)"],
                horizontal=True,
                index=0,
                key="conflict_mode_radio"
            )
            
            # Mappatura per il Service Layer
            policy_map = {
                "🛑 Blocca tutto (Errore)": "error",
                "⏭️ Salta chi è occupato": "skip",
                "✏️ Sovrascrivi (Forza Inserimento)": "overwrite"
            }
            
            if st.form_submit_button("🚀 Pianifica Turno", type="primary", use_container_width=True):
                # 1. Calcolo Orari
                try:
                    if tipo_inserimento == "Standard (da Turni Predefiniti)":
                        t_obj = next(t for t in lista_turni if t['id_turno'] == t_sel_id)
                        start_t = datetime.strptime(t_obj['ora_inizio'], '%H:%M:%S').time()
                        end_t = datetime.strptime(t_obj['ora_fine'], '%H:%M:%S').time()
                        dt_start_eff = datetime.combine(d_sel, start_t)
                        dt_end_eff = datetime.combine(d_sel + timedelta(days=1) if t_obj['scavalca_mezzanotte'] else d_sel, end_t)
                    else:
                        dt_start_eff = datetime.combine(d_custom_start, t_custom_start)
                        dt_end_eff = datetime.combine(d_custom_end, t_custom_end)
                        if dt_start_eff >= dt_end_eff:
                            st.error("Errore: La fine del turno deve essere successiva all'inizio.")
                            st.stop()
                    
                    # 2. Recupero Membri
                    membri = shift_service.get_membri_squadra(s_sel_id)
                    if not membri:
                        st.error("Squadra vuota! Aggiungi membri in 'Gestione Squadre'.")
                        st.stop()

                    # 3. Preparazione Batch CON ID SQUADRA (Storicizzazione)
                    att_db = a_sel_id if a_sel_id != "-1" else None
                    batch = [{
                        "id_dipendente": m,
                        "id_squadra": s_sel_id, # <--- FONDAMENTALE: Storicizza la squadra del turno
                        "id_attivita": att_db,
                        "data_ora_inizio": dt_start_eff,
                        "data_ora_fine": dt_end_eff,
                        "note": note_ord
                    } for m in membri]
                    
                    # 4. Chiamata al Service con Policy
                    policy_code = policy_map[conflict_mode]
                    results = shift_service.create_shifts_batch(batch, conflict_policy=policy_code)
                    
                    # 5. Analisi Risultati
                    msg = f"✅ Operazione conclusa.\n- **Creati:** {results['created']} segmenti."
                    
                    if results['skipped']:
                        msg += f"\n- **Saltati (Già Occupati):** {len(results['skipped'])} operai (Policy: Skip)."
                    
                    if results['overwritten']:
                        msg += f"\n- **Sovrascritti (Turni Cancellati):** {len(results['overwritten'])} operai (Policy: Overwrite)."
                    
                    # Feedback visuale
                    if results['created'] > 0 or results['overwritten']:
                        st.success(msg)
                        st.cache_data.clear()
                        
                        # Riepilogo visivo
                        with st.container(border=True):
                            rc1, rc2 = st.columns(2)
                            with rc1:
                                st.write(f"**Squadra:** {opts_sq[s_sel_id]}")
                                st.write(f"**Inizio:** {dt_start_eff.strftime('%d/%m %H:%M')}")
                            with rc2:
                                st.write(f"**Attività:** {opts_att.get(a_sel_id)}")
                                st.write(f"**Fine:** {dt_end_eff.strftime('%d/%m %H:%M')}")
                    else:
                        st.warning(msg + "\nNessun turno è stato inserito.")

                except Exception as e:
                    st.error(f"Errore: {e}")

# ==============================================================================
# TAB 2: TRASFERIMENTO & CAMBIO CICLO (HR Transfer)
# ==============================================================================
with tab_trans:
    st.subheader("Gestione HR: Trasferimento & Transizione")
    st.markdown("""
    Questa procedura esegue un **Cambio Squadra Strutturale** gestendo i turni di raccordo.
    Il sistema applicherà una **Smart Delete**: cancellerà solo i turni futuri, preservando lo storico.
    """)
    
    with st.container(border=True):
        col_pers, col_dest = st.columns(2)
        
        with col_pers:
            dip_opts = {row.name: f"{row['cognome']} {row['nome']} ({row['ruolo']})" for _, row in df_dipendenti.iterrows()}
            target_dip_id = st.selectbox("Seleziona Operaio da Trasferire", options=list(dip_opts.keys()), format_func=lambda x: dip_opts[x])
            
        with col_dest:
            opts_sq_trans = {s['id_squadra']: s['nome_squadra'] for s in lista_squadre}
            target_team_id = st.selectbox("Nuova Squadra di Destinazione", options=opts_sq_trans.keys(), format_func=lambda x: opts_sq_trans[x])
        
        c3, c4 = st.columns(2)
        with c3:
            d_change = st.date_input("Data del Trasferimento", date.today(), key="d_trans")
        with c4:
            proto = st.radio("Direzione Transizione", ["☀️ ➔ 🌙  DA GIORNO A NOTTE", "🌙 ➔ ☀️  DA NOTTE A GIORNO"], key="proto_trans")
            
        st.divider()
        
        if proto == "☀️ ➔ 🌙  DA GIORNO A NOTTE":
            st.info("""
            **Protocollo G>N (10h Totali):**
            1. **08:00 - 14:00** (6h): Chiusura turno diurno.
            2. **20:00 - 06:00** (4h su oggi): Inizio ciclo notturno.
            *HR: L'operaio viene spostato nella Squadra Notte.*
            """)
            code = 'DAY_TO_NIGHT'
        else:
            st.info("""
            **Protocollo N>G (10h Totali):**
            1. **20:00 - 02:00** (6h): Notte Corta (anticipa riposo).
            2. **08:00 - 18:00** (Domani): Primo turno diurno standard.
            *HR: L'operaio viene spostato nella Squadra Giorno.*
            """)
            code = 'NIGHT_TO_DAY'

        if st.button("🔄 Esegui Trasferimento e Cambio Ciclo", type="primary", use_container_width=True):
            try:
                shift_service.execute_team_transfer(target_dip_id, target_team_id, code, d_change)
                
                st.success(f"✅ Trasferimento completato: {dip_opts[target_dip_id]} è ora nella squadra {opts_sq_trans[target_team_id]}.")
                st.info("I turni di raccordo sono stati generati e i turni futuri sono stati riallineati.")
                st.cache_data.clear() 
                
            except Exception as e:
                st.error(f"Errore durante il trasferimento: {e}")