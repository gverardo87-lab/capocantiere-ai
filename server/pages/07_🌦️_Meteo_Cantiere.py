# server/pages/07_🌦️_Meteo_Cantiere.py (Versione con Descrizioni Chiare)
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.weather_api import get_coords_for_city, get_weather_forecast

st.set_page_config(page_title="Meteo Cantiere", page_icon="🌦️", layout="wide")
st.title("🌦️ Previsioni Meteo Operative")
st.markdown("Dashboard dettagliata per la pianificazione delle attività di cantiere.")

st.sidebar.header("📍 Località Cantiere")
city_name = st.sidebar.text_input("Inserisci una città", value="Imperia")
search_button = st.sidebar.button("Cerca Previsioni", type="primary")

if 'weather_forecast' not in st.session_state: st.session_state.weather_forecast = None
if 'location_name' not in st.session_state: st.session_state.location_name = None

if search_button:
    coords = get_coords_for_city(city_name)
    if coords:
        lat, lon, found_name = coords
        st.session_state.location_name = found_name
        st.session_state.weather_forecast = get_weather_forecast(lat, lon)
    else:
        st.sidebar.error(f"Località '{city_name}' non trovata.")
        st.session_state.weather_forecast = None

if st.session_state.weather_forecast:
    forecast = st.session_state.weather_forecast
    df_daily = forecast['daily']
    df_hourly = forecast['hourly']
    
    st.success(f"Previsioni per **{st.session_state.location_name}** caricate.")
    
    today = df_daily.iloc[0]
    
    # --- NUOVA SEZIONE PANORAMICA ---
    st.subheader(f"Panoramica per Oggi ({today['Data'].strftime('%A %d')})")
    
    main_desc = f"## {today['Icona']} {today['Descrizione']}"
    st.markdown(main_desc)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🌡️ Temp. Max/Min", f"{today['Temp. Max (°C)']:.1f}° / {today['Temp. Min (°C)']:.1f}°")
    kpi2.metric("💧 Prob. Pioggia", f"{today['Prob. Pioggia (%)']:.0f}%", f"{today['Precipitazioni (mm)']:.1f} mm")
    kpi3.metric("💨 Vento Massima", f"{today['Vento (km/h)']:.1f} km/h", f"Raffica {today['Raffica (km/h)']:.1f} km/h")
    kpi4.metric("☀️ Indice UV Max", f"{today['Indice UV Max']:.1f}", help="Un valore > 6 richiede protezione solare.")
    st.divider()

    tab_daily, tab_hourly = st.tabs(["🗓️ Previsione Settimanale", "⏰ Dettaglio Orario (Prossime 48h)"])

    with tab_daily:
        st.subheader("Andamento Prossimi 7 Giorni")
        
        # Mostriamo le descrizioni anche nella tabella
        st.dataframe(
            df_daily[['Data', 'Descrizione', 'Temp. Max (°C)', 'Prob. Pioggia (%)', 'Vento (km/h)']],
            hide_index=True, use_container_width=True,
            column_config={"Data": st.column_config.DateColumn("Data", format="dddd, DD/MM")}
        )

    with tab_hourly:
        st.subheader("Previsione Oraria Dettagliata (Prossime 48 Ore)")
        df_hourly_48h = df_hourly[df_hourly['Ora'] <= df_hourly['Ora'].min() + pd.Timedelta(hours=48)]
        
        fig_hourly = px.line(df_hourly_48h, x='Ora', y='Temp. (°C)', title='Andamento Temperatura e Probabilità di Pioggia Oraria')
        fig_hourly.add_bar(x=df_hourly_48h['Ora'], y=df_hourly_48h['Prob. Pioggia (%)'], name='Prob. Pioggia', yaxis='y2')
        fig_hourly.update_layout(
            yaxis_title='Temperatura (°C)',
            yaxis2=dict(title='Prob. Pioggia (%)', overlaying='y', side='right', range=[0, 100]),
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig_hourly, use_container_width=True)

else:
    st.info("⬅️ Inserisci una località e clicca 'Cerca Previsioni' per iniziare.")