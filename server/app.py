from __future__ import annotations
import streamlit as st

st.set_page_config(
    page_title="🏗️ CapoCantiere AI",
    page_icon="🏗️",
    layout="wide",
)

st.title("Benvenuto in CapoCantiere AI")
st.markdown(
    """
    **Applicazione per la gestione semplificata del personale e dei lavori di cantiere.**

    Questa applicazione è stata creata per aiutare i manager di cantiere a tenere traccia delle ore,
    del personale e delle commesse in modo efficiente.

    ---

    ### Come Iniziare:

    1.  **Carica Documenti:** Vai alla pagina `Carica Documenti` dal menu a sinistra per aggiungere nuovi file come rapportini ore, fatture o altri documenti.

    2.  **Gestisci Dati:** Usa le pagine `Personale` e `Commesse` per visualizzare e gestire le anagrafiche dei tuoi lavoratori e dei tuoi progetti.
    
    3.  **Visualizza Report:** La `Dashboard` offre una vista filtrabile delle ore lavorate, mentre la pagina `Riepilogo` fornisce una vista d'insieme aggregata.

    4.  **Assitente AI:** Fai domande in linguaggio naturale sui tuoi dati nella pagina `Assistente AI`.

    ---

    *Seleziona una pagina dal menu a sinistra per iniziare.*
    """
)

with st.sidebar:
    st.success("Seleziona una pagina per iniziare.")
    st.divider()
    # The "Svuota Memoria" button is a global action, so it can live here.
    if st.button("⚠️ Svuota Memoria Dati", type="primary", width='stretch', help="ATTENZIONE: Cancella tutti i documenti e i dati caricati!"):
        # We need to import db_manager here, only when needed.
        from core.db import db_manager
        with st.spinner("Cancellazione di tutti i dati in corso..."):
            db_manager.delete_all_data()
        st.session_state.clear()
        st.rerun()