# file: server/pages/01_Reportistica.py (Versione 17.5 - Integrazione Doppio Binario Presenza/Lavoro)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import io 

# Aggiungiamo la root del progetto al path per importare i moduli 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
    # Importiamo ShiftEngine per eventuali ricalcoli o utilità
    from core.logic import ShiftEngine 
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare i moduli: {e}")
    st.stop()

st.set_page_config(page_title="Centro Report Amministrativo", page_icon="📊", layout="wide")
st.title("📊 Centro Report Amministrativo")
st.markdown("Analisi professionale a doppio binario: **Presenza (Busta)** e **Lavoro (Cantiere)**.")

# --- 1. FUNZIONI DI CARICAMENTO DATI ---

@st.cache_data(ttl=600)
def load_activities_map():
    activities_map = {
        "VIAGGIO": "VIAGGIO (Trasferta)",
        "STRAORDINARIO": "STRAORDINARIO (Generico)",
        "OFFICINA": "OFFICINA (Lavoro Interno)",
        "-1": "N/A (Non Specificato)"
    }
    try:
        schedule_data = schedule_db_manager.get_schedule_data()
        df_schedule = pd.DataFrame(schedule_data)
        if not df_schedule.empty:
            schedule_map = df_schedule.set_index('id_attivita')['descrizione'].to_dict()
            activities_map.update(schedule_map)
    except Exception as e:
        print(f"Errore caricamento cronoprogramma per mappa: {e}")
    return activities_map

@st.cache_data(ttl=60)
def load_squadra_map():
    try:
        squadre = shift_service.get_squadre()
        dip_squadra_map = {}
        for squadra in squadre:
            membri_ids = shift_service.get_membri_squadra(squadra['id_squadra'])
            for id_dip in membri_ids:
                dip_squadra_map[id_dip] = squadra['nome_squadra']
        return dip_squadra_map
    except Exception as e:
        print(f"Errore caricamento mappa squadre: {e}")
        return {}

def map_activity_id(id_att, activities_map):
    if pd.isna(id_att) or id_att == "-1":
        return "N/A (Non Specificato)"
    return activities_map.get(id_att, f"Attività Sconosciuta ({id_att})")

@st.cache_data(ttl=60)
def load_processed_data(start_date, end_date):
    """Carica i dati includendo le nuove colonne Presenza e Lavoro."""
    # Recupera i dati dal service (che ora include ore_presenza e ore_lavoro)
    df_raw_report = shift_service.get_report_data_df(start_date, end_date)

    if df_raw_report.empty:
        return pd.DataFrame()
    
    activities_map = load_activities_map()
    squadra_map = load_squadra_map()

    # Arricchimento dati
    df_raw_report['desc_attivita'] = df_raw_report['id_attivita'].apply(map_activity_id, args=(activities_map,))
    df_raw_report['squadra'] = df_raw_report['id_dipendente'].map(squadra_map).fillna("Non Assegnato")
    df_raw_report['giorno'] = df_raw_report['data_ora_inizio'].dt.date
    
    # Fallback per vecchi record (se ore_presenza è null, calcola al volo)
    if 'ore_presenza' not in df_raw_report.columns:
        df_raw_report['ore_presenza'] = 0.0
    if 'ore_lavoro' not in df_raw_report.columns:
        df_raw_report['ore_lavoro'] = 0.0
        
    # Se ci sono valori nulli (vecchio DB), li riempiamo col calcolo standard
    mask_nan = df_raw_report['ore_presenza'].isna()
    if mask_nan.any():
        print("⚠️ Trovati record legacy senza ore calcolate. Eseguo backfill...")
        temp_calc = df_raw_report[mask_nan].apply(
            lambda row: ShiftEngine.calculate_professional_hours(row['data_ora_inizio'], row['data_ora_fine']), 
            axis=1, result_type='expand'
        )
        df_raw_report.loc[mask_nan, 'ore_presenza'] = temp_calc[0]
        df_raw_report.loc[mask_nan, 'ore_lavoro'] = temp_calc[1]

    return df_raw_report

def to_excel(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='ReportOre')
    return output.getvalue()

# --- 2. PANNELLO FILTRI PRINCIPALE ---
st.subheader("Pannello di Controllo")

if 'report_loaded' not in st.session_state:
    st.session_state.report_loaded = False

with st.container(border=True):
    col1, col2, col3 = st.columns([1, 1, 2])
    today = date.today()
    
    default_start = st.session_state.get('report_date_from', today.replace(day=1))
    default_end = st.session_state.get('report_date_to', today)
    
    with col1:
        date_from_input = st.date_input("Da data", default_start)
    with col2:
        date_to_input = st.date_input("A data", default_end)
    with col3:
        st.write("")
        st.write("")
        run_report = st.button("Applica Filtri e Carica Report", type="primary", use_container_width=True)

if run_report:
    st.session_state.report_loaded = True
    if (st.session_state.get('report_date_from') != date_from_input or 
        st.session_state.get('report_date_to') != date_to_input):
        st.cache_data.clear()
    st.session_state.report_date_from = date_from_input
    st.session_state.report_date_to = date_to_input

if not st.session_state.report_loaded:
    st.info("Imposta un intervallo di date e clicca 'Applica Filtri' per caricare il report.")
    st.stop()

date_from = st.session_state.report_date_from
date_to = st.session_state.report_date_to

if date_from > date_to:
    st.error("Errore: La data 'Da' deve essere precedente alla data 'A'.")
    st.stop()

# --- 3. CARICAMENTO E FILTRAGGIO ---
try:
    with st.spinner("Caricamento dati professionali in corso..."):
        df_processed = load_processed_data(date_from, date_to)
        if df_processed.empty:
            st.warning("Nessuna registrazione trovata nell'intervallo selezionato.")
            st.stop()
except Exception as e:
    st.error(f"Errore generazione report: {e}")
    st.stop()

st.header(f"Report dal {date_from.strftime('%d/%m/%Y')} al {date_to.strftime('%d/%m/%Y')}")

st.subheader("Filtri Avanzati")
with st.container(border=True):
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        selected_dipendenti = st.multiselect("Filtra per Dipendente", sorted(df_processed['dipendente_nome'].unique()))
    with f_col2:
        selected_squadre = st.multiselect("Filtra per Squadra", sorted(df_processed['squadra'].unique()))
    with f_col3:
        selected_attivita = st.multiselect("Filtra per Attività", sorted(df_processed['desc_attivita'].unique()))

df_filtered = df_processed.copy()
if selected_dipendenti: df_filtered = df_filtered[df_filtered['dipendente_nome'].isin(selected_dipendenti)]
if selected_squadre: df_filtered = df_filtered[df_filtered['squadra'].isin(selected_squadre)]
if selected_attivita: df_filtered = df_filtered[df_filtered['desc_attivita'].isin(selected_attivita)]

if df_filtered.empty:
    st.warning("Nessun dato corrisponde ai filtri selezionati.")
    st.stop()

# --- 4. KPI E AGGREGAZIONI (DOPPIO BINARIO) ---
total_presenza = df_filtered['ore_presenza'].sum()
total_lavoro = df_filtered['ore_lavoro'].sum()
total_dipendenti = df_filtered['id_dipendente'].nunique()
avg_hours_dip = total_presenza / total_dipendenti if total_dipendenti > 0 else 0

# Aggregazioni per grafici
df_dipendente = df_filtered.groupby(['dipendente_nome', 'ruolo'])[['ore_presenza', 'ore_lavoro']].sum().reset_index()
df_attivita = df_filtered.groupby('desc_attivita')[['ore_presenza', 'ore_lavoro']].sum().reset_index().sort_values(by="ore_lavoro", ascending=False)
df_squadra = df_filtered.groupby('squadra')[['ore_presenza', 'ore_lavoro']].sum().reset_index()
df_giornaliero = df_filtered.groupby('giorno')[['ore_presenza', 'ore_lavoro']].sum().reset_index()

# --- 5. VISUALIZZAZIONE A TAB ---
tab1, tab2, tab3 = st.tabs(["📊 Dashboard Aggregata", "🔍 Analisi Pivot (Statino)", "📥 Export Contabilità"])

with tab1:
    st.header("Dashboard Aggregata")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Ore Presenza (Busta)", f"{total_presenza:,.2f} h", help="Totale ore da pagare (include le pause)")
    kpi2.metric("Ore Lavoro (Cantiere)", f"{total_lavoro:,.2f} h", help="Totale ore fatturabili (netto pause)")
    kpi3.metric("Dipendenti", total_dipendenti)
    kpi4.metric("Media Presenza / Dip", f"{avg_hours_dip:,.2f} h")
    
    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Distribuzione Lavoro per Squadra")
        fig_sq = px.pie(df_squadra, names='squadra', values='ore_lavoro', hole=.4)
        st.plotly_chart(fig_sq, use_container_width=True)
    with c2:
        st.subheader("Lavoro per Attività (Fatturabile)")
        fig_att = px.bar(df_attivita, x='desc_attivita', y='ore_lavoro', color='desc_attivita')
        st.plotly_chart(fig_att, use_container_width=True)

    st.subheader("Andamento Giornaliero (Presenza vs Lavoro)")
    # Riorganizziamo il DF per il grafico a linee multi-variabile
    fig_line = px.line(df_giornaliero, x='giorno', y=['ore_presenza', 'ore_lavoro'], 
                       labels={'value': 'Ore', 'variable': 'Tipo'}, markers=True,
                       color_discrete_map={'ore_presenza': 'orange', 'ore_lavoro': 'green'})
    st.plotly_chart(fig_line, use_container_width=True)

with tab2:
    st.header("Analisi Pivot Professionale")
    st.markdown("Confronta i dati per Busta Paga (Presenza) e Fatturazione (Lavoro).")
    
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.subheader("Riepilogo Ore Presenza (Busta Paga)")
        try:
            pivot = pd.pivot_table(
                df_filtered,
                index=['squadra', 'dipendente_nome'],
                columns='giorno',
                values='ore_presenza', 
                aggfunc='sum',
                fill_value=0,
                margins=True, margins_name="TOTALE"
            )
            st.dataframe(pivot.style.format("{:.2f}"), use_container_width=True)
        except Exception as e:
            st.warning(f"Errore pivot: {e}")

    with col_p2:
        st.subheader("Riepilogo Ore Lavoro (Fatturabile)")
        try:
            pivot_lav = pd.pivot_table(
                df_filtered,
                index=['squadra', 'dipendente_nome'],
                columns='giorno',
                values='ore_lavoro',
                aggfunc='sum',
                fill_value=0,
                margins=True, margins_name="TOTALE"
            )
            st.dataframe(pivot_lav.style.format("{:.2f}"), use_container_width=True)
        except Exception as e:
            st.warning(f"Errore pivot: {e}")

with tab3:
    st.header("Dati Grezzi & Export per Buste Paga")
    st.markdown("Esporta i dati completi con doppia colonna per l'invio al consulente del lavoro.")
    
    df_export = df_filtered.sort_values(by=["squadra", "dipendente_nome", "data_ora_inizio"])
    
    # Seleziona e rinomina le colonne per la contabilità
    colonne_export = {
        'giorno': 'Data Competenza',
        'squadra': 'Squadra',
        'dipendente_nome': 'Dipendente',
        'ruolo': 'Ruolo',
        'desc_attivita': 'Attività',
        'data_ora_inizio': 'Inizio Turno',
        'data_ora_fine': 'Fine Turno',
        'ore_presenza': 'Ore Presenza (Busta)',
        'ore_lavoro': 'Ore Lavoro (Cantiere)',
        'note': 'Note'
    }
    # Filtriamo solo le colonne che esistono effettivamente
    cols_to_use = [c for c in colonne_export.keys() if c in df_export.columns]
    df_export_final = df_export[cols_to_use].rename(columns=colonne_export)
    
    try:
        excel_data = to_excel(df_export_final)
        st.download_button(
            label="📥 Download Report Excel Completo",
            data=excel_data,
            file_name=f"Report_Cantieri_{date_from.strftime('%d%m%Y')}_{date_to.strftime('%d%m%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheet_ml.sheet",
            use_container_width=True,
            type="primary"
        )
    except Exception as e:
        st.error(f"Impossibile generare il file Excel: {e}")

    st.divider()
    st.dataframe(df_export_final, use_container_width=True, hide_index=True)