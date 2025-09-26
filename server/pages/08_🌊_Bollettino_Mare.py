# server/pages/08_🌊_Meteo_Marino.py (Versione con layout corretto a piena larghezza)
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.weather_api import get_coords_for_city, get_marine_forecast
from core.maps_api import get_technical_maps_urls

st.set_page_config(page_title="Meteo Marino", page_icon="🌊", layout="wide")
st.title("🌊 Stazione Meteo Marittima")
st.markdown("Dati puntuali e carte sinottiche professionali per le operazioni marittime.")

# --- Logica per la ricerca e il recupero dati (INVARIATA) ---
st.sidebar.header("📍 Località Marittima")
city_name = st.sidebar.text_input("Inserisci un porto o una città costiera", value="Imperia")
search_button = st.sidebar.button("Ottieni Bollettino", type="primary")

if 'marine_data' not in st.session_state: st.session_state.marine_data = None
if 'marine_location' not in st.session_state: st.session_state.marine_location = None

if search_button:
    coords = get_coords_for_city(city_name)
    if coords:
        lat, lon, found_name = coords
        st.session_state.marine_location = found_name
        st.session_state.marine_data = get_marine_forecast(lat, lon)
    else:
        st.sidebar.error(f"Località '{city_name}' non trovata.")
        st.session_state.marine_data = None

# --- Interfaccia a TAB ---
tab_dati, tab_carte = st.tabs(["📊 Bollettino Dati", "🗺️ Carte Sinottiche"])

with tab_dati:
    st.header("Bollettino Dati Puntuali (Open-Meteo)")
    if st.session_state.marine_data is not None:
        df = st.session_state.marine_data
        st.success(f"Dati marini per **{st.session_state.marine_location}**")

        today = df.iloc[0]
        st.subheader(f"Condizioni Massime per Oggi ({today['Data'].strftime('%A %d')})")
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("🌊 Altezza Onde Massima", f"{today['Altezza Onde (m)']:.2f} m")
        kpi2.metric("⏱️ Periodo Onde Massimo", f"{today['Periodo Onde (s)']:.1f} s")
        kpi3.metric("🧭 Direzione Onde", f"{today['Direzione Onde (°)']:.0f}°")
        st.divider()

        st.subheader("Andamento Settimanale dell'Altezza delle Onde")
        fig = px.bar(df, x='Data', y='Altezza Onde (m)', text='Altezza Onde (m)')
        fig.update_traces(texttemplate='%{text:.2f}m', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⬅️ Inserisci una località e clicca il pulsante per generare il bollettino.")

with tab_carte:
    st.header("Carte Sinottiche Professionali (Modello GFS)")
    st.info("Fonte: DWD / Wetterzentrale.de. Le carte mostrano la situazione attuale o la previsione a breve termine.")

    maps = get_technical_maps_urls()
    
    st.subheader("Pressione e Isobare - Europa")
    st.image(maps["isobare_europa"], caption="Mostra le aree di alta (H) e bassa (L) pressione.", use_column_width=True)
    st.divider()
    
    st.subheader("Vento a 10m - Europa")
    st.image(maps["vento_europa"], caption="Mostra la velocità (a colori) e la direzione del vento.", use_column_width=True)
    st.divider()

    st.subheader("Stato del Mare (Onde) - Europa")
    st.image(maps["onde_europa"], caption="Mostra l'altezza significativa delle onde (a colori).", use_column_width=True)