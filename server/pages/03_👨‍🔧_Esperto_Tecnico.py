# server/pages/03_👨‍🔧_Esperto_Tecnico.py (Versione con Citazioni)

import os
import sys
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.knowledge_chain import get_expert_response

st.set_page_config(page_title="Esperto Tecnico", page_icon="👨‍🔧", layout="wide")

st.title("👨‍🔧 Esperto Tecnico da Documentazione")
st.markdown("Fai una domanda sui manuali e i documenti tecnici caricati nel sistema.")

if "expert_messages" not in st.session_state:
    st.session_state.expert_messages = [{
        "role": "assistant", 
        "content": "Ciao! Sono l'esperto tecnico. Fai una domanda sulla documentazione che ho studiato."
    }]

# Mostra la cronologia della chat
for message in st.session_state.expert_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # NUOVO: Se il messaggio dell'assistente ha delle fonti, le mostriamo
        if "sources" in message and message["sources"]:
            with st.expander("Mostra fonti consultate"):
                for source in message["sources"]:
                    st.info(f"Fonte: **{source['source']}** - Pagina: **{source['page']}**")


if prompt := st.chat_input("Qual è la procedura per la saldatura TIG?"):
    # Aggiungi il messaggio dell'utente alla cronologia
    st.session_state.expert_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Mostra la risposta dell'assistente
    with st.chat_message("assistant"):
        with st.spinner("Sto consultando la documentazione..."):
            # Chiamiamo la nostra funzione che ora ritorna un dizionario
            response_data = get_expert_response(prompt)
            
            response_text = response_data["answer"]
            sources = response_data["sources"]
            
            st.markdown(response_text)
            
            # NUOVO: Mostriamo le fonti sotto la risposta
            if sources:
                with st.expander("Mostra fonti consultate"):
                    for source in sources:
                        st.info(f"Fonte: **{source['source']}** - Pagina: **{source['page']}**")
    
    # Aggiungi la risposta completa (testo + fonti) alla cronologia
    st.session_state.expert_messages.append({
        "role": "assistant",
        "content": response_text,
        "sources": sources
    })