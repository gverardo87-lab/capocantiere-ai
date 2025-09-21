from __future__ import annotations

import os
import sys
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.chat_logic import get_ai_response

st.title("💬 Assistente di Cantiere AI")
st.markdown("Fai una domanda in linguaggio naturale sui dati caricati nel sistema.")

# --- LOGICA CHAT ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Ciao! Fammi una domanda sui dati dei rapportini."}]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Quante ore ha lavorato Rossi Luca?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Sto pensando..."):
            response = get_ai_response(st.session_state.messages)
            st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

with st.sidebar:
    st.divider()
    if st.button("🔄 Svuota Conversazione", use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": "Ciao! La conversazione è stata resettata."}]
        st.rerun()
