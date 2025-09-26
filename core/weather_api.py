# core/weather_api.py (Versione Definitiva con Logica e Link Corretti)
import requests
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

# Leggi la chiave API dall'ambiente
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

GEOCODING_API_URL = "http://api.openweathermap.org/geo/1.0/direct"
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/forecast"

def get_coords_for_city(city_name: str) -> tuple[float, float, str] | None:
    """Converte un nome di città in coordinate (lat, lon)."""
    if not OPENWEATHER_API_KEY:
        print("ERRORE: Manca la chiave API di OpenWeatherMap")
        return None
        
    params = {"q": city_name, "limit": 1, "appid": OPENWEATHER_API_KEY}
    try:
        response = requests.get(GEOCODING_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # --- CORREZIONE CRUCIALE QUI ---
        # Controlliamo se la lista 'data' non è vuota prima di accedere a un elemento.
        if data and isinstance(data, list) and len(data) > 0:
            result = data[0]
            return result["lat"], result["lon"], f"{result.get('name', '')}, {result.get('country', '')}"
        
        # Se la lista è vuota, significa che la città non è stata trovata.
        print(f"Città '{city_name}' non trovata dalla API.")
        return None

    except Exception as e:
        print(f"Errore durante la ricerca della città (Geocoding): {e}")
        return None

def get_weather_forecast(latitude: float, longitude: float) -> pd.DataFrame | None:
    """Ottiene le previsioni per 5 giorni."""
    if not OPENWEATHER_API_KEY: return None
    params = {
        "lat": latitude, "lon": longitude, "appid": OPENWEATHER_API_KEY,
        "units": "metric", "lang": "it"
    }
    try:
        response = requests.get(WEATHER_API_URL, params=params)
        response.raise_for_status()
        data = response.json().get('list', [])
        
        records = []
        for item in data:
            records.append({
                "Data": datetime.fromtimestamp(item['dt']),
                "Temp (°C)": item['main']['temp'],
                "Precipitazioni (mm)": item.get('rain', {}).get('3h', 0),
                "Vento (km/h)": item['wind']['speed'] * 3.6,
                "Raffica (km/h)": item['wind'].get('gust', 0) * 3.6,
                "Descrizione": item['weather'][0]['description'].capitalize()
            })
        
        df = pd.DataFrame(records)
        df_daily = df.set_index('Data').resample('D').agg({
            'Temp (°C)': 'max', 'Precipitazioni (mm)': 'sum',
            'Vento (km/h)': 'max', 'Raffica (km/h)': 'max',
            'Descrizione': 'first'
        }).reset_index().fillna(method='ffill')
        return df_daily.head(7)

    except Exception as e:
        print(f"Errore durante il recupero delle previsioni meteo: {e}")
        return None

def get_weather_maps_urls() -> dict[str, str]:
    """Restituisce URL stabili per le mappe."""
    # Aggiungiamo un parametro casuale per evitare che il browser usi una vecchia immagine in cache
    cache_buster = datetime.now().strftime("%Y%m%d%H%M")
    
    return {
        "isobare": f"https://www.wetterzentrale.de/maps/GFSOPEU00_0_1.png?{cache_buster}",
        # --- NUOVO LINK STABILE PER IL SATELLITE ---
        "satellite": f"https://cdn.sat24.com/images/it/it/europa/latest.jpg?{cache_buster}"
    }