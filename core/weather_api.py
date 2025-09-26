# core/weather_api.py (Versione Definitiva - Mare ripristinato, Meteo corretto)
import requests
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

GEOCODING_API_URL = "http://api.openweathermap.org/geo/1.0/direct"
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"

def get_weather_description(code: int) -> tuple[str, str]:
    """Traduce il WMO WeatherCode in una descrizione e un'icona."""
    wmo_codes = {
        0: ("Sereno", "☀️"), 1: ("Prevalentemente sereno", "🌤️"), 2: ("Parzialmente nuvoloso", "⛅"),
        3: ("Nuvoloso", "☁️"), 45: ("Nebbia", "🌫️"), 48: ("Nebbia con brina", "🌫️"),
        51: ("Pioggerella leggera", "💧"), 53: ("Pioggerella moderata", "💧"), 55: ("Pioggerella intensa", "💧"),
        61: ("Pioggia leggera", "🌧️"), 63: ("Pioggia moderata", "🌧️"), 65: ("Pioggia forte", "🌧️"),
        71: ("Nevicata leggera", "🌨️"), 73: ("Nevicata moderata", "🌨️"), 75: ("Nevicata pesante", "🌨️"),
        80: ("Rovescio leggero", "🌦️"), 81: ("Rovescio moderato", "🌦️"), 82: ("Rovescio violento", "🌦️"),
        95: ("Temporale", "⛈️"), 96: ("Temporale con grandine", "⛈️"), 99: ("Temporale con grandine", "⛈️")
    }
    return wmo_codes.get(code, ("Non disponibile", "❓"))

def get_coords_for_city(city_name: str) -> tuple[float, float, str] | None:
    if not OPENWEATHER_API_KEY: return None
    params = {"q": city_name, "limit": 1, "appid": OPENWEATHER_API_KEY}
    try:
        response = requests.get(GEOCODING_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]["lat"], data[0]["lon"], f"{data[0].get('name', '')}, {data[0].get('country', '')}"
        return None
    except Exception: return None

def get_weather_forecast(latitude: float, longitude: float) -> dict | None:
    """Ottiene le previsioni meteo generali (funzione CORRETTA)."""
    params = {
        "latitude": latitude, "longitude": longitude,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,precipitation_sum,precipitation_probability_max,windspeed_10m_max,windgusts_10m_max",
        "hourly": "temperature_2m,precipitation_probability,weathercode,windspeed_10m",
        "timezone": "Europe/Rome"
    }
    try:
        response = requests.get(WEATHER_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        df_daily = pd.DataFrame(data['daily'])
        df_daily['Data'] = pd.to_datetime(df_daily['time'])
        desc, icon = zip(*df_daily['weathercode'].apply(get_weather_description))
        df_daily['Descrizione'] = desc
        df_daily['Icona'] = icon
        df_daily.rename(columns={
            "temperature_2m_max": "Temp. Max (°C)", "temperature_2m_min": "Temp. Min (°C)",
            "uv_index_max": "Indice UV Max", "precipitation_sum": "Precipitazioni (mm)",
            "precipitation_probability_max": "Prob. Pioggia (%)", "windspeed_10m_max": "Vento (km/h)",
            "windgusts_10m_max": "Raffica (km/h)"
        }, inplace=True)

        df_hourly = pd.DataFrame(data['hourly'])
        df_hourly['Ora'] = pd.to_datetime(df_hourly['time'])
        df_hourly.rename(columns={
            "temperature_2m": "Temp. (°C)", "precipitation_probability": "Prob. Pioggia (%)",
            "windspeed_10m": "Vento (km/h)"
        }, inplace=True)
        
        return {"daily": df_daily, "hourly": df_hourly}
    except Exception as e:
        print(f"ERRORE CRITICO in get_weather_forecast: {e}")
        return None

def get_marine_forecast(latitude: float, longitude: float) -> pd.DataFrame | None:
    """Ottiene le previsioni marine (funzione RIPRISTINATA E FUNZIONANTE)."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "wave_height,wave_direction,wave_period,wind_wave_height,wind_wave_direction",
        "timezone": "Europe/Rome"
    }
    try:
        response = requests.get(MARINE_API_URL, params=params)
        response.raise_for_status()
        data = response.json().get('hourly', {})
        if not data: return None
        
        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['time'])
        
        df.rename(columns={
            "time": "Data",
            "wave_height": "Altezza Onde (m)",
            "wave_direction": "Direzione Onde (°)",
            "wave_period": "Periodo Onde (s)",
        }, inplace=True, errors='ignore') # Ignora errori se alcune colonne non ci sono
        
        # Raggruppiamo per giorno, prendendo i valori massimi
        df_daily = df.set_index('Data').resample('D').max().reset_index()
        return df_daily

    except Exception as e:
        print(f"Errore durante il recupero delle previsioni marine: {e}")
        return None