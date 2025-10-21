# file: server/pages/14_Riepilogo_Calendario.py (NUOVO - Versione 16.3)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from typing import Dict, List

# Aggiungiamo la root del progetto al path per importare i moduli 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    # Importiamo solo il service layer
    from core.shift_service import shift_service
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare `core.shift_service`: {e}")
    st.stop()

st.set_page_config(page_title="Calendario Pianificazione", page_icon="🗓️", layout="wide")
st.title("🗓️ Calendario Pianificazione Turni")
st.markdown("Visione d'insieme (stile calendario) dei turni pianificati per Squadra o per Dipendente.")

# --- 1. FILTRO SETTIMANALE E VISTA ---
with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Seleziona la Settimana")
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday()) # Trova Lunedì
        selected_monday = st.date_input("Lunedì della settimana", value=start_of_week)
        
    with col2:
        st.subheader("Seleziona la Vista")
        view_mode = st.radio(
            "Visualizza per:",
            ["Squadra", "Dipendente"],
            horizontal=True,
            label_visibility="collapsed"
        )

start_date = selected_monday
end_date = selected_monday + timedelta(days=6) # Fino a Domenica

st.info(f"Visualizzazione dei turni che **iniziano** da **Lunedì {start_date.strftime('%d/%m')}** a **Domenica {end_date.strftime('%d/%m')}**.")

# --- 2. CARICAMENTO DATI PER L'INTERVALLO ---
@st.cache_data(ttl=60)
def load_calendar_data(start, end):
    """Carica turni, squadre, membri e dipendenti."""
    df_turni = shift_service.get_turni_master_range_df(start, end)
    squadre = shift_service.get_squadre()
    df_dipendenti = shift_service.get_dipendenti_df(solo_attivi=False)
    
    # Costruisci la mappa dipendente -> squadra (basata sulla definizione ATTUALE della squadra)
    dip_squadra_map = {}
    for squadra in squadre:
        membri_ids = shift_service.get_membri_squadra(squadra['id_squadra'])
        for id_dip in membri_ids:
            dip_squadra_map[id_dip] = squadra['nome_squadra']
            
    # Mappa per nome dipendente
    dip_nome_map = df_dipendenti.apply(lambda x: f"{x['cognome']} {x['nome']}", axis=1).to_dict()
            
    return df_turni, dip_squadra_map, dip_nome_map

try:
    with st.spinner("Caricamento dati calendario..."):
        df_turni, dip_squadra_map, dip_nome_map = load_calendar_data(start_date, end_date)
except Exception as e:
    st.error(f"Errore nel caricamento dati: {e}")
    st.stop()

if df_turni.empty:
    st.warning("Nessun turno pianificato trovato per la settimana selezionata.")
    st.stop()

# --- 3. PREPARAZIONE DATI PER PIVOT ---

# Crea la colonna 'giorno' (solo data)
df_turni['giorno'] = df_turni['data_ora_inizio_effettiva'].dt.date

# Crea la stringa visuale per il turno (stile Google Calendar)
df_turni['turno_info'] = df_turni.apply(
    lambda row: f"{row['data_ora_inizio_effettiva'].strftime('%H:%M')}-"
                f"{row['data_ora_fine_effettiva'].strftime('%H:%M')} "
                f"({row.get('id_attivita', 'N/A')})",
    axis=1
)

# Aggiungi le colonne per le viste
df_turni['squadra'] = df_turni['id_dipendente'].map(dip_squadra_map).fillna("Non Assegnato")
df_turni['dipendente_nome'] = df_turni['id_dipendente'].map(dip_nome_map).fillna("Sconosciuto")

# Lista completa dei giorni della settimana
week_days = [start_date + timedelta(days=i) for i in range(7)]

# --- 4. FUNZIONE DI STYLING PER CELLE ---
def highlight_cells(val):
    """Colora le celle che non sono vuote per assomigliare a un calendario."""
    if val != '-' and val != 0:
        return 'background-color: #1C2A44' # Colore secondario del tema
    return ''

# --- 5. VISUALIZZAZIONE DINAMICA (Squadra o Dipendente) ---

if view_mode == "Squadra":
    st.header("📅 Calendario per Squadra")
    
    # Lista delle squadre che hanno lavorato o sono definite
    squadre_index = sorted(list(set(df_turni['squadra'].unique())))
    
    # --- PIVOT PER I TURNI ---
    st.subheader("Turni Pianificati")
    st.markdown("Visualizza l'attività principale per ogni squadra, ogni giorno.")
    
    df_pivot_turni_squadra = df_turni.pivot_table(
        index='squadra',
        columns='giorno',
        values='turno_info',
        aggfunc='first', # Mostra il primo turno pianificato per la squadra
        fill_value='-'
    ).reindex(index=squadre_index, columns=week_days, fill_value='-')
    
    df_pivot_turni_squadra.columns = [col.strftime('%a %d/%m') for col in df_pivot_turni_squadra.columns]
    
    st.dataframe(
        df_pivot_turni_squadra.style.applymap(highlight_cells),
        use_container_width=True
    )

    # --- PIVOT PER LE ORE ---
    st.subheader("Monte Ore Settimanale (per Squadra)")
    st.markdown("Somma delle ore lavorate da tutti i membri della squadra.")
    
    df_pivot_ore_squadra = df_turni.pivot_table(
        index='squadra',
        columns='giorno',
        values='durata_ore',
        aggfunc='sum',
        fill_value=0
    ).reindex(index=squadre_index, columns=week_days, fill_value=0)
    
    df_pivot_ore_squadra['TOTALE ORE'] = df_pivot_ore_squadra.sum(axis=1)
    df_pivot_ore_squadra.columns = [col.strftime('%a %d/%m') if isinstance(col, date) else col for col in df_pivot_ore_squadra.columns]
    
    st.dataframe(
        df_pivot_ore_squadra.style.format("{:.2f} h"),
        use_container_width=True
    )
    
else:
    st.header(f"📅 Calendario per Dipendente")
    
    # Lista dei dipendenti che hanno lavorato
    dipendenti_index = sorted(list(set(df_turni['dipendente_nome'].unique())))
    
    # --- PIVOT PER I TURNI ---
    st.subheader("Turni Pianificati")
    st.markdown("Visualizza il turno di ogni singolo dipendente.")
    
    df_pivot_turni_dip = df_turni.pivot_table(
        index=['squadra', 'dipendente_nome'], # Multi-indice per raggruppare per squadra
        columns='giorno',
        values='turno_info',
        aggfunc='first',
        fill_value='-'
    ).reindex(columns=week_days, fill_value='-')
    
    df_pivot_turni_dip.columns = [col.strftime('%a %d/%m') for col in df_pivot_turni_dip.columns]
    
    st.dataframe(
        df_pivot_turni_dip.style.applymap(highlight_cells),
        use_container_width=True
    )
    
    # --- PIVOT PER LE ORE ---
    st.subheader("Monte Ore Settimanale (per Dipendente)")
    st.markdown("Somma delle ore lavorate da ogni singolo dipendente.")
    
    df_pivot_ore_dip = df_turni.pivot_table(
        index=['squadra', 'dipendente_nome'],
        columns='giorno',
        values='durata_ore',
        aggfunc='sum',
        fill_value=0
    ).reindex(columns=week_days, fill_value=0)
    
    df_pivot_ore_dip['TOTALE ORE'] = df_pivot_ore_dip.sum(axis=1)
    df_pivot_ore_dip.columns = [col.strftime('%a %d/%m') if isinstance(col, date) else col for col in df_pivot_ore_dip.columns]
    
    st.dataframe(
        df_pivot_ore_dip.style.format("{:.2f} h"),
        use_container_width=True
    )

st.divider()
st.caption("Nota: L'assegnazione 'Squadra' si basa sulla composizione attuale delle squadre in 'Gestione Squadre'. Se un dipendente ha cambiato squadra, i suoi turni passati verranno mostrati sotto la squadra attuale.")