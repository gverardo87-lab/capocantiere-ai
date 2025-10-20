# file: server/pages/13_✏️_Control_Room_Ore.py (Versione 15.1 - FIX Cache)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime, date, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.crm_db import crm_db_manager
    from core.schedule_db import schedule_db_manager
except ImportError:
    st.error("Errore critico: Impossibile importare i moduli del database.")
    st.stop()

st.set_page_config(page_title="Control Room Ore", page_icon="✏️", layout="wide")
st.title("✏️ Control Room - Gestione Eccezioni")
st.markdown("Visualizza, modifica, o cancella i singoli segmenti di lavoro giornalieri.")

# --- 1. Selettore data e caricamento dati ---
st.subheader("Filtro Giornaliero")
selected_date = st.date_input("Seleziona il giorno da visualizzare", date.today(), key="control_room_date")

# ✅ Caricamento sempre fresco (no cache)
def load_registrazioni(giorno: date):
    """Carica i segmenti di registrazione per il giorno selezionato."""
    print(f"\n🔍 DEBUG: Caricamento registrazioni per {giorno}")
    
    # La query ora è semplificata e robusta grazie allo split
    df = crm_db_manager.get_registrazioni_giorno_df(giorno)
    print(f"🔍 DEBUG: Trovate {len(df)} registrazioni (segmenti)")
    
    if not df.empty:
        # Questo debug è utile per te:
        print(f"🔍 DEBUG: Prima registrazione: {df.iloc[0]['cognome']} {df.iloc[0]['nome']} - {df.iloc[0]['data_ora_inizio']} / {df.iloc[0]['data_ora_fine']} / Ore: {df.iloc[0]['durata_ore']}")
    
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
    st.session_state.current_date = selected_date

except Exception as e:
    st.error(f"Errore nel caricamento delle registrazioni: {e}")
    import traceback
    st.code(traceback.format_exc())
    st.stop()

# --- 2. Tabella Modificabile ---
st.subheader(f"Segmenti di Lavoro per il {selected_date.strftime('%d/%m/%Y')}")

if df_registrazioni.empty:
    st.info("Nessun segmento di lavoro trovato per questo giorno.")
else:
    df_registrazioni_copy = df_registrazioni.copy()
    df_registrazioni_copy['elimina'] = False
    
    edited_df = st.data_editor(
        df_registrazioni_copy,
        key="editor_registrazioni",
        use_container_width=True,
        num_rows="dynamic", 
        column_config={
            "cognome": st.column_config.TextColumn("Cognome", disabled=True),
            "nome": st.column_config.TextColumn("Nome", disabled=True),
            "ruolo": st.column_config.TextColumn("Ruolo", disabled=True),
            "data_ora_inizio": st.column_config.DatetimeColumn("Inizio Segmento", format="DD/MM/YYYY HH:mm", required=True),
            "data_ora_fine": st.column_config.DatetimeColumn("Fine Segmento", format="DD/MM/YYYY HH:mm", required=True),
            "id_attivita": st.column_config.SelectboxColumn("Attività", options=opzioni_attivita.keys()),
            "note": st.column_config.TextColumn("Note"),
            "durata_ore": st.column_config.NumberColumn("Ore", format="%.2f h", disabled=True),
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
            for id_reg in da_eliminare_ids:
                try:
                    crm_db_manager.delete_registrazione(int(id_reg))
                    eliminati_count += 1
                except Exception as e:
                    errori.append(f"Eliminazione riga {id_reg}: {e}")
            
            # 2. MODIFICHE
            df_modifiche = edited_df[edited_df['elimina'] == False].copy()
            for id_reg, row in df_modifiche.iterrows():
                try:
                    start_val = row['data_ora_inizio']
                    end_val = row['data_ora_fine']
                    
                    if isinstance(start_val, str): start_dt = pd.to_datetime(start_val).to_pydatetime()
                    elif isinstance(start_val, pd.Timestamp): start_dt = start_val.to_pydatetime()
                    else: start_dt = start_val
                    
                    if isinstance(end_val, str): end_dt = pd.to_datetime(end_val).to_pydatetime()
                    elif isinstance(end_val, pd.Timestamp): end_dt = end_val.to_pydatetime()
                    else: end_dt = end_val
                    
                    if pd.isna(start_dt) or pd.isna(end_dt):
                        errori.append(f"Riga {id_reg}: Date non valide")
                        continue
                    
                    if start_dt >= end_dt:
                        errori.append(f"Riga {id_reg}: Orario inizio >= fine")
                        continue
                    
                    # ✅ UPDATE (Ora "Split-Aware")
                    crm_db_manager.update_full_registrazione(
                        id_reg=int(id_reg),
                        start_time=start_dt,
                        end_time=end_dt,
                        id_att=row.get('id_attivita'),
                        note=row.get('note')
                    )
                    aggiornati_count += 1
                    
                except ValueError as ve: # Sovrapposizioni o altri errori di logica
                    errori.append(f"Riga {id_reg}: {str(ve)}")
                except Exception as e:
                    errori.append(f"Riga {id_reg}: Errore - {str(e)}")
            
            # Messaggio di successo
            if aggiornati_count > 0 or eliminati_count > 0:
                st.success(f"✅ Operazione completata: {aggiornati_count} aggiornamenti, {eliminati_count} eliminazioni")
            
            if errori:
                with st.expander(f"⚠️ {len(errori)} operazioni non riuscite", expanded=True):
                    for err in errori:
                        st.warning(err)
            
            if aggiornati_count > 0 or eliminati_count > 0:
                # --- ★★★ MICROMIGLIORAMENTO ★★★ ---
                # Pulisce la cache di tutta l'app per forzare
                # il ricalcolo della 'durata_ore' al rerun.
                st.cache_data.clear()
                # ------------------------------------
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Errore critico: {e}")
            import traceback
            st.code(traceback.format_exc())

st.divider()

# --- 3. Gestione Interruzioni ---
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

        ids_selezionati = st.multiselect(
            "Seleziona segmenti da splittare", 
            options=opzioni_dipendenti.keys(), 
            format_func=lambda x: opzioni_dipendenti.get(x, "N/A")
        )
        
        col1, col2 = st.columns(2)
        with col1:
            ora_inizio_interruzione = st.time_input("Ora Inizio Interruzione", time(14, 0))
        with col2:
            ora_fine_interruzione = st.time_input("Ora Fine Interruzione", time(15, 0))
        
        submitted_interruzione = st.form_submit_button("Applica Interruzione", use_container_width=True)
        
        if submitted_interruzione:
            if not ids_selezionati:
                st.warning("Nessuna registrazione selezionata.")
            elif ora_inizio_interruzione >= ora_fine_interruzione:
                st.warning("L'ora di fine interruzione deve essere successiva all'ora di inizio.")
            else:
                # L'interruzione avviene nello stesso giorno selezionato
                dt_inizio_interruzione = datetime.combine(selected_date, ora_inizio_interruzione)
                dt_fine_interruzione = datetime.combine(selected_date, ora_fine_interruzione)
                
                success_count = 0
                fail_count = 0
                
                with st.spinner("Applicazione interruzioni in corso..."):
                    for id_reg in ids_selezionati:
                        try:
                            # La funzione DB ora è robusta
                            crm_db_manager.split_registrazione_interruzione(
                                int(id_reg), 
                                dt_inizio_interruzione, 
                                dt_fine_interruzione
                            )
                            success_count += 1
                        except Exception as e:
                            st.error(f"Errore record {id_reg} ({opzioni_dipendenti[id_reg]}): {e}")
                            fail_count += 1
                
                st.success(f"Interruzione applicata! {success_count} successi, {fail_count} fallimenti.")
                
                if success_count > 0:
                    # --- ★★★ MICROMIGLIORAMENTO ★★★ ---
                    # Pulisce la cache anche qui per
                    # mostrare i nuovi segmenti splittati.
                    st.cache_data.clear()
                    # ------------------------------------
                    st.rerun()