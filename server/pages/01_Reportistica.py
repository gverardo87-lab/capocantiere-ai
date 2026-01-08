# file: server/pages/01_Reportistica.py (Versione 33.0 - GOLD MASTER: Audit Granulare)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import io 

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
    from core.logic import ShiftEngine 
except ImportError as e:
    st.error(f"Errore critico moduli: {e}")
    st.stop()

st.set_page_config(page_title="Centro Report & Audit Costi", page_icon="📊", layout="wide")

st.title("📊 Centro Report & Audit Industriale")
st.markdown("Analisi Operativa e **Simulatore Finanziario Integrato**.")

# --- HELPER STILI ---
def style_internal(val):
    if not isinstance(val, (int, float)) or val == 0: return 'color: #e0e0e0'
    if val < 8: return 'background-color: #dbeafe; color: black' 
    if val <= 10: return 'background-color: #93c5fd; color: black' 
    return 'background-color: #2563eb; color: white'

def style_external(val):
    if not isinstance(val, (int, float)) or val == 0: return 'color: #e0e0e0'
    if val < 8: return 'background-color: #ffedd5; color: black' 
    if val <= 9: return 'background-color: #fdba74; color: black' 
    return 'background-color: #ea580c; color: white' 

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=600)
def load_activities_map():
    activities_map = {"VIAGGIO": "VIAGGIO", "STRAORDINARIO": "STRAORDINARIO", "OFFICINA": "OFFICINA", "-1": "N/A"}
    try:
        schedule_data = schedule_db_manager.get_schedule_data()
        df_s = pd.DataFrame(schedule_data)
        if not df_s.empty: activities_map.update(df_s.set_index('id_attivita')['descrizione'].to_dict())
    except: pass
    return activities_map

@st.cache_data(ttl=50)
def load_squadra_map():
    try:
        squadre = shift_service.get_squadre()
        d_map = {}
        for sq in squadre:
            mems = shift_service.get_membri_squadra(sq['id_squadra'])
            for mid in mems: d_map[mid] = sq['nome_squadra']
        return d_map
    except: return {}

def map_activity_id(id_att, activities_map):
    if pd.isna(id_att) or id_att == "-1": return "N/A"
    return activities_map.get(id_att, f"Attività {id_att}")

@st.cache_data(ttl=60)
def load_processed_data(start_date, end_date):
    df = shift_service.get_report_data_df(start_date, end_date)
    if df.empty: return pd.DataFrame()
    act_map = load_activities_map()
    sq_map = load_squadra_map()
    df['desc_attivita'] = df['id_attivita'].apply(map_activity_id, args=(act_map,))
    df['squadra'] = df['id_dipendente'].map(sq_map).fillna("Non Assegnato")
    df['giorno'] = df['data_ora_inizio'].dt.date
    if 'ore_presenza' not in df.columns: df['ore_presenza'] = 0.0
    if 'ore_lavoro' not in df.columns: df['ore_lavoro'] = 0.0
    mask = df['ore_presenza'].isna()
    if mask.any():
        calc = df[mask].apply(lambda r: ShiftEngine.calculate_professional_hours(r['data_ora_inizio'], r['data_ora_fine']), axis=1, result_type='expand')
        df.loc[mask, 'ore_presenza'] = calc[0]
        df.loc[mask, 'ore_lavoro'] = calc[1]
    return df

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    return output.getvalue()

# --- FILTRI ---
st.subheader("Pannello di Controllo")
if 'report_loaded' not in st.session_state: st.session_state.report_loaded = False
with st.container(border=True):
    c1, c2, c3 = st.columns([1, 1, 2])
    today = date.today()
    d_start = st.session_state.get('rep_start', today.replace(day=1))
    d_end = st.session_state.get('rep_end', today)
    with c1: d_in = st.date_input("Dal", d_start)
    with c2: d_out = st.date_input("Al", d_end)
    with c3: 
        st.write("")
        st.write("")
        if st.button("Applica Filtri e Carica", type="primary", use_container_width=True):
            st.session_state.rep_start = d_in
            st.session_state.rep_end = d_out
            st.session_state.report_loaded = True
            st.rerun()

if not st.session_state.report_loaded:
    st.info("Imposta un intervallo di date e clicca 'Applica Filtri'.")
    st.stop()

try:
    with st.spinner("Elaborazione..."):
        df_proc = load_processed_data(st.session_state.rep_start, st.session_state.rep_end)
        if df_proc.empty: st.warning("Nessun dato."); st.stop()
except Exception as e: st.error(f"Errore: {e}"); st.stop()

st.header(f"Report dal {st.session_state.rep_start.strftime('%d/%m/%Y')} al {st.session_state.rep_end.strftime('%d/%m/%Y')}")

with st.expander("Filtri Avanzati", expanded=False):
    f1, f2, f3 = st.columns(3)
    with f1: s_dip = st.multiselect("Dipendente", sorted(df_proc['dipendente_nome'].unique()))
    with f2: s_sq = st.multiselect("Squadra", sorted(df_proc['squadra'].unique()))
    with f3: s_act = st.multiselect("Attività", sorted(df_proc['desc_attivita'].unique()))

df_filtered = df_proc.copy()
if s_dip: df_filtered = df_filtered[df_filtered['dipendente_nome'].isin(s_dip)]
if s_sq: df_filtered = df_filtered[df_filtered['squadra'].isin(s_sq)]
if s_act: df_filtered = df_filtered[df_filtered['desc_attivita'].isin(s_act)]

if df_filtered.empty: st.warning("Nessun dato con i filtri attuali."); st.stop()

# --- TABS UNIFICATI ---
tab1, tab2, tab3, tab_audit = st.tabs(["📊 Dashboard", "🔍 Pivot", "📥 Export", "⚖️ AUDIT & SIMULATORE"])

# TAB 1: DASHBOARD
with tab1:
    tot_p, tot_l = df_filtered['ore_presenza'].sum(), df_filtered['ore_lavoro'].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Ore Presenza", f"{tot_p:,.1f}")
    k2.metric("Ore Lavoro", f"{tot_l:,.1f}")
    k3.metric("Delta", f"{tot_p-tot_l:,.1f}", delta="Non Produttive", delta_color="inverse")
    st.divider()
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.pie(df_filtered.groupby('squadra')['ore_lavoro'].sum().reset_index(), names='squadra', values='ore_lavoro', title="Ore per Squadra"), use_container_width=True)
    c2.plotly_chart(px.bar(df_filtered.groupby('giorno')[['ore_presenza', 'ore_lavoro']].sum().reset_index(), x='giorno', y=['ore_presenza', 'ore_lavoro'], title="Trend"), use_container_width=True)

# TAB 2: PIVOT
with tab2:
    st.subheader("1. STATINO INTERNO")
    try:
        p1 = pd.pivot_table(df_filtered, index=['squadra', 'dipendente_nome'], columns='giorno', values='ore_presenza', aggfunc='sum', fill_value=0, margins=True)
        st.dataframe(p1.style.format("{:.1f}").map(style_internal), use_container_width=True)
    except: st.error("Errore pivot")
    st.divider()
    st.subheader("2. REPORT CANTIERE")
    try:
        p2 = pd.pivot_table(df_filtered, index=['squadra', 'dipendente_nome'], columns='giorno', values='ore_lavoro', aggfunc='sum', fill_value=0, margins=True)
        st.dataframe(p2.style.format("{:.1f}").map(style_external), use_container_width=True)
    except: pass

# TAB 3: EXPORT
with tab3:
    col_map = {'giorno': 'Data', 'squadra': 'Squadra', 'dipendente_nome': 'Nome', 'ruolo': 'Ruolo', 'desc_attivita': 'Attività', 'ore_presenza': 'Presenza', 'ore_lavoro': 'Lavoro'}
    cols = [c for c in col_map.keys() if c in df_filtered.columns]
    df_exp = df_filtered[cols].rename(columns=col_map)
    st.download_button("Scarica Excel", to_excel(df_exp), f"Report_{date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheet_ml.sheet", type="primary")
    st.dataframe(df_exp, hide_index=True)

# ==============================================================================
# ★ TAB 4: AUDIT UNIFICATO & CORRETTO ★
# ==============================================================================
with tab_audit:
    st.markdown("## ⚖️ Control Room Finanziaria (Analisi Squadra Tipo)")
    
    # --- LAYOUT A COLONNE PER INPUT ---
    with st.expander("🛠️ CONFIGURAZIONE PARAMETRI DI COMMESSA", expanded=True):
        ic1, ic2, ic3, ic4 = st.columns(4)
        
        with ic1:
            st.markdown("**1. STRUTTURA SQUADRA**")
            n_op = st.number_input("N. Operai", 1, 50, 6)
            n_cap = st.number_input("N. Capisquadra", 0, 10, 1)
            tot_pax = n_op + n_cap
            st.info(f"Squadra: **{tot_pax}** Persone")

        with ic2:
            st.markdown("**2. COSTI (Busta+Oneri)**")
            net_op = st.number_input("Netto Operaio (€/h)", 0.0, 50.0, 13.00, format="%.2f")
            one_op = st.number_input("Oneri Operaio (€/gg)", 0.0, 100.0, 42.00, format="%.2f", help="INPS, INAIL, Ratei, TFR giornalieri")
            net_cap = st.number_input("Netto Capo (€/h)", 0.0, 60.0, 16.00, format="%.2f")
            one_cap = st.number_input("Oneri Capo (€/gg)", 0.0, 150.0, 48.00, format="%.2f")

        with ic3:
            st.markdown("**3. SPESE VIVE & GENERALI**")
            ticket = st.number_input("Ticket/Viaggio (€/gg)", 0.0, 100.0, 20.00, format="%.2f", help="Spesa viva per persona al giorno")
            ovh = st.number_input("Spese Gen. (€/h fatt.)", 0.0, 20.0, 2.28, format="%.2f", help="Costi fissi ufficio/auto ribaltati")
            h_pay = st.number_input("Ore Pagate (Input)", 0.0, 15.0, 10.0, step=0.5)

        with ic4:
            st.markdown("**4. RICAVI & PROIEZIONE**")
            h_bill = st.number_input("Ore Fatturate (Output)", 0.0, 15.0, 9.0, step=0.5)
            tariffa = st.number_input("Tariffa Cliente (€/h)", 0.0, 100.0, 27.00, format="%.2f")
            gg_mese = st.number_input("Giorni Mese", 1, 31, 22)
            n_squadre = st.number_input("Moltiplicatore Squadre", 1, 20, 1)

    # --- IL MOTORE DI CALCOLO (ANALITICO) ---
    
    # 1. Costi Personale (Busta + Oneri)
    costo_pers_op_gg = (net_op * h_pay) + one_op
    costo_pers_cap_gg = (net_cap * h_pay) + one_cap
    
    # 2. Spese Vive (Ticket)
    # Calcolate separate per trasparenza nel grafico
    ticket_tot_gg = ticket * tot_pax
    
    # 3. Costo Totale Squadra (Personale + Ticket)
    costo_labor_sq_gg = (costo_pers_op_gg * n_op) + (costo_pers_cap_gg * n_cap)
    costo_vivo_sq_gg = costo_labor_sq_gg + ticket_tot_gg
    
    # 4. Ricavi Squadra
    h_bill_sq = h_bill * tot_pax
    r_tot_sq_gg = h_bill_sq * tariffa
    
    # 5. Margine Industriale (Prima Overheads)
    marg_ind_gg = r_tot_sq_gg - costo_vivo_sq_gg
    
    # 6. Overheads e Netto
    c_ovh_sq_gg = ovh * h_bill_sq
    marg_net_gg = marg_ind_gg - c_ovh_sq_gg
    
    # 7. BEP (Break Even Point Tariffa)
    costo_pieno_sq = costo_vivo_sq_gg + c_ovh_sq_gg
    tariffa_bep = costo_pieno_sq / h_bill_sq if h_bill_sq > 0 else 0

    # 8. Proiezioni
    proj_mese = marg_net_gg * gg_mese * n_squadre
    tot_pax_campo = tot_pax * n_squadre

    # --- OUTPUT VISIVO (LO SCONTRINO PARLANTE) ---
    st.divider()
    c_left, c_right = st.columns([1.3, 1])

    with c_left:
        st.subheader("🧾 Scontrino Analitico (Squadra Giorno)")
        
        # HTML TABLE per massima chiarezza e dettaglio
        html_tab = f"""
        <table style="width:100%; border-collapse: collapse; font-size:14px;">
            <tr style="border-bottom: 2px solid #ccc; background-color: #f0f2f6;">
                <th style="text-align:left; padding:10px;">VOCE DI BILANCIO</th>
                <th style="text-align:right; padding:10px;">DETTAGLIO CALCOLO</th>
                <th style="text-align:right; padding:10px;">IMPORTO</th>
            </tr>
            <tr>
                <td style="padding:10px; color:#006600;"><b>(+) FATTURATO SQUADRA</b></td>
                <td style="text-align:right; color:#666;">{tot_pax} Uomini x {h_bill}h x € {tariffa:.2f}</td>
                <td style="text-align:right; font-weight:bold; color:#006600;">€ {r_tot_sq_gg:,.2f}</td>
            </tr>
            <tr>
                <td style="padding:10px;">(-) Personale Operai ({n_op})</td>
                <td style="text-align:right; color:#666;">{n_op} x [(€{net_op}x{h_pay}h)+€{one_op}]</td>
                <td style="text-align:right; color:#b91c1c;">€ {costo_pers_op_gg*n_op:,.2f}</td>
            </tr>
            <tr>
                <td style="padding:10px;">(-) Personale Capi ({n_cap})</td>
                <td style="text-align:right; color:#666;">{n_cap} x [(€{net_cap}x{h_pay}h)+€{one_cap}]</td>
                <td style="text-align:right; color:#b91c1c;">€ {costo_pers_cap_gg*n_cap:,.2f}</td>
            </tr>
            <tr>
                <td style="padding:10px;">(-) Spese Vive (Ticket/Viaggio)</td>
                <td style="text-align:right; color:#666;">€ {ticket:.2f} x {tot_pax} Persone</td>
                <td style="text-align:right; color:#b91c1c;">€ {ticket_tot_gg:,.2f}</td>
            </tr>
            <tr style="background-color: #fff8e1; font-weight:bold; border-top:1px solid #ddd;">
                <td style="padding:10px;">= MARGINE INDUSTRIALE</td>
                <td style="text-align:right;">Ricavi - (Pers + Ticket)</td>
                <td style="text-align:right;">€ {marg_ind_gg:,.2f}</td>
            </tr>
            <tr>
                <td style="padding:10px;">(-) Spese Generali (Struttura)</td>
                <td style="text-align:right; color:#666;">€ {ovh:.2f} x {h_bill_sq} ore fatt.</td>
                <td style="text-align:right; color:#b91c1c;">€ {c_ovh_sq_gg:,.2f}</td>
            </tr>
            <tr style="border-top: 2px solid #000; background-color: {'#d1e7dd' if marg_net_gg >= 0 else '#f8d7da'};">
                <td style="padding:12px; font-size:16px;"><b>= UTILE NETTO (Giorno)</b></td>
                <td></td>
                <td style="text-align:right; font-size:16px; font-weight:bold; color:{'#0f5132' if marg_net_gg >= 0 else '#842029'};">€ {marg_net_gg:,.2f}</td>
            </tr>
        </table>
        """
        st.markdown(html_tab, unsafe_allow_html=True)
        
        st.write("")
        st.markdown("#### 🚀 Proiezione Finanziaria")
        kp1, kp2 = st.columns(2)
        kp1.metric("Tariffa di Pareggio (BEP)", f"€ {tariffa_bep:.2f}", delta=f"{tariffa-tariffa_bep:.2f} vs Attuale", delta_color="normal" if tariffa>=tariffa_bep else "inverse")
        kp2.metric(f"Risultato Mese ({tot_pax_campo} Pax)", f"€ {proj_mese:,.2f}", delta="UTILE" if proj_mese>=0 else "PERDITA", delta_color="normal" if proj_mese>=0 else "inverse")

    with c_right:
        st.subheader("📉 Cascata dei Margini")
        st.caption("Analisi visiva dell'erosione del valore giornaliero.")
        
        # Waterfall Chart Granulare
        fig = go.Figure(go.Waterfall(
            orientation = "v",
            measure = ["relative", "relative", "relative", "relative", "total", "relative", "total"],
            x = ["Fatturato", "Manodopera", "Ticket/Viaggi", "Margine Ind.", "Check", "Spese Gen.", "Utile Netto"],
            y = [
                r_tot_sq_gg, 
                -(costo_labor_sq_gg), 
                -(ticket_tot_gg), 
                0, 
                marg_ind_gg, # Check point visivo
                -c_ovh_sq_gg, 
                0
            ],
            text = [
                f"€{r_tot_sq_gg:.0f}", 
                f"-€{costo_labor_sq_gg:.0f}", 
                f"-€{ticket_tot_gg:.0f}", 
                f"{marg_ind_gg:.0f}", 
                None,
                f"-€{c_ovh_sq_gg:.0f}", 
                f"€{marg_net_gg:.0f}"
            ],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
            decreasing = {"marker":{"color":"#EF553B"}},
            increasing = {"marker":{"color":"#00CC96"}},
            totals = {"marker":{"color":"#1F77B4"}}
        ))
        fig.update_layout(showlegend=False, height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        if proj_mese < 0:
            st.error(f"🛑 **STOP:** Con {tot_pax_campo} uomini perdi **€ {abs(proj_mese):,.0f} al mese**.")
        else:
            st.success(f"✅ **GO:** Con {tot_pax_campo} uomini generi **€ {proj_mese:,.0f} al mese**.")