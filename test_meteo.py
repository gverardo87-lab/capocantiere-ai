# test_meteo.py
import os
import requests
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

# Leggi la chiave API
api_key = os.getenv("OPENWEATHER_API_KEY")
city = "Imperia"

print(f"--- Sto testando la chiave API: ...{api_key[-5:]}") # Mostra solo le ultime 5 cifre

if not api_key:
    print("ERRORE: Chiave API non trovata nel file .env!")
else:
    # Costruisci l'URL per la richiesta
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={api_key}"

    try:
        # Esegui la richiesta
        response = requests.get(url)

        # Controlla il codice di stato
        if response.status_code == 200:
            print("✅ SUCCESSO! La chiave API funziona e la connessione è andata a buon fine.")
            print("Dati ricevuti:", response.json())
        elif response.status_code == 401:
            print("❌ ERRORE 401: La chiave API non è valida o non è ancora attiva.")
            print("Attendi ancora un po' o controlla di averla copiata correttamente.")
        else:
            print(f"❌ ERRORE {response.status_code}: Qualcosa è andato storto.")
            print("Dettagli:", response.text)

    except Exception as e:
        print(f"ERRORE di connessione: {e}")