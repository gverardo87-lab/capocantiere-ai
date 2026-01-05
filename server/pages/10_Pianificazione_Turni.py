# file: server/pages/10_Pianificazione_Turni.py (Versione 33.5 - Fix Reattività Squadra)
from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from collections import Counter

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare i moduli: {e}")
    st.stop()

st.set_page_config(page_title="Pianificazione Turni", page_icon="📅", layout="wide")

# --- CSS LEADER STYLE ---
st.markdown("""
<style>
    .kpi-box {
        background-color: rgba(128, 128, 128, 0.05);
        border-radius: 8px; padding: 10px; text-align: center;
        border: 1px solid rgba(128, 128, 128, 0.1);
    }
    .kpi-num { font-size: 1.5rem; font-weight: 700; }
    .kpi-txt { font-size: 0.8rem; opacity: 0.8; text-transform: uppercase; }
    .role-badge { 
        background-color: rgba(128, 128, 128, 0.1); padding: 2px 6px; 
        border-radius: 4px; font-size: 0.8em; margin-right: 4px; border: 1px solid rgba(128, 128, 128, 0.2);
    }
</style>
""", unsafe_allow_html=True)

st.title("📅 Pianificazione Turni & Cicli")
st.markdown("Gestione integrata: Pianificazione Ordinaria (Squadre/Custom) e Gestione HR (Trasferimenti/Cambi Ciclo).")

# --- HELPER: RUOLI ESSENZIALI ---
def get_role_metadata(role_name: str) -> tuple[str, int]:
    if not isinstance(role_name, str): return "👷", 9
    r = role_name.lower()
    if 'capo' in r or 'preposto' in r: return "👑", 0
    if 'saldat' in r: return "👨‍🏭", 1
    if 'carpent' in r: return "🔨", 1
    return "👷", 9

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=30)
def load_data():
    turni = shift_service.get_turni_standard()
    squadre = shift_service.get_squadre()
    df_dip = shift_service.get_dipendenti_df(solo_attivi=True)
    
    # Map per visualizzazione nomi
    dip_map = {}
    role_map = {}
    for index, row in df_dip.iterrows():
        ruolo = row['ruolo'] if pd.notna(row['ruolo']) else "N/D"
        icon, _ = get_role_metadata(ruolo)
        dip_map[index] = f"{row['cognome']} {row['nome']} | {icon} {ruolo}"
        role_map[index] = ruolo

    df_sched = st.session_state.get('df_schedule', pd.DataFrame())
    if df_sched.empty:
        try:
            s_data = schedule_db_manager.get_schedule_data()
            df_sched = pd.DataFrame(s_data)
            st.session_state.df_schedule = df_sched
        except Exception as e:
            # print(f"Errore schedule: {e}") 
            df_sched = pd.DataFrame()

    return turni, squadre, df_dip, dip_map, role_map, df_sched

try:
    lista_turni, lista_squadre, df_dipendenti, dipendenti_map, dip_role_map, df_schedule = load_data()
    # Dizionario rapido per le squadre
    opts_sq = {s['id_squadra']: s['nome_squadra'] for s in lista_squadre}
except Exception as e:
    st.error(f"Errore caricamento dati: {e}")
    st.stop()

# --- TAB SYSTEM ---
tab_ord, tab_trans = st.tabs(["📆 Pianificazione Ordinaria", "✈️ Trasferimento & Cambio Ciclo"])

# ==============================================================================
# TAB 1: PIANIFICAZIONE ORDINARIA (Con Composizione Dinamica)
# ==============================================================================
with tab_ord:
    # --- KPI DASHBOARD ---
    try:
        today_shifts = shift_service.get_turni_master_giorno_df(date.today())
        shifts_count = len(today_shifts)
        men_deployed = today_shifts['id_dipendente'].nunique() if not today_shifts.empty else 0
    except: shifts_count, men_deployed = 0, 0

    c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
    c_kpi1.markdown(f"<div class='kpi-box'><div class='kpi-num'>{date.today().strftime('%d/%m')}</div><div class='kpi-txt'>Data Odierna</div></div>", unsafe_allow_html=True)
    c_kpi2.markdown(f"<div class='kpi-box'><div class='kpi-num'>{shifts_count}</div><div class='kpi-txt'>Turni Attivi</div></div>", unsafe_allow_html=True)
    c_kpi3.markdown(f"<div class='kpi-box'><div class='kpi-num'>{men_deployed}</div><div class='kpi-txt'>Uomini in Campo</div></div>", unsafe_allow_html=True)
    st.divider()

    st.subheader("Configurazione Turno")
    
    if not lista_turni or not lista_squadre:
        st.warning("Configurazione incompleta (mancano turni o squadre).")
    else:
        # --- BLOCCO 1: SELEZIONE CONTESTO (FUORI DAL FORM PER REATTIVITÀ) ---
        # Questo permette che quando cambi squadra, la pagina si aggiorni subito con i membri giusti.
        
        c_mode = st.container()
        col_ctx_1, col_ctx_2 = st.columns(2)
        
        # Variabili che devono essere accessibili dopo
        d_sel = date.today()
        t_sel_id = None
        d_custom_start, d_custom_end = date.today(), date.today()
        t_custom_start, t_custom_end = time(8, 0), time(13, 0)
        
        with col_ctx_1:
            tipo_inserimento = st.radio(
                "Modalità Inserimento",
                ["Standard (da Turni Predefiniti)", "Custom (Orario Manuale)"],
                horizontal=True,
                label_visibility="collapsed"
            )

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

        with col_ctx_2:
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
            
            # ★ CRUCIALE: Questo è fuori dal form, quindi aggiorna membri_standard_ids SUBITO ★
            s_sel_id = st.selectbox("Squadra di Riferimento", options=opts_sq.keys(), format_func=lambda x: opts_sq[x])

        # Recupero immediato dei membri (reattivo)
        membri_standard_ids = shift_service.get_membri_squadra(s_sel_id)

        # --- BLOCCO 2: COMPOSIZIONE & INVIO (DENTRO IL FORM) ---
        st.markdown("---")
        st.markdown("##### 👷 Composizione e Conferma")
        
        with st.form("planning_form_ord"):
            # Composizione Dinamica
            cd1, cd2 = st.columns(2)
            with cd1:
                # Multiselect pre-compilata: permette di DESELEZIONARE gli assenti
                membri_confermati = st.multiselect(
                    "Membri Presenti (Deseleziona assenti)",
                    options=membri_standard_ids,
                    default=membri_standard_ids,
                    format_func=lambda x: dipendenti_map.get(x, f"ID {x}")
                )
            
            with cd2:
                # Filtro e Jolly
                all_roles = sorted(list(set([r for r in dip_role_map.values() if r])))
                # Nota: Il filtro è visivo qui, ma essendo nel form non ricarica la pagina. 
                # Per i jolly va bene mostrare tutto o usare un expander se la lista è lunga.
                # Se volessimo il filtro reattivo anche qui, dovremmo portarlo fuori dal form.
                # Per ora manteniamo la lista completa per semplicità nel form.
                
                altri_dipendenti = [d for d in df_dipendenti.index if d not in membri_standard_ids]
                
                sostituti_selezionati = st.multiselect(
                    "Aggiungi Sostituti / Jolly (da altre squadre)",
                    options=altri_dipendenti,
                    format_func=lambda x: dipendenti_map.get(x, f"ID {x}")
                )

            # Lista definitiva
            membri_finali = list(set(membri_confermati + sostituti_selezionati))
            
            # Info Totale (Visualizzato prima del submit)
            st.caption(f"Operai selezionati per l'invio: **{len(membri_finali)}**")

            st.divider()
            note_ord = st.text_input("Note Pianificazione")
            
            # Policy Conflitti
            c_pol, c_sub = st.columns([2, 1])
            with c_pol:
                conflict_mode = st.radio(
                    "Gestione Conflitti",
                    ["🛑 Blocca tutto", "⏭️ Salta occupati", "✏️ Sovrascrivi"],
                    horizontal=True, index=0
                )
            
            policy_map = {"🛑 Blocca tutto": "error", "⏭️ Salta occupati": "skip", "✏️ Sovrascrivi": "overwrite"}
            
            with c_sub:
                st.write("") 
                submitted = st.form_submit_button("🚀 Pianifica Turno Operativo", type="primary", use_container_width=True)

            if submitted:
                # 1. Validazione
                if not membri_finali:
                    st.error("Errore: Nessun operaio selezionato.")
                    st.stop()

                # 2. Calcolo Orari (usando le variabili definite fuori dal form)
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
                            st.error("Errore: Fine < Inizio.")
                            st.stop()
                    
                    # 3. Preparazione Batch
                    att_db = a_sel_id if a_sel_id != "-1" else None
                    
                    batch = [{
                        "id_dipendente": m,
                        "id_squadra": s_sel_id, 
                        "id_attivita": att_db,
                        "data_ora_inizio": dt_start_eff,
                        "data_ora_fine": dt_end_eff,
                        "note": note_ord
                    } for m in membri_finali]
                    
                    # 4. Chiamata Service
                    results = shift_service.create_shifts_batch(batch, conflict_policy=policy_map[conflict_mode])
                    
                    # 5. Feedback
                    msg = f"✅ Turno creato per {results['created']} operai."
                    if results['skipped']: msg += f" (Saltati: {len(results['skipped'])})"
                    if results['overwritten']: msg += f" (Sovrascritti: {len(results['overwritten'])})"
                    
                    if results['created'] > 0 or results['overwritten']:
                        st.success(msg)
                        st.cache_data.clear() # Fondamentale per aggiornare i KPI
                    else:
                        st.warning(msg)

                except Exception as e:
                    st.error(f"Errore: {e}")

# ==============================================================================
# TAB 2: HR TRANSFER & CAMBIO CICLO (INVARIATO - CONSERVATIVO)
# ==============================================================================
with tab_trans:
    st.subheader("Gestione HR: Trasferimento Strutturale")
    st.info("Usa questa funzione per cambi di squadra PERMANENTI. Per prestiti di un giorno, usa il Tab 1.")
    
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
            **Protocollo G>N:** 08-14 (Giorno) + 20-06 (Notte).
            """)
            code = 'DAY_TO_NIGHT'
        else:
            st.info("""
            **Protocollo N>G:** 20-02 (Notte Corta) + 08-18 (Domani).
            """)
            code = 'NIGHT_TO_DAY'

        if st.button("🔄 Esegui Trasferimento Permanente", type="primary", use_container_width=True):
            try:
                shift_service.execute_team_transfer(target_dip_id, target_team_id, code, d_change)
                st.success(f"✅ Trasferimento completato per {dip_opts[target_dip_id]}.")
                st.cache_data.clear() 
            except Exception as e:
                st.error(f"Errore durante il trasferimento: {e}")