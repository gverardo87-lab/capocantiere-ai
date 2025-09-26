# server/pages/07_🌦️_Meteo_Cantiere.py (Versione Definitiva con OpenWeatherMap)
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.weather_api import get_coords_for_city, get_weather_forecast, get_weather_maps_urls

st.set_page_config(page_title="Meteo Cantiere", page_icon="🌦️", layout="wide")

st.title("🌦️ Meteo e Condizioni Operative Cantiere")

# Controlla se la chiave API è presente
if not os.getenv("OPENWEATHER_API_KEY"):
    st.error("Manca la chiave API di OpenWeatherMap!")
    st.info("Per favore, segui questi passi:\n1. Crea un file `.env` nella cartella principale del progetto.\n2. Aggiungi questa riga: `OPENWEATHER_API_KEY=\"la_tua_chiave_api\"`")
    st.stop()

st.sidebar.header("📍 Località Cantiere")
city_name = st.sidebar.text_input("Inserisci una città", value="Imperia")
search_button = st.sidebar.button("Cerca Previsioni", type="primary")

if 'weather_data' not in st.session_state: st.session_state.weather_data = None
if 'location_name' not in st.session_state: st.session_state.location_name = None

if search_button:
    coords_result = get_coords_for_city(city_name)
    if coords_result:
        lat, lon, found_name = coords_result
        st.session_state.location_name = found_name
        st.session_state.weather_data = get_weather_forecast(lat, lon)
    else:
        st.session_state.weather_data = None
        st.session_state.location_name = None
        st.sidebar.error(f"Città '{city_name}' non trovata.")

tab1, tab2, tab3 = st.tabs(["📊 Previsione 5 Giorni", "🛰️ Satellite Europa", "🗺️ Isobare Europa"])

with tab1:
    if st.session_state.weather_data is not None:
        df = st.session_state.weather_data
        st.success(f"Previsioni per **{st.session_state.location_name}**")
        
        today = df.iloc[0]
        st.subheader(f"Condizioni per Oggi ({today['Data'].strftime('%A %d')}) - {today['Descrizione']}")

        col1, col2, col3 = st.columns(3)
        col1.metric("🌡️ Temperatura Max", f"{today['Temp (°C)']:.1f} °C")
        col2.metric("💧 Precipitazioni", f"{today['Precipitazioni (mm)']:.1f} mm")
        col3.metric("💨 Vento Max", f"{today['Vento (km/h)']:.1f} km/h", f"Raffica {today['Raffica (km/h)']:.1f} km/h")
        st.divider()

        st.subheader("Andamento Prossimi Giorni")
        fig = px.bar(df, x='Data', y='Precipitazioni (mm)', title='Temperature e Precipitazioni Previste', labels={'Data': ''})
        fig.add_scatter(x=df['Data'], y=df['Temp (°C)'], mode='lines+markers', name='Temp. Max', yaxis='y2')
        fig.update_layout(yaxis_title='Precipitazioni (mm)', yaxis2=dict(title='Temperatura (°C)', overlaying='y', side='right'), legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("⬅️ Inserisci una città e clicca 'Cerca Previsioni'.")

with tab2:
    st.header("Immagine Satellite Europa")
    urls = get_weather_maps_urls()
    st.image(urls["satellite"], caption=f"Fonte: Wetterzentrale.de - Aggiornato: {datetime.now().strftime('%H:%M')}", use_column_width=True)

with tab3:
    st.header("Carta Sinottica (Isobare)")
    urls = get_weather_maps_urls()
    st.image(urls["isobare"], caption=f"Fonte: Wetterzentrale.de - Aggiornato: {datetime.now().strftime('%H:%M')}", use_column_width=True)