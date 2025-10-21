# file: server/pages/01_Reportistica.py (Versione 17.1 - Corretto bug 'state' sui filtri)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import io # Necessario per l'export Excel

# Aggiungiamo la root del progetto al path per importare i moduli 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
    from core.logic import calculate_duration_hours
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare i moduli: {e}")
    st.stop()

st.set_page_config(page_title="Centro Report Amministrativo", page_icon="📊", layout="wide")
st.title("📊 Centro Report Amministrativo")
st.markdown("Strumento avanzato per l'analisi dei costi di manodopera, la contabilità e l'export per buste paga.")

# --- 1. FUNZIONI DI CARICAMENTO DATI ---

@st.cache_data(ttl=600) # Cache più lunga per la mappa attività
def load_activities_map():
    """Crea un dizionario (mappa) di ID Attività -> Descrizione."""
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
    """Crea un dizionario (mappa) di ID Dipendente -> Nome Squadra."""
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
    """Carica, processa e arricchisce i dati grezzi dal database."""
    df_raw_report = shift_service.get_report_data_df(start_date, end_date)

    if df_raw_report.empty:
        return pd.DataFrame()
    
    # Carica mappe
    activities_map = load_activities_map()
    squadra_map = load_squadra_map()

    # Arricchimento dati
    df_raw_report['durata_ore'] = df_raw_report.apply(
        lambda row: calculate_duration_hours(row['data_ora_inizio'], row['data_ora_fine']),
        axis=1
    )
    df_raw_report['desc_attivita'] = df_raw_report['id_attivita'].apply(map_activity_id, args=(activities_map,))
    df_raw_report['squadra'] = df_raw_report['id_dipendente'].map(squadra_map).fillna("Non Assegnato")
    df_raw_report['giorno'] = df_raw_report['data_ora_inizio'].dt.date
    
    return df_raw_report

def to_excel(df: pd.DataFrame) -> bytes:
    """Converte un DataFrame in un file Excel in memoria."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='ReportOre')
    processed_data = output.getvalue()
    return processed_data

# --- 2. PANNELLO FILTRI PRINCIPALE (CON GESTIONE STATE) ---
st.subheader("Pannello di Controllo")

# ★★★ INIZIO FIX GESTIONE STATO ★★★
if 'report_loaded' not in st.session_state:
    st.session_state.report_loaded = False

with st.container(border=True):
    col1, col2, col3 = st.columns([1, 1, 2])
    today = date.today()
    
    # Se le date sono già in session_state (perché il report è caricato), usiamo quelle
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
    # L'utente ha premuto il bottone
    st.session_state.report_loaded = True
    
    # Controlliamo se le date sono cambiate rispetto all'ultimo caricamento
    if (st.session_state.get('report_date_from') != date_from_input or 
        st.session_state.get('report_date_to') != date_to_input):
        
        # Date cambiate: puliamo la cache per forzare il ricaricamento dei dati
        st.cache_data.clear()
        print("DEBUG: Date cambiate, cache pulita.")
    
    # Salviamo (o aggiorniamo) le date nello stato della sessione
    st.session_state.report_date_from = date_from_input
    st.session_state.report_date_to = date_to_input

# ★★★ FIX CHIAVE ★★★
# Ora il controllo non è più su 'run_report' (che è True solo per un istante)
# ma sulla variabile 'report_loaded' che persiste nella sessione.
if not st.session_state.report_loaded:
    st.info("Imposta un intervallo di date e clicca 'Applica Filtri' per caricare il report.")
    st.stop()

# Da qui in poi, usiamo le date salvate in session_state per garantire coerenza
# anche durante i rerun causati dai filtri avanzati.
date_from = st.session_state.report_date_from
date_to = st.session_state.report_date_to
# ★★★ FINE FIX GESTIONE STATO ★★★

if date_from > date_to:
    st.error("Errore: La data 'Da' deve essere precedente alla data 'A'.")
    st.session_state.report_loaded = False # Resetta lo stato se le date sono invalide
    st.stop()

# --- 3. CARICAMENTO E FILTRAGGIO AVANZATO ---
try:
    with st.spinner("Caricamento e aggregazione dati in corso..."):
        # La funzione 'load_processed_data' usa la cache. 
        # Verrà eseguita davvero solo se 'st.cache_data.clear()' è stato chiamato.
        df_processed = load_processed_data(date_from, date_to)

        if df_processed.empty:
            st.warning("Nessuna registrazione trovata nell'intervallo di date selezionato.")
            st.stop()

except Exception as e:
    st.error(f"Si è verificato un errore durante la generazione del report: {e}")
    st.stop()

st.header(f"Report dal {date_from.strftime('%d/%m/%Y')} al {date_to.strftime('%d/%m/%Y')}")

# --- FILTRI AVANZATI (POST-CARICAMENTO) ---
# Questi filtri ora NON causeranno più il reset della pagina
st.subheader("Filtri Avanzati")
with st.container(border=True):
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        dipendenti_options = sorted(df_processed['dipendente_nome'].unique())
        selected_dipendenti = st.multiselect("Filtra per Dipendente", dipendenti_options, placeholder="Tutti i dipendenti")
    with f_col2:
        squadre_options = sorted(df_processed['squadra'].unique())
        selected_squadre = st.multiselect("Filtra per Squadra", squadre_options, placeholder="Tutte le squadre")
    with f_col3:
        attivita_options = sorted(df_processed['desc_attivita'].unique())
        selected_attivita = st.multiselect("Filtra per Attività", attivita_options, placeholder="Tutte le attività")

# Applica i filtri avanzati
df_filtered = df_processed.copy()
if selected_dipendenti:
    df_filtered = df_filtered[df_filtered['dipendente_nome'].isin(selected_dipendenti)]
if selected_squadre:
    df_filtered = df_filtered[df_filtered['squadra'].isin(selected_squadre)]
if selected_attivita:
    df_filtered = df_filtered[df_filtered['desc_attivita'].isin(selected_attivita)]

if df_filtered.empty:
    st.warning("Nessun dato corrisponde ai filtri avanzati selezionati.")
    st.stop()

# --- 4. CALCOLO KPI E AGGREGAZIONI (SUI DATI FILTRATI) ---
total_hours = df_filtered['durata_ore'].sum()
total_dipendenti = df_filtered['id_dipendente'].nunique()
total_giorni = df_filtered['giorno'].nunique()
avg_hours_dip = total_hours / total_dipendenti if total_dipendenti > 0 else 0

# Aggregazioni per i grafici
df_dipendente = df_filtered.groupby(['dipendente_nome', 'ruolo'])['durata_ore'].sum().reset_index().sort_values(by="durata_ore", ascending=False)
df_attivita = df_filtered.groupby('desc_attivita')['durata_ore'].sum().reset_index().sort_values(by="durata_ore", ascending=False)
df_squadra = df_filtered.groupby('squadra')['durata_ore'].sum().reset_index().sort_values(by="durata_ore", ascending=False)
df_giornaliero = df_filtered.groupby('giorno')['durata_ore'].sum().reset_index()

# --- 5. VISUALIZZAZIONE A TAB ---
tab1, tab2, tab3 = st.tabs(["📊 Dashboard Aggregata", "🔍 Analisi Dettagliata (Pivot)", "📥 Dati Grezzi & Export"])

with tab1:
    st.header("Dashboard Aggregata")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Ore Totali (Filtrate)", f"{total_hours:,.2f} h")
    kpi2.metric("Dipendenti Coinvolti", total_dipendenti)
    kpi3.metric("Giorni di Lavoro", total_giorni)
    kpi4.metric("Media Ore / Dipendente", f"{avg_hours_dip:,.2f} h")
    
    st.divider()
    
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.subheader("Ore per Squadra")
        fig_sq = px.pie(df_squadra, names='squadra', values='durata_ore', title="Ripartizione Ore per Squadra")
        st.plotly_chart(fig_sq, use_container_width=True)

    with chart_col2:
        st.subheader("Ore per Attività")
        fig_att = px.pie(df_attivita, names='desc_attivita', values='durata_ore', title="Ripartizione Ore per Attività")
        st.plotly_chart(fig_att, use_container_width=True)

    st.divider()
    
    st.subheader("Andamento Ore Giornaliere (per Competenza)")
    fig_giorno = px.line(
        df_giornaliero, 
        x='giorno', 
        y='durata_ore',
        title="Totale Ore Lavorate per Giorno (00:00-00:00)",
        labels={'giorno': 'Data di Competenza', 'durata_ore': 'Ore Totali'}
    )
    fig_giorno.update_traces(mode='lines+markers', line_shape='spline')
    st.plotly_chart(fig_giorno, use_container_width=True)

with tab2:
    st.header("Analisi Dettagliata (Tabelle Pivot)")
    
    st.subheader("Pivot: Ore per Dipendente al Giorno")
    st.markdown("Totale ore per dipendente, suddivise per giorno.")
    
    try:
        pivot_dip_giorno = pd.pivot_table(
            df_filtered,
            index=['squadra', 'dipendente_nome', 'ruolo'],
            columns='giorno',
            values='durata_ore',
            aggfunc='sum',
            fill_value=0,
            margins=True,
            margins_name="TOTALE"
        )
        st.dataframe(pivot_dip_giorno.style.format("{:.2f} h"), use_container_width=True)
    except Exception as e:
        st.warning(f"Impossibile generare il pivot dipendente/giorno: {e}")

    st.divider()

    st.subheader("Pivot: Ore per Attività per Squadra")
    st.markdown("Totale ore per attività, suddivise per squadra.")
    
    try:
        pivot_att_squadra = pd.pivot_table(
            df_filtered,
            index=['desc_attivita'],
            columns=['squadra'],
            values='durata_ore',
            aggfunc='sum',
            fill_value=0,
            margins=True,
            margins_name="TOTALE"
        )
        st.dataframe(pivot_att_squadra.style.format("{:.2f} h"), use_container_width=True)
    except Exception as e:
        st.warning(f"Impossibile generare il pivot attività/squadra: {e}")

with tab3:
    st.header("Dati Grezzi & Export per Buste Paga")
    
    st.markdown("Usa i filtri avanzati sopra per preparare i dati, poi clicca 'Download Excel'.")
    
    # Preparazione finale del DataFrame per l'export
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
        'durata_ore': 'Ore Totali',
        'id_attivita': 'Codice Attività',
        'tipo_ore': 'Tipo Ore DB'
    }
    df_export_final = df_export[colonne_export.keys()].rename(columns=colonne_export)
    
    try:
        excel_data = to_excel(df_export_final)
        
        st.download_button(
            label="📥 Download Report Filtrato (.xlsx)",
            data=excel_data,
            file_name=f"Report_Ore_{date_from.strftime('%d_%m_%Y')}_al_{date_to.strftime('%d_%m_%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheet_ml.sheet",
            use_container_width=True,
            type="primary"
        )
    except Exception as e:
        st.error(f"Impossibile generare il file Excel: {e}")

    st.divider()
    
    st.subheader("Dettaglio Segmenti di Lavoro (Filtrati)")
    st.dataframe(
        df_export_final,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data Competenza": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Inizio Turno": st.column_config.DatetimeColumn("Inizio", format="DD/MM HH:mm"),
            "Fine Turno": st.column_config.DatetimeColumn("Fine", format="DD/MM HH:mm"),
            "Ore Totali": st.column_config.NumberColumn("Ore", format="%.2f h")
        }
    )