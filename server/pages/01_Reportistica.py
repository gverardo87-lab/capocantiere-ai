# file: server/pages/01_Reportistica.py (Versione 21.1 - Fix No-Matplotlib)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import io 

# Aggiungiamo la root del progetto al path per importare i moduli 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
    from core.logic import ShiftEngine 
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare i moduli: {e}")
    st.stop()

st.set_page_config(page_title="Centro Report & Audit Costi", page_icon="📊", layout="wide")
st.title("📊 Centro Report & Audit Industriale")
st.markdown("Analisi Operativa e **Certificazione Costi di Commessa**.")

# --- HELPER STILI (SENZA MATPLOTLIB) ---
def style_internal(val):
    """Scala di Blu per Statino Interno (CSS Puro)"""
    if not isinstance(val, (int, float)) or val == 0: return 'color: #e0e0e0'
    if val < 8: return 'background-color: #dbeafe; color: black' # Blu chiarissimo (Sotto soglia)
    if val <= 10: return 'background-color: #93c5fd; color: black' # Blu medio (Standard)
    return 'background-color: #2563eb; color: white' # Blu scuro (Straordinario)

def style_external(val):
    """Scala di Arancio per Report Cantiere (CSS Puro)"""
    if not isinstance(val, (int, float)) or val == 0: return 'color: #e0e0e0'
    if val < 8: return 'background-color: #ffedd5; color: black' # Arancio chiarissimo
    if val <= 9: return 'background-color: #fdba74; color: black' # Arancio medio (Standard Cantiere)
    return 'background-color: #ea580c; color: white' # Arancio scuro (Extra)

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
        # print(f"Errore caricamento cronoprogramma per mappa: {e}")
        pass
    return activities_map

@st.cache_data(ttl=50)
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
        # print(f"Errore caricamento mappa squadre: {e}")
        return {}

def map_activity_id(id_att, activities_map):
    if pd.isna(id_att) or id_att == "-1":
        return "N/A (Non Specificato)"
    return activities_map.get(id_att, f"Attività Sconosciuta ({id_att})")

@st.cache_data(ttl=60)
def load_processed_data(start_date, end_date):
    """Carica i dati includendo le nuove colonne Presenza e Lavoro."""
    df_raw_report = shift_service.get_report_data_df(start_date, end_date)

    if df_raw_report.empty:
        return pd.DataFrame()
    
    activities_map = load_activities_map()
    squadra_map = load_squadra_map()

    # Arricchimento dati
    df_raw_report['desc_attivita'] = df_raw_report['id_attivita'].apply(map_activity_id, args=(activities_map,))
    df_raw_report['squadra'] = df_raw_report['id_dipendente'].map(squadra_map).fillna("Non Assegnato")
    df_raw_report['giorno'] = df_raw_report['data_ora_inizio'].dt.date
    
    # Fallback calcolo ore (se mancano nel DB)
    if 'ore_presenza' not in df_raw_report.columns: df_raw_report['ore_presenza'] = 0.0
    if 'ore_lavoro' not in df_raw_report.columns: df_raw_report['ore_lavoro'] = 0.0
        
    mask_nan = df_raw_report['ore_presenza'].isna()
    if mask_nan.any():
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

# --- 2. PANNELLO FILTRI ---
st.subheader("Pannello di Controllo")

if 'report_loaded' not in st.session_state:
    st.session_state.report_loaded = False

with st.container(border=True):
    col1, col2, col3 = st.columns([1, 1, 2])
    today = date.today()
    default_start = st.session_state.get('report_date_from', today.replace(day=1))
    default_end = st.session_state.get('report_date_to', today)
    
    with col1: date_from_input = st.date_input("Da data", default_start)
    with col2: date_to_input = st.date_input("A data", default_end)
    with col3:
        st.write("")
        st.write("")
        run_report = st.button("Applica Filtri e Carica Report", type="primary", use_container_width=True)

if run_report:
    st.session_state.report_loaded = True
    if (st.session_state.get('report_date_from') != date_from_input or st.session_state.get('report_date_to') != date_to_input):
        st.cache_data.clear()
    st.session_state.report_date_from = date_from_input
    st.session_state.report_date_to = date_to_input

if not st.session_state.report_loaded:
    st.info("Imposta un intervallo di date e clicca 'Applica Filtri'.")
    st.stop()

date_from = st.session_state.report_date_from
date_to = st.session_state.report_date_to

if date_from > date_to: st.error("Date invalide."); st.stop()

try:
    with st.spinner("Elaborazione dati..."):
        df_processed = load_processed_data(date_from, date_to)
        if df_processed.empty:
            st.warning("Nessun dato trovato."); st.stop()
except Exception as e:
    st.error(f"Errore: {e}"); st.stop()

st.header(f"Report dal {date_from.strftime('%d/%m/%Y')} al {date_to.strftime('%d/%m/%Y')}")

# Filtri Avanzati
with st.expander("Filtri Avanzati (Squadra / Dipendente)", expanded=False):
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1: selected_dipendenti = st.multiselect("Dipendente", sorted(df_processed['dipendente_nome'].unique()))
    with f_col2: selected_squadre = st.multiselect("Squadra", sorted(df_processed['squadra'].unique()))
    with f_col3: selected_attivita = st.multiselect("Attività", sorted(df_processed['desc_attivita'].unique()))

df_filtered = df_processed.copy()
if selected_dipendenti: df_filtered = df_filtered[df_filtered['dipendente_nome'].isin(selected_dipendenti)]
if selected_squadre: df_filtered = df_filtered[df_filtered['squadra'].isin(selected_squadre)]
if selected_attivita: df_filtered = df_filtered[df_filtered['desc_attivita'].isin(selected_attivita)]

if df_filtered.empty: st.warning("Nessun dato con questi filtri."); st.stop()

# --- 3. TABS ---
tab1, tab2, tab3, tab_audit = st.tabs(["📊 Dashboard Operativa", "🔍 Analisi Pivot (Separate)", "📥 Export Excel", "⚖️ AUDIT INDUSTRIALE"])

# TAB 1: DASHBOARD
with tab1:
    tot_p, tot_l = df_filtered['ore_presenza'].sum(), df_filtered['ore_lavoro'].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Ore Presenza (Busta)", f"{tot_p:,.1f}")
    k2.metric("Ore Lavoro (Cantiere)", f"{tot_l:,.1f}")
    k3.metric("Delta Ore", f"{tot_p-tot_l:,.1f}", delta="Non Produttive", delta_color="inverse")
    st.divider()
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.pie(df_filtered.groupby('squadra')['ore_lavoro'].sum().reset_index(), names='squadra', values='ore_lavoro', title="Ore per Squadra"), use_container_width=True)
    c2.plotly_chart(px.bar(df_filtered.groupby('giorno')[['ore_presenza', 'ore_lavoro']].sum().reset_index(), x='giorno', y=['ore_presenza', 'ore_lavoro'], title="Trend Giornaliero"), use_container_width=True)

# ==============================================================================
# ★ TAB 2: PIVOT SEPARATE (FIX NO MATPLOTLIB) ★
# ==============================================================================
with tab2:
    st.header("Analisi Pivot Separata")
    st.markdown("Visualizzazione distinta per **Contabilità Interna** ed **Esterna**.")

    # --- TABELLA 1: INTERNA (BUSTE PAGA) ---
    st.subheader("1. STATINO INTERNO (Buste Paga)")
    st.info("📅 Dati basati su **Ore Presenza Totali** (Retribuite al dipendente)")
    
    try:
        pivot_presenza = pd.pivot_table(
            df_filtered, 
            index=['squadra', 'dipendente_nome'], 
            columns='giorno', 
            values='ore_presenza', 
            aggfunc='sum', 
            fill_value=0, 
            margins=True, 
            margins_name="TOTALE"
        )
        # USA STYLE.MAP INVECE DI BACKGROUND_GRADIENT
        st.dataframe(pivot_presenza.style.format("{:.1f}").map(style_internal), use_container_width=True)
    except Exception as e:
        st.error(f"Errore creazione pivot presenza: {e}")

    st.markdown("---") # Divisore Netto

    # --- TABELLA 2: ESTERNA (CANTIERE) ---
    st.subheader("2. REPORT CANTIERE (Fatturazione)")
    st.warning("🚜 Dati basati su **Ore Lavoro Riconosciute** (Fatturabili al cantiere)")
    
    try:
        pivot_lavoro = pd.pivot_table(
            df_filtered, 
            index=['squadra', 'dipendente_nome'], 
            columns='giorno', 
            values='ore_lavoro', 
            aggfunc='sum', 
            fill_value=0, 
            margins=True, 
            margins_name="TOTALE"
        )
        # USA STYLE.MAP INVECE DI BACKGROUND_GRADIENT
        st.dataframe(pivot_lavoro.style.format("{:.1f}").map(style_external), use_container_width=True)
    except Exception as e:
        st.error(f"Errore creazione pivot lavoro: {e}")

# TAB 3: EXPORT
with tab3:
    st.subheader("Esportazione Dati")
    colonne_export = {'giorno': 'Data', 'squadra': 'Squadra', 'dipendente_nome': 'Nome', 'ruolo': 'Ruolo', 'desc_attivita': 'Attività', 'ore_presenza': 'Presenza', 'ore_lavoro': 'Lavoro', 'note': 'Note'}
    
    # Fix robusto per colonne mancanti
    cols_to_use = [c for c in colonne_export.keys() if c in df_filtered.columns]
    df_exp = df_filtered[cols_to_use].rename(columns=colonne_export)
    
    st.download_button("Scarica Excel Completo", to_excel(df_exp), f"Report_{date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheet_ml.sheet", type="primary")
    st.dataframe(df_exp, hide_index=True)

# ==============================================================================
# ★ TAB 4: AUDIT INDUSTRIALE (MARSIGLIA MODEL) ★
# ==============================================================================
with tab_audit:
    st.markdown("## ⚖️ Audit Industriale: Analisi per Squadra Tipo")
    st.markdown("Analisi del **Costo Vivo Giornaliero** (10h pagate) vs **Incasso Giornaliero** (9h riconosciute).")
    
    # --- A. CONFIGURAZIONE ---
    with st.expander("🛠️ Parametri di Audit (Editabili)", expanded=True):
        c_p1, c_p2, c_p3 = st.columns(3)
        with c_p1:
            st.markdown("##### 1. Ricavi")
            tariffa_attuale = st.number_input("Tariffa Oraria (€)", value=27.00, format="%.2f")
            ore_fattura_gg = st.number_input("Ore Riconosciute dal Cantiere", value=9)
        with c_p2:
            st.markdown("##### 2. Costi Manodopera")
            netto_op = st.number_input("Netto Ora Operaio (€)", value=18.00, format="%.2f")
            oneri_op = st.number_input("Oneri Giornalieri Op.", value=42.00, format="%.2f")
            netto_capo = st.number_input("Netto Ora Capo (€)", value=21.00, format="%.2f")
            oneri_capo = st.number_input("Oneri Giornalieri Capo", value=48.00, format="%.2f")
            n_op = st.number_input("Numero Operai", value=6)
        with c_p3:
            st.markdown("##### 3. Costi Struttura")
            ore_presenza_gg = st.number_input("Ore Pagate all'Uomo", value=10)
            ticket = st.number_input("Ticket/Giorno (€)", value=20.00, format="%.2f")
            overheads = st.number_input("Spese Generali (€/ora fatt.)", value=2.28, format="%.2f")

    st.divider()

    # --- B. MOTORE MATEMATICO ---
    # 1. Costi Uscita
    costo_giorno_singolo_op = (netto_op * ore_presenza_gg) + oneri_op + ticket
    costo_giorno_singolo_capo = (netto_capo * ore_presenza_gg) + oneri_capo + ticket
    costo_giorno_squadra = (costo_giorno_singolo_op * n_op) + costo_giorno_singolo_capo
    
    # 2. Ricavi Entrata
    ore_fatturabili_squadra = (n_op + 1) * ore_fattura_gg
    incasso_giorno_squadra = ore_fatturabili_squadra * tariffa_attuale
    
    # 3. Risultati
    margine_industriale_giorno = incasso_giorno_squadra - costo_giorno_squadra
    costo_overheads_giorno = overheads * ore_fatturabili_squadra
    margine_netto_giorno = margine_industriale_giorno - costo_overheads_giorno
    
    # Break Even
    costo_totale_full_giorno = costo_giorno_squadra + costo_overheads_giorno
    bep_tariffa = costo_totale_full_giorno / ore_fatturabili_squadra

    # --- C. VISUALIZZAZIONE ---
    col_res_1, col_res_2 = st.columns([1, 2])
    with col_res_1:
        st.subheader("Bilancio Squadra (1 Giorno)")
        st.markdown(f"**Uscite (Costo Vivo):** :red[€ {costo_giorno_squadra:,.2f}]")
        st.markdown(f"**Entrate (Fatturato):** :blue[€ {incasso_giorno_squadra:,.2f}]")
        if margine_industriale_giorno < 0: st.error(f"⚠️ PERDITA OPERATIVA: € {margine_industriale_giorno:,.2f} /giorno")
        else: st.warning(f"Margine Lordo: € {margine_industriale_giorno:,.2f} /giorno")
        st.markdown("---")
        final_color = "red" if margine_netto_giorno < 0 else "green"
        st.markdown(f"### Risultato Netto: :{final_color}[€ {margine_netto_giorno:,.2f}] /giorno")

    with col_res_2:
        st.subheader("Analisi Tariffa Oraria")
        k1, k2, k3 = st.columns(3)
        k1.metric("Tariffa Attuale", f"€ {tariffa_attuale:.2f}")
        k2.metric("Costo Reale (BEP)", f"€ {bep_tariffa:.2f}")
        k3.metric("Differenza", f"€ {tariffa_attuale - bep_tariffa:.2f}", delta_color="normal" if tariffa_attuale > bep_tariffa else "inverse")
        
        st.markdown("#### 🧮 La Prova del 9 (Dettaglio Uomo)")
        df_prova = pd.DataFrame([
            {"Voce": "Paga Netta (10h)", "Importo": netto_op * 10},
            {"Voce": "+ Oneri (INPS/INAIL)", "Importo": oneri_op},
            {"Voce": "+ Ticket", "Importo": ticket},
            {"Voce": "= COSTO VIVO UOMO", "Importo": costo_giorno_singolo_op},
            {"Voce": "Fatturato (9h x 27€)", "Importo": 9 * tariffa_attuale},
            {"Voce": "MARGINE (Pre-spese)", "Importo": (9 * tariffa_attuale) - costo_giorno_singolo_op}
        ])
        st.dataframe(df_prova.style.format({"Importo": "€ {:.2f}"}), hide_index=True, use_container_width=True)

    st.divider()
    
    # --- D. GENERATORE LETTERA ---
    st.subheader("📄 Generazione Audit per Direzione")
    
    audit_text = f"""
    MARSIGLIA, {date.today().strftime("%d/%m/%Y")}

    OGGETTO: AUDIT INDUSTRIALE E REVISIONE COSTI DI COMMESSA
    RIF: Cantiere Navale Marsiglia (CNdM) – Analisi Costi Squadra {n_op+1} Unità

    1. EXECUTIVE SUMMARY
    La presente relazione certifica che l'attuale tariffa di € {tariffa_attuale:.2f}/h è INFERIORE al 
    Costo Industriale di Produzione (€ {bep_tariffa:.2f}/h), generando una perdita strutturale 
    giornaliera di € {abs(margine_netto_giorno):.2f} per ogni squadra in campo.

    2. ANALISI CASH FLOW GIORNALIERO (SQUADRA {n_op+1} PERSONE)
    
    A. COSTI VIVI (USCITE CERTE SU 10 ORE PRESENZA)
       - Personale Operativo ({n_op} unità): € {costo_giorno_singolo_op:.2f} cad. x {n_op} = € {costo_giorno_singolo_op*n_op:,.2f}
       - Capocantiere (1 unità): € {costo_giorno_singolo_capo:,.2f}
       ----------------------------------------------------------
       TOTALE COSTO MANODOPERA GIORNALIERO: € {costo_giorno_squadra:,.2f}

    B. RICAVI (ENTRATE SU 9 ORE RICONOSCIUTE)
       - Ore Totali Fatturabili: {(n_op+1)*ore_fattura_gg} ore
       - Tariffa Applicata: € {tariffa_attuale:.2f}/h
       ----------------------------------------------------------
       TOTALE FATTURATO GIORNALIERO: € {incasso_giorno_squadra:,.2f}

    3. RISULTATO OPERATIVO
       Fatturato (€ {incasso_giorno_squadra:,.2f}) - Costo Manodopera (€ {costo_giorno_squadra:,.2f})
       = MARGINE INDUSTRIALE LORDO: € {margine_industriale_giorno:,.2f} /giorno
       
       Meno Spese Generali (Overheads € {overheads:.2f}/h): - € {costo_overheads_giorno:,.2f}
       ==========================================================
       RISULTATO NETTO FINALE: € {margine_netto_giorno:,.2f} /giorno
       ==========================================================

    4. RICHIESTA ADEGUAMENTO
    Il Costo di Break-Even (Pareggio) è certificato a € {bep_tariffa:.2f} /h.
    Si richiede l'adeguamento della tariffa a € {int(bep_tariffa)+1}.00 /h per garantire 
    la continuità operativa senza perdite.

    In Fede,
    L'Amministratore Unico
    """
    
    st.text_area("Copia il testo qui sotto:", value=audit_text, height=450)