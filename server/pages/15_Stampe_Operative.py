# server/pages/15_Stampe_Operative.py
from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.shift_service import shift_service
except ImportError as e:
    st.error(f"Errore critico: {e}")
    st.stop()

st.set_page_config(page_title="Riepilogo Ore", page_icon="📋", layout="wide")

# ==============================================================================
# 1. SETUP DATI
# ==============================================================================
st.title("📋 Riepilogo Ore Mensile")

c1, c2, c3 = st.columns([1, 1, 2])
today = date.today()
def_m = today.month - 1 if today.day < 10 else today.month
def_y = today.year
if def_m == 0: def_m=12; def_y-=1

nomi_mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

with c1:
    sel_mese = st.selectbox("Mese", options=nomi_mesi, index=def_m-1)
    n_mese = nomi_mesi.index(sel_mese) + 1
with c2:
    sel_anno = st.number_input("Anno", value=def_y, step=1)
with c3:
    try:
        df_dip = shift_service.get_dipendenti_df(solo_attivi=True)
        d_map = {i: f"{r['cognome']} {r['nome']}" for i, r in df_dip.iterrows()}
        sel_dip = st.selectbox("Dipendente", options=d_map.keys(), format_func=lambda x: d_map[x])
    except: st.stop()

st.divider()

# ==============================================================================
# 2. LOGICA "SMART MERGE" (Il trucco per pulire le righe)
# ==============================================================================
start = date(sel_anno, n_mese, 1)
end = date(sel_anno, n_mese, calendar.monthrange(sel_anno, n_mese)[1])

df_rep = shift_service.get_report_data_df(start, end)
df_w = df_rep[df_rep['id_dipendente'] == sel_dip].copy() if not df_rep.empty else pd.DataFrame()

if df_w.empty:
    st.warning("⚠️ Nessun dato trovato per il periodo selezionato.")
else:
    # Ordiniamo per data/ora
    df_w.sort_values('data_ora_inizio', inplace=True)
    
    merged_rows = []
    
    # Iteriamo per unire i turni spezzati dalla mezzanotte
    buffer_row = None

    for _, row in df_w.iterrows():
        current_start = row['data_ora_inizio']
        current_end = row['data_ora_fine']
        current_hours = row['ore_presenza']
        current_act = str(row['id_attivita'])
        
        if buffer_row:
            # Controllo se questo turno è la continuazione del precedente
            # Criterio: Stessa attività E il precedente finiva alle 23:59/00:00 E questo inizia a 00:00
            prev_end = buffer_row['end']
            
            # Tolleranza di 1 minuto per il cambio data
            diff_seconds = (current_start - prev_end).total_seconds()
            
            is_continuation = (0 <= diff_seconds <= 60) and (current_start.hour == 0)
            
            if is_continuation:
                # UNISCO!
                buffer_row['end'] = current_end
                buffer_row['hours'] += current_hours
                # L'attività resta quella del padre
                continue # Salto al prossimo, ho già gestito questo pezzo
            else:
                # Non è continuazione, salvo il buffer e inizio nuovo buffer
                merged_rows.append(buffer_row)
                buffer_row = None # Reset
        
        # Creo nuovo buffer
        buffer_row = {
            'start': current_start,
            'end': current_end,
            'hours': current_hours,
            'activity': current_act
        }
    
    # Aggiungo l'ultimo rimasto appeso
    if buffer_row:
        merged_rows.append(buffer_row)

    # ==============================================================================
    # 3. PREPARAZIONE TABELLA VISUALE
    # ==============================================================================
    view_data = []
    tot_ore = 0.0
    
    for item in merged_rows:
        d_s = item['start']
        d_e = item['end']
        ore = item['hours']
        att_cod = item['activity']
        
        tot_ore += ore
        
        # Descrizione & Icona
        desc = att_cod if att_cod != "-1" else "Ordinario"
        if "OFF" in att_cod: desc = "🔧 Officina"
        elif "VIAGGIO" in att_cod: desc = "🚚 Trasferta"
        else:
            # Se è notte (o scavalca la notte), mettiamo icona luna
            h = d_s.hour
            if h >= 20 or h < 6: desc = "🌙 " + desc
            elif 18 <= h < 20: desc = "🌗 " + desc
            else: desc = "☀️ " + desc

        # Formattazione Orario Intelligente
        # Se finisce il giorno dopo, lo indichiamo
        str_orario = f"{d_s.strftime('%H:%M')} - {d_e.strftime('%H:%M')}"
        if d_e.date() > d_s.date():
            str_orario += " (+1)" # Indica giorno dopo

        view_data.append({
            "Data": d_s.strftime('%d/%m'),
            "Giorno": d_s.strftime('%A'),
            "Attività": desc,
            "Orario": str_orario,
            "Ore": f"{ore:g}", # Toglie i decimali .0 se interi
            "Visto": "......" 
        })
        
    df_view = pd.DataFrame(view_data)

    # --- OUTPUT STREAMLIT ---
    
    # Intestazione stile "Documento"
    info = df_dip.loc[sel_dip]
    st.markdown(f"### {info['cognome']} {info['nome']} - {info['ruolo']}")
    st.caption(f"Periodo: {sel_mese} {sel_anno} | Totale Ore: {tot_ore:g}")
    
    # TABELLA
    st.table(df_view)
    
    # FOOTER
    st.markdown("---")
    c_tot, c_legal = st.columns([1, 2])
    with c_tot:
        st.metric("TOTALE", f"{tot_ore:g} Ore")
    with c_legal:
        st.info("Firma per accettazione: __________________________")

    st.markdown("<br><small>Stampa con CTRL+P</small>", unsafe_allow_html=True)