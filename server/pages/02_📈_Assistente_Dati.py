# server/pages/02_📈_Assistente_Dati.py
import os
import sys
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.chat_logic import get_ai_response as get_data_assistant_response

st.set_page_config(page_title="Assistente Dati", page_icon="📈", layout="wide")

st.title("📈 Assistente Dati")
st.markdown("Fai una domanda sui dati dei rapportini caricati (ore, commesse, operai).")

if "data_messages" not in st.session_state:
    st.session_state.data_messages = [{"role": "assistant", "content": "Ciao! Chiedimi un riepilogo dei dati."}]

for message in st.session_state.data_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Quante ore ha lavorato Rossi Luca?", key="data_chat"):
    st.session_state.data_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Sto analizzando i dati..."):
            response = get_data_assistant_response(st.session_state.data_messages)
            st.markdown(response)
    st.session_state.data_messages.append({"role": "assistant", "content": response})