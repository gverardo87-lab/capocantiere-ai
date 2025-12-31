# file: server/pages/14_Riepilogo_Calendario.py (Versione 31.1 - No Matplotlib Dependency)
# Include: Storicizzazione Squadre, Fix Mixed Types, Styling Leggero

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import calendar

# Aggiungiamo la root del progetto al path per importare i moduli 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.shift_service import shift_service
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare `core.shift_service`: {e}")
    st.stop()

st.set_page_config(page_title="Calendario Pianificazione", page_icon="🗓️", layout="wide")
st.title("🗓️ Calendario Pianificazione Turni")
st.markdown("Visione d'insieme storicizzata dei turni pianificati per Squadra o per Dipendente.")

if st.button("🔄 Aggiorna Dati"):
    st.cache_data.clear()
    st.rerun()

# --- 1. FILTRO PERIODO E VISTA ---
with st.container(border=True):
    col1, col2 = st.columns(2)
    today = date.today()

    with col1:
        st.subheader("Seleziona il Periodo")
        period_mode = st.radio(
            "Modalità Periodo",
            ["Settimana", "Mese", "Intervallo Personalizzato"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        if period_mode == "Settimana":
            start_of_week = today - timedelta(days=today.weekday()) # Trova Lunedì
            selected_monday = st.date_input("Lunedì della settimana", value=start_of_week)
            start_date = selected_monday
            end_date = selected_monday + timedelta(days=6) # Fino a Domenica
        
        elif period_mode == "Mese":
            month_map = {i: calendar.month_name[i] for i in range(1, 13)}
            sel_col1, sel_col2 = st.columns(2)
            selected_month = sel_col1.selectbox("Mese", options=list(month_map.keys()), format_func=lambda m: month_map[m], index=today.month - 1)
            selected_year = sel_col2.number_input("Anno", value=today.year, min_value=2020, max_value=2050)
            start_date = date(selected_year, selected_month, 1)
            last_day_of_month = calendar.monthrange(selected_year, selected_month)[1]
            end_date = date(selected_year, selected_month, last_day_of_month)

        else: # Intervallo Personalizzato
            sel_col1, sel_col2 = st.columns(2)
            default_start = today.replace(day=1)
            start_date = sel_col1.date_input("Da data", value=default_start)
            end_date = sel_col2.date_input("A data", value=today)

    with col2:
        st.subheader("Seleziona la Vista")
        view_mode = st.radio("Visualizza per:", ["Squadra", "Dipendente"], horizontal=True, label_visibility="collapsed")

st.info(f"Visualizzazione dei turni da **{start_date.strftime('%d/%m/%Y')}** a **{end_date.strftime('%d/%m/%Y')}**.")

if start_date > end_date:
    st.error("Errore: La data di inizio non può essere successiva alla data di fine.")
    st.stop()

# --- 2. CARICAMENTO DATI ---
# Nota: get_turni_master_range_df ora restituisce anche 'id_squadra' e 'nome_squadra' (STORICO)
try:
    with st.spinner("Caricamento dati storicizzati..."):
        df_turni = shift_service.get_turni_master_range_df(start_date, end_date)
except Exception as e:
    st.error(f"Errore nel caricamento dati: {e}")
    st.stop()

if df_turni.empty:
    st.warning("Nessun turno pianificato trovato per il periodo selezionato.")
    st.stop()

# --- 3. PREPARAZIONE DATI ---
df_turni['giorno'] = pd.to_datetime(df_turni['data_ora_inizio_effettiva']).dt.date

# Fix Mixed Types Warning: Forziamo id_attivita a stringa
df_turni['id_attivita'] = df_turni['id_attivita'].fillna("").astype(str)

# Costruzione stringa info turno
df_turni['turno_info'] = df_turni.apply(
    lambda row: f"{row['data_ora_inizio_effettiva'].strftime('%H:%M')}-"
                f"{row['data_ora_fine_effettiva'].strftime('%H:%M')} "
                f"({row['id_attivita']})",
    axis=1
)

# ★ STORICIZZAZIONE: Usa il nome squadra salvato nel turno (o fallback 'Non Assegnata')
df_turni['squadra_storica'] = df_turni['nome_squadra'].fillna("Non Assegnata")

# Lista completa giorni
all_days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

# Formattazione Colonne
if period_mode == "Settimana":
    col_fmt = lambda col: col.strftime('%a %d/%m') if isinstance(col, date) else col
else:
    col_fmt = lambda col: col.strftime('%d/%m') if isinstance(col, date) else col

# --- 4. FUNZIONI DI STYLING (SENZA MATPLOTLIB) ---

def highlight_cells_info(val):
    """Stile per celle di testo (info turno)."""
    if val != '-' and val != 0: return 'background-color: #1C2A44; color: white'
    return ''

def style_squadra_hours(val):
    """Simula una heatmap blu per le ore squadra senza dipendenze esterne."""
    if isinstance(val, (int, float)):
        if val == 0: return 'color: #e0e0e0'
        # Sfumature di blu manuali
        if val < 20: return 'background-color: #dbeafe; color: black' # Blu chiarissimo
        if val < 50: return 'background-color: #93c5fd; color: black' # Blu medio
        return 'background-color: #2563eb; color: white' # Blu scuro
    return ''

def style_dipendente_hours(val):
    """Stile semaforico per ore dipendente."""
    if isinstance(val, (int, float)):
        if val == 0: return 'color: #e0e0e0'
        if val > 10: return 'background-color: #fee2e2; color: black' # Rosso chiaro (Warning)
        if val >= 8: return 'background-color: #dcfce7; color: black' # Verde chiaro (OK)
        return 'background-color: #fef9c3; color: black' # Giallo chiaro (Parziale)
    return ''

# --- 5. VISUALIZZAZIONE ---

if view_mode == "Squadra":
    st.header("📅 Calendario per Squadra (Storicizzato)")
    
    # PIVOT TURNI (Info)
    st.subheader("Turni Pianificati")
    piv_turni = df_turni.pivot_table(
        index='squadra_storica', columns='giorno', values='turno_info',
        aggfunc='first', fill_value='-'
    )
    piv_turni = piv_turni.reindex(columns=all_days, fill_value='-')
    piv_turni.columns = [col_fmt(c) for c in piv_turni.columns]
    
    st.dataframe(piv_turni.style.map(highlight_cells_info), use_container_width=True)

    # PIVOT ORE (Somma)
    st.subheader("Monte Ore per Squadra")
    piv_ore = df_turni.pivot_table(
        index='squadra_storica', columns='giorno', values='durata_ore',
        aggfunc='sum', fill_value=0
    )
    piv_ore = piv_ore.reindex(columns=all_days, fill_value=0)
    piv_ore['TOTALE'] = piv_ore.sum(axis=1)
    piv_ore.columns = [col_fmt(c) for c in piv_ore.columns]
    
    # Applica stile personalizzato invece di background_gradient
    st.dataframe(piv_ore.style.format("{:.2f} h").map(style_squadra_hours), use_container_width=True)

else: # Dipendente
    st.header(f"📅 Calendario per Dipendente")
    
    # PIVOT TURNI
    st.subheader("Turni Pianificati")
    piv_turni_dip = df_turni.pivot_table(
        index=['squadra_storica', 'dipendente_nome'], 
        columns='giorno', values='turno_info',
        aggfunc='first', fill_value='-'
    ).reindex(columns=all_days, fill_value='-')
    
    piv_turni_dip.columns = [col_fmt(c) for c in piv_turni_dip.columns]
    st.dataframe(piv_turni_dip.style.map(highlight_cells_info), use_container_width=True)
    
    # PIVOT ORE
    st.subheader("Monte Ore per Dipendente")
    piv_ore_dip = df_turni.pivot_table(
        index=['squadra_storica', 'dipendente_nome'], 
        columns='giorno', values='durata_ore',
        aggfunc='sum', fill_value=0
    ).reindex(columns=all_days, fill_value=0)
    
    piv_ore_dip['TOTALE'] = piv_ore_dip.sum(axis=1)
    piv_ore_dip.columns = [col_fmt(c) for c in piv_ore_dip.columns]

    st.dataframe(piv_ore_dip.style.map(style_dipendente_hours).format("{:.2f} h"), use_container_width=True)

st.divider()
st.caption("Nota: I dati visualizzati riflettono la squadra di appartenenza al momento dell'esecuzione del turno (Storicizzazione Attiva).")