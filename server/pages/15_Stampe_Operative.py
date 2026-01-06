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
# CSS OTTIMIZZATO (DARK MODE + PRINT FRIENDLY)
# ==============================================================================
st.markdown("""
<style>
    /* STILE A VIDEO (Adattivo Dark/Light) */
    .clean-table { 
        width: 100%; 
        border-collapse: collapse; 
        font-family: sans-serif; 
        font-size: 15px; 
    }
    
    /* Intestazione: Usa il colore del tema corrente (non forzare bianco/nero) */
    .clean-table th { 
        text-align: left; 
        padding: 12px 10px; 
        border-bottom: 2px solid var(--text-color); /* Linea colore testo */
        opacity: 0.8;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 12px;
        letter-spacing: 1px;
    }
    
    .clean-table td { 
        padding: 10px; 
        border-bottom: 1px solid rgba(128, 128, 128, 0.2); /* Bordo sottile adattivo */
    }
    
    /* Righe alterne: Usa un colore molto tenue che va bene su entrambi i temi */
    .clean-table tr:nth-child(even) { 
        background-color: rgba(128, 128, 128, 0.05); 
    }

    /* STILE PER LA STAMPA (Forza Carta Bianca) */
    @media print {
        /* Nascondi interfaccia Streamlit */
        [data-testid="stSidebar"], header, footer, .stButton, .stSelectbox, .stNumberInput, .stAlert { display: none !important; }
        .block-container { padding: 0 !important; margin: 0 !important; }
        
        /* Forza BIANCO e NERO assoluto */
        body, .stApp {
            background-color: white !important;
            color: black !important;
        }
        
        .clean-table th { 
            color: black !important; 
            border-bottom: 2px solid black !important; 
        }
        .clean-table td { 
            color: black !important; 
            border-bottom: 1px solid #ddd !important; 
        }
        .clean-table tr:nth-child(even) { 
            background-color: #f9f9f9 !important; /* Grigio chiaro classico su carta */
        }
        
        /* Nascondi sfondi scuri */
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    }
</style>
""", unsafe_allow_html=True)

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
# 2. LOGICA (Smart Merge + Cambio Turno)
# ==============================================================================
start = date(sel_anno, n_mese, 1)
end = date(sel_anno, n_mese, calendar.monthrange(sel_anno, n_mese)[1])

df_rep = shift_service.get_report_data_df(start, end)
df_w = df_rep[df_rep['id_dipendente'] == sel_dip].copy() if not df_rep.empty else pd.DataFrame()

if df_w.empty:
    st.warning("⚠️ Nessun dato trovato per il periodo selezionato.")
else:
    df_w.sort_values('data_ora_inizio', inplace=True)
    
    # UNIONE TURNI (Smart Merge)
    merged_rows = []
    buffer_row = None

    for _, row in df_w.iterrows():
        current_start = row['data_ora_inizio']
        current_end = row['data_ora_fine']
        current_hours = row['ore_presenza']
        current_act = str(row['id_attivita'])
        
        if buffer_row:
            diff_sec = (current_start - buffer_row['end']).total_seconds()
            if (0 <= diff_sec <= 120) and (current_start.hour == 0):
                buffer_row['end'] = current_end
                buffer_row['hours'] += current_hours
                continue 
            else:
                merged_rows.append(buffer_row)
                buffer_row = None
        
        buffer_row = {
            'start': current_start,
            'end': current_end,
            'hours': current_hours,
            'activity': current_act
        }
    if buffer_row: merged_rows.append(buffer_row)

    # VISUALIZZAZIONE
    view_data = []
    tot_ore = 0.0
    prev_shift_type = None 

    for item in merged_rows:
        d_s = item['start']
        d_e = item['end']
        ore = item['hours']
        att_cod = item['activity']
        tot_ore += ore
        
        # Tipo Turno
        h = d_s.hour
        if "OFF" in att_cod: 
            curr_type = "OFFICINA"; icon = "🔧"
        elif "VIAGGIO" in att_cod:
            curr_type = "TRASFERTA"; icon = "🚚"
        elif h >= 20 or h < 6: 
            curr_type = "NOTTE"; icon = "🌙"
        elif 18 <= h < 20:
            curr_type = "SERA"; icon = "🌗"
        else:
            curr_type = "GIORNO"; icon = "☀️"

        # Descrizione
        desc = att_cod if att_cod not in ["-1", "nan", "None"] else f"Turno {curr_type.capitalize()}"
        if "OFF" in att_cod: desc = "Officina"
        if "VIAGGIO" in att_cod: desc = "Trasferta"

        # Rileva Cambio Turno (Giorno <-> Notte)
        tag_cambio = ""
        major_types = ["GIORNO", "NOTTE"]
        if prev_shift_type and curr_type in major_types and prev_shift_type in major_types:
            if curr_type != prev_shift_type:
                # Usa uno span con colore del tema (o rosso soft)
                tag_cambio = f" <span style='font-size:0.85em; opacity:0.8; margin-left:8px;'>🔀 <b>CAMBIO</b></span>"
        
        if ore > 4: prev_shift_type = curr_type

        # Formattazione Orario
        orario_str = f"{d_s.strftime('%H:%M')} - {d_e.strftime('%H:%M')}"
        if d_e.date() > d_s.date():
            orario_str += " <small>(+1)</small>"

        view_data.append({
            "DATA": f"<b>{d_s.day}</b> <small>{d_s.strftime('%a')}</small>",
            "ATTIVITÀ": f"<span style='font-size:1.1em'>{icon}</span> {desc} {tag_cambio}",
            "ORARIO": orario_str,
            "ORE": f"<b>{ore:g}</b>",
            "VISTO": "<span style='color:#ccc'>......</span>"
        })
        
    df_view = pd.DataFrame(view_data)

    # OUTPUT
    info = df_dip.loc[sel_dip]
    
    # Header Dati
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:end; border-bottom:1px solid #555; padding-bottom:10px; margin-bottom:15px;">
        <div>
            <h2 style="margin:0; padding:0;">{info['cognome']} {info['nome']}</h2>
            <div style="opacity:0.7;">{info['ruolo']} | Matr. #{sel_dip:04d}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:1.2em; font-weight:bold;">{sel_mese.upper()} {sel_anno}</div>
            <div style="opacity:0.7;">Riepilogo Ore</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # TABELLA HTML PULITA
    st.write(df_view.to_html(escape=False, index=False, classes="clean-table"), unsafe_allow_html=True)
    
    # FOOTER
    st.markdown("---")
    c_tot, c_sign = st.columns([1, 2])
    with c_tot:
        st.metric("TOTALE ORE", f"{tot_ore:g}")
    with c_sign:
        st.markdown(f"""
        <div style="margin-top:10px; border-top:1px solid #555; padding-top:5px; text-align:center; width:80%;">
            <small>Firma per accettazione</small><br>
            <br>
        </div>
        """, unsafe_allow_html=True)

    st.caption("💡 Premi CTRL+P per stampare (Versione Carta ottimizzata)")