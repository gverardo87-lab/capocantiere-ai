# file: server/pages/13_✏️_Control_Room_Ore.py (Versione 16.0 - Architettura Service)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime, date, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    # ★ IMPORT CORRETTO ★
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare i moduli: {e}")
    st.stop()

st.set_page_config(page_title="Control Room Ore", page_icon="✏️", layout="wide")
st.title("✏️ Control Room - Gestione Turni Master")
st.markdown("Visualizza, modifica, o cancella gli interi turni di lavoro giornalieri.")

# --- 1. Selettore data e caricamento dati ---
st.subheader("Filtro Giornaliero")
selected_date = st.date_input("Seleziona il giorno da visualizzare", date.today(), key="control_room_date")

def load_turni_e_attivita(giorno: date):
    """Carica i TURNI MASTER e le attività tramite il service layer."""
    print(f"\n🔍 DEBUG: Caricamento TURNI MASTER per {giorno}")
    
    # ★ CHIAMATA CORRETTA al service ★
    df_turni_master = shift_service.get_turni_master_giorno_df(giorno)
    print(f"🔍 DEBUG: Trovati {len(df_turni_master)} turni master")
        
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
    if not df_turni_master.empty and 'id_attivita' in df_turni_master.columns:
        for id_att in df_turni_master['id_attivita'].unique():
            if id_att and id_att not in opzioni_attivita:
                opzioni_attivita[id_att] = f"({id_att}) - ATTIVITÀ PASSATA"
            
    return df_turni_master, opzioni_attivita

try:
    df_turni, opzioni_attivita = load_turni_e_attivita(selected_date)
except Exception as e:
    st.error(f"Errore nel caricamento dei turni: {e}")
    import traceback
    st.code(traceback.format_exc())
    st.stop()

# --- 2. Tabella Modificabile (Ora basata su Turni Master) ---
st.subheader(f"Turni Master attivi il {selected_date.strftime('%d/%m/%Y')}")

if df_turni.empty:
    st.info("Nessun turno di lavoro trovato per questo giorno.")
else:
    df_turni_copy = df_turni.copy()
    df_turni_copy['elimina'] = False
    
    edited_df = st.data_editor(
        df_turni_copy,
        key="editor_turni_master",
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "cognome": st.column_config.TextColumn("Cognome", disabled=True),
            "nome": st.column_config.TextColumn("Nome", disabled=True),
            "ruolo": st.column_config.TextColumn("Ruolo", disabled=True),
            "data_ora_inizio_effettiva": st.column_config.DatetimeColumn("Inizio Turno", format="DD/MM/YYYY HH:mm", required=True),
            "data_ora_fine_effettiva": st.column_config.DatetimeColumn("Fine Turno", format="DD/MM/YYYY HH:mm", required=True),
            "id_attivita": st.column_config.SelectboxColumn("Attività", options=opzioni_attivita.keys(), required=True),
            "note": st.column_config.TextColumn("Note"),
            "durata_ore": st.column_config.NumberColumn("Ore Totali", format="%.2f h", disabled=True),
            "id_dipendente": None,
            "elimina": st.column_config.CheckboxColumn("Elimina?", default=False)
        },
        disabled=["cognome", "nome", "ruolo", "durata_ore"]
    )

    # --- LOGICA DI SALVATAGGIO ---
    if st.button("Salva Modifiche ed Eliminazioni", type="primary"):
        eliminati_count = 0
        aggiornati_count = 0
        errori = []
        
        try:
            # 1. ELIMINAZIONI
            da_eliminare_ids = edited_df[edited_df['elimina'] == True].index.tolist()
            for id_master in da_eliminare_ids:
                try:
                    # ★ CHIAMATA CORRETTA al service ★
                    shift_service.delete_master_shift(int(id_master))
                    eliminati_count += 1
                except Exception as e:
                    errori.append(f"Eliminazione turno {id_master}: {e}")
            
            # --- 2. MODIFICHE ---
            df_modifiche = edited_df[edited_df['elimina'] == False]
            df_originali = df_turni[df_turni.index.isin(df_modifiche.index)]
            modifiche_reali_ids = []

            for id_master in df_modifiche.index:
                if id_master not in df_originali.index: continue
                riga_modificata = df_modifiche.loc[id_master]
                riga_originale = df_originali.loc[id_master]
                
                is_changed = False
                if pd.to_datetime(riga_modificata['data_ora_inizio_effettiva']) != riga_originale['data_ora_inizio_effettiva']:
                    is_changed = True
                elif pd.to_datetime(riga_modificata['data_ora_fine_effettiva']) != riga_originale['data_ora_fine_effettiva']:
                    is_changed = True
                elif str(riga_modificata.get('id_attivita') or '') != str(riga_originale.get('id_attivita') or ''):
                    is_changed = True
                elif str(riga_modificata.get('note') or '') != str(riga_originale.get('note') or ''):
                    is_changed = True
                    
                if is_changed:
                    modifiche_reali_ids.append(id_master)
            
            for id_master in modifiche_reali_ids:
                row = df_modifiche.loc[id_master]
                try:
                    start_dt = pd.to_datetime(row['data_ora_inizio_effettiva']).to_pydatetime()
                    end_dt = pd.to_datetime(row['data_ora_fine_effettiva']).to_pydatetime()
                    
                    if pd.isna(start_dt) or pd.isna(end_dt) or start_dt >= end_dt:
                        errori.append(f"Turno {id_master} ({row['cognome']}): Date non valide o inizio >= fine")
                        continue
                    
                    # ★ CHIAMATA CORRETTA al service ★
                    shift_service.update_master_shift(
                        id_turno_master=int(id_master),
                        new_start=start_dt,
                        new_end=end_dt,
                        new_id_attivita=row.get('id_attivita') or '-1',
                        new_note=row.get('note')
                    )
                    aggiornati_count += 1
                    
                except ValueError as ve: 
                    errori.append(f"Turno {id_master} ({row['cognome']}): {str(ve)}")
                except Exception as e:
                    errori.append(f"Turno {id_master} ({row['cognome']}): Errore - {str(e)}")

            if aggiornati_count > 0 or eliminati_count > 0:
                st.success(f"✅ Operazione completata: {aggiornati_count} aggiornamenti, {eliminati_count} eliminazioni")
            elif not errori:
                st.info("Nessuna modifica rilevata.")
            
            if errori:
                with st.expander(f"⚠️ {len(errori)} operazioni non riuscite", expanded=True):
                    for err in errori:
                        st.warning(err)
            
            if aggiornati_count > 0 or eliminati_count > 0:
                st.cache_data.clear()
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Errore critico: {e}")
            import traceback
            st.code(traceback.format_exc())

st.divider()

# --- 3. Gestione Interruzioni ---
st.subheader("🛑 Gestione Interruzioni di Cantiere")

if df_turni.empty:
    st.info("Nessuna registrazione da modificare.")
else:
    with st.form("interruzione_form"):
        opzioni_turni = {}
        for id_master, row in edited_df[edited_df['elimina'] == False].iterrows():
            try:
                inizio_str = pd.to_datetime(row['data_ora_inizio_effettiva']).strftime('%H:%M')
                fine_str = pd.to_datetime(row['data_ora_fine_effettiva']).strftime('%H:%M')
                orario_str = f"({inizio_str} - {fine_str})"
            except Exception:
                orario_str = "(Orario non valido)"
            
            opzioni_turni[id_master] = f"{row['cognome']} {row['nome']} {orario_str}"

        ids_selezionati = st.multiselect(
            "Seleziona i turni master da splittare", 
            options=opzioni_turni.keys(), 
            format_func=lambda x: opzioni_turni.get(x, "N/A")
        )
        
        col1, col2 = st.columns(2)
        with col1:
            ora_inizio_interruzione = st.time_input("Ora Inizio Interruzione", time(14, 0))
        with col2:
            ora_fine_interruzione = st.time_input("Ora Fine Interruzione", time(15, 0))
        
        submitted_interruzione = st.form_submit_button("Applica Interruzione (Divide i Turni)", use_container_width=True)
        
        if submitted_interruzione:
            if not ids_selezionati:
                st.warning("Nessun turno selezionato.")
            elif ora_inizio_interruzione >= ora_fine_interruzione:
                st.warning("L'ora di fine interruzione deve essere successiva all'ora di inizio.")
            else:
                dt_inizio_interruzione = datetime.combine(selected_date, ora_inizio_interruzione)
                dt_fine_interruzione = datetime.combine(selected_date, ora_fine_interruzione)
                
                success_count = 0
                fail_count = 0
                
                with st.spinner("Applicazione interruzioni in corso..."):
                    for id_master in ids_selezionati:
                        try:
                            # ★ CHIAMATA CORRETTA al service ★
                            shift_service.split_master_shift_for_interruption(
                                int(id_master), 
                                dt_inizio_interruzione, 
                                dt_fine_interruzione
                            )
                            success_count += 1
                        except Exception as e:
                            st.error(f"Errore turno {id_master} ({opzioni_turni[id_master]}): {e}")
                            fail_count += 1
                
                st.success(f"Interruzione applicata! {success_count} turni splittati, {fail_count} fallimenti.")
                
                if success_count > 0:
                    st.cache_data.clear()
                    st.rerun()