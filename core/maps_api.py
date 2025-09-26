# core/maps_api.py (Versione con carte a colori ad alta risoluzione)
from datetime import datetime

def get_technical_maps_urls() -> dict[str, str]:
    """
    Restituisce gli URL delle migliori carte tecniche a colori per l'Europa.
    Fonte unica: DWD / Wetterzentrale.de per massima stabilità e qualità.
    """
    cache_buster = datetime.now().strftime("%Y%m%d%H%M")
    base_url = "https://www.wetterzentrale.de/maps/"
    
    return {
        # Carta sinottica con pressione (isobare)
        "isobare_europa": f"{base_url}GFSOPEU00_0_1.png?{cache_buster}",
        
        # Carta del vento a 10 metri (a colori)
        "vento_europa": f"{base_url}GFSOPEU00_24_2.png?{cache_buster}",
        
        # Carta dell'altezza delle onde (a colori)
        "onde_europa": f"{base_url}GFSOPEU00_168_6.png?{cache_buster}"
    }