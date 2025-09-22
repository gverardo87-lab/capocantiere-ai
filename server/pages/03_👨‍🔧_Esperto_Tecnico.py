# server/pages/03_👨‍🔧_Esperto_Tecnico.py
import os
import sys
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.knowledge_chain import get_expert_response

st.set_page_config(page_title="Esperto Tecnico", page_icon="👨‍🔧", layout="wide")

st.title("👨‍🔧 Esperto Tecnico da Documentazione")
st.markdown("Fai una domanda sui manuali e i documenti tecnici caricati nel sistema.")

if "expert_messages" not in st.session_state:
    st.session_state.expert_messages = [{"role": "assistant", "content": "Ciao! Sono l'esperto tecnico. Fai una domanda sulla documentazione che ho studiato."}]

for message in st.session_state.expert_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Qual è la procedura per la saldatura TIG?", key="expert_chat"):
    st.session_state.expert_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Sto consultando la documentazione..."):
            response = get_expert_response(prompt)
            st.markdown(response)
    st.session_state.expert_messages.append({"role": "assistant", "content": response})