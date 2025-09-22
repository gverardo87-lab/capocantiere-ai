# knowledge_base/ask.py (Versione finale che usa la Knowledge Chain)

import os
import sys
from pathlib import Path

# Aggiungiamo la root del progetto al path per importare da altre cartelle
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    # Importiamo direttamente la nostra funzione "motore" dal core
    from core.knowledge_chain import get_expert_response
    print("INFO: Motore dell'esperto (Knowledge Chain) importato correttamente.")
except ImportError:
    print("ERRORE: Impossibile importare la logica da 'core/knowledge_chain.py'.")
    print("Assicurati che il file esista e che le librerie necessarie siano installate.")
    sys.exit(1)

# --- Esecuzione principale dello script ---
if __name__ == "__main__":
    print("\n\n*** Assistente Tecnico da Documentazione Attivo (Test da Console) ***")
    
    # Facciamo un ciclo per poter fare più domande
    while True:
        try:
            user_query = input("\nInserisci la tua domanda (o scrivi 'esci' per terminare): \n> ")
            if user_query.lower() == 'esci':
                break
            if not user_query.strip():
                continue
            
            # Chiamiamo la nostra funzione centrale per ottenere la risposta e le fonti
            print("--- Chiamo l'esperto... (potrebbe richiedere un po' di tempo) ---")
            response_data = get_expert_response(user_query)
            
            answer = response_data["answer"]
            sources = response_data["sources"]

            # Stampiamo i risultati in modo formattato
            print("\n" + "="*40)
            print("   RISPOSTA DELL'ESPERTO")
            print("="*40)
            print(answer)
            
            if sources:
                print("\n" + "-"*40)
                print("   FONTI CONSULTATE")
                print("-"*40)
                for source in sources:
                    print(f"- {source['source']}, Pagina: {source['page']}")
            print("="*40)

        except KeyboardInterrupt:
            # Permette di uscire con Ctrl+C in modo pulito
            print("\n\nUscita dal programma.")
            break
        except Exception as e:
            print(f"\nSi è verificato un errore inaspettato: {e}")