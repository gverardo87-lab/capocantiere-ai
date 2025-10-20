# file: server/pages/12_Gestione_Squadre.py (Versione 16.0 - Architettura Service)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    # ★ IMPORT CORRETTO ★
    from core.shift_service import shift_service
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare `core.shift_service`: {e}")
    st.stop()

st.set_page_config(page_title="Gestione Squadre", page_icon="👥", layout="wide")
st.title("👥 Gestione Squadre")
st.markdown("Crea e assegna i dipendenti alle squadre di lavoro.")

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=30)
def load_anagrafica_e_squadre():
    # ★ CHIAMATE CORRETTE al service ★
    dipendenti = shift_service.get_dipendenti_df(solo_attivi=True)
    squadre = shift_service.get_squadre()
    return dipendenti, squadre

try:
    df_dipendenti, lista_squadre = load_anagrafica_e_squadre()
    
    opzioni_dipendenti = {index: f"{row['cognome']} {row['nome']}" for index, row in df_dipendenti.iterrows()}
    opzioni_dipendenti_con_nessuno = {0: "Nessuno"}
    opzioni_dipendenti_con_nessuno.update(opzioni_dipendenti)
    opzioni_squadre = {s['id_squadra']: s['nome_squadra'] for s in lista_squadre}

except Exception as e:
    st.error(f"Impossibile caricare dati: {e}")
    st.stop()

# --- 1. Elenco Squadre Attuali ("Cumulativo") ---
st.subheader("Elenco Squadre Attuali")
if not lista_squadre:
    st.info("Nessuna squadra trovata. Creane una dal modulo 'Crea Nuova Squadra'.")
else:
    with st.container(border=True):
        for squadra in lista_squadre:
            s_id = squadra['id_squadra']
            s_nome = squadra['nome_squadra']
            s_capo_id = squadra['id_caposquadra']
            
            capo_nome = ""
            if s_capo_id and s_capo_id in opzioni_dipendenti:
                capo_nome = f" (Caposquadra: {opzioni_dipendenti[s_capo_id]})"
                
            st.markdown(f"#### {s_nome}{capo_nome}")
            
            # ★ CHIAMATA CORRETTA al service ★
            membri_ids = shift_service.get_membri_squadra(s_id)
            if not membri_ids:
                st.write("Nessun membro assegnato.")
            else:
                nomi_membri = []
                for id_m in membri_ids:
                    nome = opzioni_dipendenti.get(id_m, f"ID Sconosciuto ({id_m})")
                    if id_m == s_capo_id:
                        nome = f"**{nome} (Capo)**"
                    nomi_membri.append(nome)
                
                st.markdown(f"**Membri ({len(nomi_membri)}):** " + ", ".join(nomi_membri))
            st.divider()

st.divider()

# --- 2. Modifica Squadra / Crea Nuova ---
tab1, tab2 = st.tabs(["➕ Crea Nuova Squadra", "✏️ Modifica Squadra Esistente"])

with tab1:
    st.subheader("Crea Nuova Squadra")
    with st.form("new_squadra_form", clear_on_submit=True):
        nome_nuova_squadra = st.text_input("Nome della Nuova Squadra")
        caposquadra_id = st.selectbox(
            "Seleziona Caposquadra (opzionale)",
            options=opzioni_dipendenti_con_nessuno.keys(),
            format_func=lambda x: opzioni_dipendenti_con_nessuno[x],
            key="new_capo"
        )
        
        submitted_new = st.form_submit_button("Crea Squadra")
        if submitted_new:
            if not nome_nuova_squadra:
                st.warning("Il nome della squadra è obbligatorio.")
            else:
                try:
                    capo_id_db = caposquadra_id if caposquadra_id != 0 else None
                    # ★ CHIAMATA CORRETTA al service ★
                    new_id = shift_service.add_squadra(nome_nuova_squadra, capo_id_db)
                    
                    if capo_id_db:
                        st.success(f"Squadra '{nome_nuova_squadra}' creata! **{opzioni_dipendenti[capo_id_db]}** è stato aggiunto automaticamente come caposquadra e membro.")
                    else:
                        st.success(f"Squadra '{nome_nuova_squadra}' (ID: {new_id}) creata senza caposquadra.")
                    
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}. Probabilmente il nome della squadra esiste già.")

with tab2:
    st.subheader("Modifica Squadra Esistente")
    if not opzioni_squadre:
        st.info("Nessuna squadra da modificare. Creane una prima.")
    else:
        squadra_id_da_gestire = st.selectbox(
            "Seleziona la squadra da modificare",
            options=opzioni_squadre.keys(),
            format_func=lambda x: opzioni_squadre[x],
            index=0 
        )

        if squadra_id_da_gestire:
            squadra_obj = next(s for s in lista_squadre if s['id_squadra'] == squadra_id_da_gestire)
            # ★ CHIAMATA CORRETTA al service ★
            membri_attuali_ids = shift_service.get_membri_squadra(squadra_id_da_gestire)

            with st.form(f"edit_squadra_form_{squadra_id_da_gestire}"):
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown("##### Dettagli Squadra")
                    nome_squadra = st.text_input("Nome Squadra", value=squadra_obj['nome_squadra'])
                    caposquadra_attuale_id = squadra_obj['id_caposquadra'] if squadra_obj['id_caposquadra'] else 0
                    caposquadra_nuovo_id_sel = st.selectbox(
                        "Seleziona Caposquadra",
                        options=opzioni_dipendenti_con_nessuno.keys(),
                        format_func=lambda x: opzioni_dipendenti_con_nessuno[x],
                        key=f"edit_capo_{squadra_id_da_gestire}",
                        index=list(opzioni_dipendenti_con_nessuno.keys()).index(caposquadra_attuale_id)
                    )
                    caposquadra_nuovo_id_db = caposquadra_nuovo_id_sel if caposquadra_nuovo_id_sel != 0 else None
                
                with col2:
                    st.markdown("##### Membri della Squadra")
                    st.markdown(f"Il caposquadra (**{opzioni_dipendenti_con_nessuno[caposquadra_nuovo_id_sel]}**) sarà sempre incluso.")
                    membri_selezionati_ids = st.multiselect(
                        "Aggiungi altri membri",
                        options=opzioni_dipendenti.keys(),
                        format_func=lambda x: opzioni_dipendenti[x],
                        default=membri_attuali_ids,
                        key=f"edit_membri_{squadra_id_da_gestire}",
                    )
                
                st.divider()
                
                c_submit, c_delete = st.columns([3, 1])
                with c_submit:
                    submitted_edit = st.form_submit_button("Salva Modifiche", type="primary", use_container_width=True)
                with c_delete:
                    submitted_delete = st.form_submit_button("🚨 Elimina Squadra", type="secondary", use_container_width=True)

                if submitted_edit:
                    try:
                        lista_membri_finali = set(membri_selezionati_ids)
                        if caposquadra_nuovo_id_db is not None:
                            lista_membri_finali.add(caposquadra_nuovo_id_db)

                        # ★ CHIAMATE CORRETTE al service ★
                        shift_service.update_squadra_details(squadra_id_da_gestire, nome_squadra, caposquadra_nuovo_id_db)
                        shift_service.update_membri_squadra(squadra_id_da_gestire, list(lista_membri_finali))
                        
                        st.success(f"Squadra '{nome_squadra}' aggiornata con successo!")
                        if caposquadra_nuovo_id_db and caposquadra_nuovo_id_db not in membri_selezionati_ids:
                            st.info(f"Il caposquadra {opzioni_dipendenti[caposquadra_nuovo_id_db]} è stato aggiunto automaticamente ai membri.")
                            
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore durante l'aggiornamento: {e}")
                
                if submitted_delete:
                    st.warning(f"Sei sicuro di voler eliminare la squadra '{nome_squadra}'? Questa azione è irreversibile.")
                    if st.button("Conferma Eliminazione Definitiva", type="primary", key=f"del_confirm_{squadra_id_da_gestire}"):
                        try:
                            # ★ CHIAMATA CORRETTA al service ★
                            shift_service.delete_squadra(squadra_id_da_gestire)
                            st.success("Squadra eliminata.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante l'eliminazione: {e}")