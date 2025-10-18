# file: server/pages/13_✏️_Control_Room_Ore.py (Versione 14.0 - FIX CACHE + DEBUG)

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
st.markdown("Visualizza, modifica, o cancella le singole registrazioni ore. Gestisci le interruzioni di cantiere.")

# --- 1. Selettore data e caricamento dati ---
st.subheader("Filtro Giornaliero")
selected_date = st.date_input("Seleziona il giorno da visualizzare", date.today(), key="control_room_date")

# ✅ RIMOSSA CACHE - Caricamento sempre fresco
def load_registrazioni(giorno: date):
    """Carica le registrazioni per il giorno selezionato - SEMPRE FRESCO."""
    print(f"\n🔍 DEBUG: Caricamento registrazioni per {giorno}")
    
    df = crm_db_manager.get_registrazioni_giorno_df(giorno)
    print(f"🔍 DEBUG: Trovate {len(df)} registrazioni")
    
    if not df.empty:
        print(f"🔍 DEBUG: Prima registrazione: {df.iloc[0]['cognome']} {df.iloc[0]['nome']} - {df.iloc[0]['data_ora_inizio']} / {df.iloc[0]['data_ora_fine']}")
    
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
    
    # Salva sempre una copia fresca
    st.session_state.original_df_to_compare = df_registrazioni.copy()
    st.session_state.current_date = selected_date

except Exception as e:
    st.error(f"Errore nel caricamento delle registrazioni: {e}")
    import traceback
    st.code(traceback.format_exc())
    st.stop()

# --- 2. Tabella Modificabile ---
st.subheader(f"Registrazioni per il {selected_date.strftime('%d/%m/%Y')}")

if df_registrazioni.empty:
    st.info("Nessuna registrazione trovata per questo giorno. Pianifica un turno dalla pagina 'Pianificazione Turni'.")
    
    # ✅ DEBUG: Mostra cosa sta cercando il database
    with st.expander("🔍 DEBUG: Info Database"):
        try:
            # Query diretta al DB per vedere cosa c'è
            with crm_db_manager._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as total 
                    FROM registrazioni_ore 
                    WHERE data_ora_inizio IS NOT NULL 
                      AND data_ora_fine IS NOT NULL
                """)
                total = cursor.fetchone()['total']
                st.write(f"**Totale registrazioni nel DB**: {total}")
                
                cursor.execute("""
                    SELECT 
                        data_ora_inizio, 
                        data_ora_fine,
                        id_registrazione
                    FROM registrazioni_ore 
                    WHERE data_ora_inizio IS NOT NULL 
                      AND data_ora_fine IS NOT NULL
                    ORDER BY data_ora_inizio DESC
                    LIMIT 5
                """)
                recent = cursor.fetchall()
                st.write("**Ultime 5 registrazioni:**")
                for r in recent:
                    st.write(f"- ID {r['id_registrazione']}: {r['data_ora_inizio']} → {r['data_ora_fine']}")
        except Exception as e:
            st.error(f"Errore query debug: {e}")
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
            "data_ora_inizio": st.column_config.DatetimeColumn("Inizio", format="DD/MM/YYYY HH:mm", required=True),
            "data_ora_fine": st.column_config.DatetimeColumn("Fine", format="DD/MM/YYYY HH:mm", required=True),
            "id_attivita": st.column_config.SelectboxColumn("Attività", options=opzioni_attivita.keys()),
            "note": st.column_config.TextColumn("Note"),
            "durata_ore": st.column_config.NumberColumn("Ore", format="%.2f h", disabled=True),
            "id_dipendente": None,
            "elimina": st.column_config.CheckboxColumn("Elimina?", default=False)
        },
        disabled=["cognome", "nome", "ruolo", "durata_ore"]
    )

    # --- LOGICA DI SALVATAGGIO V14.0 CON DEBUG ---
    if st.button("Salva Modifiche ed Eliminazioni", type="primary"):
        eliminati_count = 0
        aggiornati_count = 0
        errori = []
        
        print("\n" + "="*50)
        print("🚀 INIZIO SALVATAGGIO")
        print("="*50)
        
        try:
            # 1. ELIMINAZIONI
            da_eliminare_ids = edited_df[edited_df['elimina'] == True].index.tolist()
            print(f"📋 Da eliminare: {len(da_eliminare_ids)} righe")
            
            for id_reg in da_eliminare_ids:
                try:
                    print(f"  🗑️ Eliminazione ID {id_reg}...")
                    crm_db_manager.delete_registrazione(int(id_reg))
                    eliminati_count += 1
                    print(f"  ✅ ID {id_reg} eliminato")
                except Exception as e:
                    print(f"  ❌ Errore eliminazione ID {id_reg}: {e}")
                    errori.append(f"Eliminazione riga {id_reg}: {e}")
            
            # 2. MODIFICHE
            df_modifiche = edited_df[edited_df['elimina'] == False].copy()
            print(f"\n📋 Da modificare: {len(df_modifiche)} righe")
            
            for id_reg, row in df_modifiche.iterrows():
                try:
                    print(f"\n  🔧 Modifica ID {id_reg}...")
                    
                    # Converti date
                    start_val = row['data_ora_inizio']
                    end_val = row['data_ora_fine']
                    
                    if isinstance(start_val, str):
                        start_dt = pd.to_datetime(start_val).to_pydatetime()
                    elif isinstance(start_val, pd.Timestamp):
                        start_dt = start_val.to_pydatetime()
                    else:
                        start_dt = start_val
                    
                    if isinstance(end_val, str):
                        end_dt = pd.to_datetime(end_val).to_pydatetime()
                    elif isinstance(end_val, pd.Timestamp):
                        end_dt = end_val.to_pydatetime()
                    else:
                        end_dt = end_val
                    
                    print(f"    📅 Nuovo orario: {start_dt} → {end_dt}")
                    
                    # Validazione
                    if pd.isna(start_dt) or pd.isna(end_dt):
                        print(f"    ❌ Date non valide")
                        errori.append(f"Riga {id_reg}: Date non valide")
                        continue
                    
                    if start_dt >= end_dt:
                        print(f"    ❌ Inizio >= Fine")
                        errori.append(f"Riga {id_reg}: Orario inizio >= fine")
                        continue
                    
                    # ✅ UPDATE
                    print(f"    💾 Chiamata update_full_registrazione...")
                    crm_db_manager.update_full_registrazione(
                        id_reg=int(id_reg),
                        start_time=start_dt,
                        end_time=end_dt,
                        id_att=row.get('id_attivita'),
                        note=row.get('note')
                    )
                    aggiornati_count += 1
                    print(f"    ✅ ID {id_reg} aggiornato con successo")
                    
                except ValueError as ve:
                    print(f"    ⚠️ Sovrapposizione: {ve}")
                    errori.append(f"Riga {id_reg}: {str(ve)}")
                except Exception as e:
                    print(f"    ❌ Errore: {e}")
                    errori.append(f"Riga {id_reg}: Errore - {str(e)}")
            
            print("\n" + "="*50)
            print(f"✅ COMPLETATO: {aggiornati_count} aggiornamenti, {eliminati_count} eliminazioni")
            print("="*50 + "\n")
            
            # ✅ FORZA RELOAD CACHE
            if 'original_df_to_compare' in st.session_state:
                del st.session_state.original_df_to_compare
            
            # Messaggio di successo
            if aggiornati_count > 0 or eliminati_count > 0:
                st.success(f"✅ Operazione completata: {aggiornati_count} aggiornamenti, {eliminati_count} eliminazioni")
            
            # Mostra errori
            if errori:
                with st.expander(f"⚠️ {len(errori)} operazioni non riuscite", expanded=True):
                    for err in errori:
                        st.warning(err)
            
            # ✅ RERUN SEMPRE (anche se ci sono errori parziali)
            if aggiornati_count > 0 or eliminati_count > 0:
                print("🔄 RERUN dell'applicazione...\n")
                st.rerun()
                
        except Exception as e:
            print(f"\n❌ ERRORE CRITICO: {e}")
            st.error(f"❌ Errore critico: {e}")
            import traceback
            st.code(traceback.format_exc())
            print(traceback.format_exc())

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
            "Seleziona registrazioni da splittare", 
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
                dt_inizio_interruzione = datetime.combine(selected_date, ora_inizio_interruzione)
                dt_fine_interruzione = datetime.combine(selected_date, ora_fine_interruzione)
                
                success_count = 0
                fail_count = 0
                
                with st.spinner("Applicazione interruzioni in corso..."):
                    for id_reg in ids_selezionati:
                        try:
                            crm_db_manager.split_registrazione_interruzione(
                                int(id_reg), 
                                dt_inizio_interruzione, 
                                dt_fine_interruzione
                            )
                            success_count += 1
                        except Exception as e:
                            st.error(f"Errore record {id_reg}: {e}")
                            fail_count += 1
                
                st.success(f"Interruzione applicata! {success_count} successi, {fail_count} fallimenti.")
                
                # Clear cache
                if 'original_df_to_compare' in st.session_state:
                    del st.session_state.original_df_to_compare
                
                st.rerun()