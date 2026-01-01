# file: server/pages/12_Gestione_Squadre.py (Versione 16.2 - Fix TypeError)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
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

# --- 1. Elenco Squadre Attuali (Layout Migliorato) ---
st.subheader("Elenco Squadre Attuali")
if not lista_squadre:
    st.info("Nessuna squadra trovata. Creane una dal modulo 'Crea Nuova Squadra'.")
else:
    with st.container(border=True):
        # Visualizzazione a griglia (3 colonne) per risparmiare spazio
        cols = st.columns(3)
        for idx, squadra in enumerate(lista_squadre):
            with cols[idx % 3]:
                s_id = squadra['id_squadra']
                s_nome = squadra['nome_squadra']
                s_capo_id = squadra['id_caposquadra']
                
                membri_ids = shift_service.get_membri_squadra(s_id)
                num_membri = len(membri_ids)
                capo_str = opzioni_dipendenti.get(s_capo_id, "Nessuno") if s_capo_id else "Nessuno"
                
                with st.expander(f"**{s_nome}** ({num_membri} membri)"):
                    st.write(f"👑 **Capo:** {capo_str}")
                    if membri_ids:
                        st.markdown("👷‍♂️ **Membri:**")
                        for m in membri_ids:
                            nome = opzioni_dipendenti.get(m, f"ID {m}")
                            if m == s_capo_id: st.markdown(f"- **{nome}** (Capo)")
                            else: st.markdown(f"- {nome}")
                    else:
                        st.caption("Nessun membro assegnato.")

st.divider()

# --- 2. Modifica Squadra / Crea Nuova ---
tab1, tab2 = st.tabs(["➕ Crea Nuova Squadra", "✏️ Modifica Squadra Esistente"])

with tab1:
    st.subheader("Crea Nuova Squadra")
    with st.form("new_squadra_form", clear_on_submit=True):
        col_new_1, col_new_2 = st.columns([2, 1])
        with col_new_1:
            nome_nuova_squadra = st.text_input("Nome della Nuova Squadra")
        with col_new_2:
            caposquadra_id = st.selectbox(
                "Caposquadra (opzionale)",
                options=opzioni_dipendenti_con_nessuno.keys(),
                format_func=lambda x: opzioni_dipendenti_con_nessuno[x],
                key="new_capo"
            )
        
        submitted_new = st.form_submit_button("Crea Squadra", type="primary")
        
        if submitted_new:
            if not nome_nuova_squadra:
                st.warning("Il nome della squadra è obbligatorio.")
            else:
                try:
                    capo_id_db = caposquadra_id if caposquadra_id != 0 else None
                    new_id = shift_service.add_squadra(nome_nuova_squadra, capo_id_db)
                    st.success(f"Squadra '{nome_nuova_squadra}' creata con successo!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}. Probabilmente il nome della squadra esiste già.")

with tab2:
    st.subheader("Modifica Squadra Esistente")
    if not opzioni_squadre:
        st.info("Nessuna squadra da modificare.")
    else:
        # Selettore squadra fuori dal form per reattività
        c_sel, _ = st.columns([1, 2])
        with c_sel:
            squadra_id_da_gestire = st.selectbox(
                "Seleziona la squadra da modificare",
                options=opzioni_squadre.keys(),
                format_func=lambda x: opzioni_squadre[x],
            )

        if squadra_id_da_gestire:
            squadra_obj = next(s for s in lista_squadre if s['id_squadra'] == squadra_id_da_gestire)
            membri_attuali_ids = shift_service.get_membri_squadra(squadra_id_da_gestire)

            # --- FORM SOLO PER MODIFICHE ---
            with st.form(f"edit_squadra_form_{squadra_id_da_gestire}"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown("##### Dettagli")
                    nome_squadra = st.text_input("Nome Squadra", value=squadra_obj['nome_squadra'])
                    
                    capo_corrente = squadra_obj['id_caposquadra'] if squadra_obj['id_caposquadra'] else 0
                    if capo_corrente not in opzioni_dipendenti_con_nessuno: capo_corrente = 0 # Safety check
                    
                    caposquadra_nuovo_id_sel = st.selectbox(
                        "Caposquadra",
                        options=opzioni_dipendenti_con_nessuno.keys(),
                        format_func=lambda x: opzioni_dipendenti_con_nessuno[x],
                        key=f"edit_capo_{squadra_id_da_gestire}",
                        index=list(opzioni_dipendenti_con_nessuno.keys()).index(capo_corrente)
                    )
                
                with col2:
                    st.markdown("##### Membri")
                    # Filtra membri attuali per assicurarsi che esistano ancora in anagrafica
                    default_membri = [m for m in membri_attuali_ids if m in opzioni_dipendenti]
                    
                    membri_selezionati_ids = st.multiselect(
                        "Seleziona i componenti della squadra",
                        options=opzioni_dipendenti.keys(),
                        format_func=lambda x: opzioni_dipendenti[x],
                        default=default_membri,
                        key=f"edit_membri_{squadra_id_da_gestire}"
                        # RIMOSSO PARAMETRO HEIGHT CHE CAUSAVA ERRORE
                    )
                
                st.caption("Nota: Il Caposquadra viene aggiunto automaticamente ai membri se non selezionato.")
                
                submitted_edit = st.form_submit_button("💾 Salva Modifiche", type="primary")

                if submitted_edit:
                    try:
                        capo_db = caposquadra_nuovo_id_sel if caposquadra_nuovo_id_sel != 0 else None
                        
                        # Aggiorna Nome e Capo
                        shift_service.update_squadra_details(squadra_id_da_gestire, nome_squadra, capo_db)
                        
                        # Aggiorna Membri (unione selezione + capo)
                        lista_membri_finali = set(membri_selezionati_ids)
                        if capo_db: lista_membri_finali.add(capo_db)
                        
                        shift_service.update_membri_squadra(squadra_id_da_gestire, list(lista_membri_finali))
                        
                        st.success(f"Squadra '{nome_squadra}' aggiornata!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore durante l'aggiornamento: {e}")

            # --- ZONA PERICOLO (FUORI DAL FORM) ---
            # Questa sezione è ora fuori dal st.form, quindi i bottoni funzionano correttamente
            st.markdown("---")
            with st.expander("🚨 Zona Pericolo: Eliminazione Squadra"):
                st.warning(f"Stai per eliminare la squadra **{squadra_obj['nome_squadra']}**. Questa azione rimuoverà l'associazione della squadra, ma non cancellerà i turni passati.")
                
                col_del_1, col_del_2 = st.columns([1, 4])
                with col_del_1:
                    if st.button("🗑️ Conferma Eliminazione", key=f"btn_del_{squadra_id_da_gestire}", type="secondary"):
                        try:
                            shift_service.delete_squadra(squadra_id_da_gestire)
                            st.success("Squadra eliminata con successo.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante l'eliminazione: {e}")