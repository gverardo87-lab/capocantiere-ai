# file: server/pages/12_Gestione_Squadre.py (Versione 17.1 - Resource & Role Management)
from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
from collections import Counter

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from core.shift_service import shift_service
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare `core.shift_service`: {e}")
    st.stop()

st.set_page_config(page_title="Gestione Squadre", page_icon="👥", layout="wide")
st.title("👥 Gestione Squadre & Risorse")
st.markdown("Gestione operativa delle squadre con visualizzazione dei ruoli e delle competenze.")

# --- HELPER: ICONE RUOLI ---
def get_role_icon(role_name: str) -> str:
    """Restituisce un'icona basata sul ruolo per impatto visivo immediato."""
    r = str(role_name).lower()
    if 'saldat' in r: return "👨‍🏭"
    if 'carpent' in r: return "🔨"
    if 'elettri' in r: return "⚡"
    if 'capo' in r or 'preposto' in r: return "👑"
    if 'gruista' in r or 'movim' in r: return "🏗️"
    if 'autist' in r: return "🚛"
    if 'manoval' in r: return "🦺"
    return "👷"

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=30)
def load_anagrafica_e_squadre():
    dipendenti = shift_service.get_dipendenti_df(solo_attivi=True)
    squadre = shift_service.get_squadre()
    return dipendenti, squadre

try:
    df_dipendenti, lista_squadre = load_anagrafica_e_squadre()
    
    # Mappa Completa: ID -> Nome Cognome (Ruolo)
    # Questa è la chiave per vedere il ruolo ovunque nei menu
    opzioni_dipendenti_display = {}
    dip_role_map = {} # Mappa di servizio ID -> Ruolo pulito
    
    for index, row in df_dipendenti.iterrows():
        ruolo = row['ruolo'] if pd.notna(row['ruolo']) else "N/D"
        icon = get_role_icon(ruolo)
        # Stringa formattata per i menu a tendina
        opzioni_dipendenti_display[index] = f"{row['cognome']} {row['nome']} | {icon} {ruolo}"
        dip_role_map[index] = ruolo

    # Calcolo Occupati Globali (Logica v17.0 mantenuta)
    dipendenti_occupati_global = set()
    squadra_members_map = {} 
    
    for s in lista_squadre:
        mems = shift_service.get_membri_squadra(s['id_squadra'])
        squadra_members_map[s['id_squadra']] = mems
        dipendenti_occupati_global.update(mems)

    opzioni_squadre = {s['id_squadra']: s['nome_squadra'] for s in lista_squadre}

except Exception as e:
    st.error(f"Impossibile caricare dati: {e}")
    st.stop()

# --- 1. DASHBOARD SQUADRE (VISUALIZZAZIONE LEADER) ---
st.subheader("Panoramica Squadre")
if not lista_squadre:
    st.info("Nessuna squadra definita.")
else:
    # Stile CSS per le card (opzionale, migliora leggibilità)
    st.markdown("""
    <style>
    div[data-testid="stExpander"] details summary p {
        font-weight: bold;
        font-size: 1.1em;
    }
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(3)
    for idx, squadra in enumerate(lista_squadre):
        with cols[idx % 3]:
            s_id = squadra['id_squadra']
            s_nome = squadra['nome_squadra']
            s_capo_id = squadra['id_caposquadra']
            
            membri_ids = squadra_members_map.get(s_id, [])
            num_membri = len(membri_ids)
            
            # Analisi Distribuzione Risorse (Resource Breakdown)
            ruoli_in_squadra = [dip_role_map.get(m, "Sconosciuto") for m in membri_ids]
            conteggio_ruoli = Counter(ruoli_in_squadra)
            # Crea stringa di riepilogo (es: 2 Saldatori, 1 Carpentiere)
            summary_parts = [f"{cnt} {ruolo}" for ruolo, cnt in conteggio_ruoli.items() if ruolo != "Sconosciuto"]
            summary_str = " • ".join(summary_parts) if summary_parts else "Nessuna specializzazione"

            # Nome Capo pulito (senza ruolo ridondante nella stringa breve)
            capo_row = df_dipendenti.loc[s_capo_id] if s_capo_id in df_dipendenti.index else None
            capo_str = f"{capo_row['cognome']} {capo_row['nome']}" if capo_row is not None else "⚠️ Manca Capo"

            with st.container(border=True):
                st.markdown(f"#### {s_nome}")
                st.caption(f"👑 **{capo_str}**")
                
                # Barra rapida composizione
                if summary_str:
                    st.info(f"📊 {summary_str}")
                
                with st.expander(f"Vedi {num_membri} Membri"):
                    if membri_ids:
                        for m in membri_ids:
                            display_name = opzioni_dipendenti_display.get(m, f"ID {m}")
                            if m == s_capo_id: 
                                st.markdown(f"**{display_name}** (Capo)")
                            else: 
                                st.markdown(f"- {display_name}")
                    else:
                        st.warning("Squadra vuota.")

st.divider()

# --- 2. MODIFICA / CREA (OPERATIVITÀ CON RUOLI) ---
tab1, tab2 = st.tabs(["➕ Crea Nuova Squadra", "✏️ Modifica Squadra Esistente"])

with tab1:
    st.subheader("Crea Nuova Squadra")
    with st.form("new_squadra_form", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        with c1: nome_nuova = st.text_input("Nome Squadra")
        with c2:
            # Filtro Liberi + Mostra Ruolo
            opz_capo = {0: "Nessuno"}
            opz_capo.update({k: v for k, v in opzioni_dipendenti_display.items() if k not in dipendenti_occupati_global})
            
            capo_id = st.selectbox("Caposquadra", options=opz_capo.keys(), format_func=lambda x: opz_capo[x], key="new_capo")
        
        if st.form_submit_button("Crea Squadra", type="primary"):
            if not nome_nuova:
                st.warning("Nome obbligatorio.")
            else:
                try:
                    cid = capo_id if capo_id != 0 else None
                    shift_service.add_squadra(nome_nuova, cid)
                    st.success("Squadra creata!"); st.cache_data.clear(); st.rerun()
                except Exception as e: st.error(f"Errore: {e}")

with tab2:
    st.subheader("Modifica Squadra")
    if not opzioni_squadre:
        st.info("Nessuna squadra.")
    else:
        s_id_edit = st.selectbox("Seleziona Squadra", options=opzioni_squadre.keys(), format_func=lambda x: opzioni_squadre[x])
        
        if s_id_edit:
            s_obj = next(s for s in lista_squadre if s['id_squadra'] == s_id_edit)
            m_ids = squadra_members_map.get(s_id_edit, [])

            # Filtro: Liberi + Membri Attuali
            occupati_altrove = dipendenti_occupati_global - set(m_ids)
            opz_filt = {k: v for k, v in opzioni_dipendenti_display.items() if k not in occupati_altrove}
            opz_capo_filt = {0: "Nessuno"}; opz_capo_filt.update(opz_filt)

            with st.form(f"edit_{s_id_edit}"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.markdown("##### Dettagli")
                    new_name = st.text_input("Nome", value=s_obj['nome_squadra'])
                    
                    cur_capo = s_obj['id_caposquadra'] if s_obj['id_caposquadra'] else 0
                    if cur_capo != 0 and cur_capo not in opz_capo_filt: # Fallback integrità
                        opz_capo_filt[cur_capo] = opzioni_dipendenti_display.get(cur_capo, "???")
                    
                    new_capo_id = st.selectbox("Caposquadra", options=opz_capo_filt.keys(), format_func=lambda x: opz_capo_filt[x], index=list(opz_capo_filt.keys()).index(cur_capo) if cur_capo in opz_capo_filt else 0)

                with c2:
                    st.markdown("##### Membri & Competenze")
                    def_mems = [m for m in m_ids if m in opz_filt]
                    
                    sel_mems = st.multiselect(
                        "Componi la squadra (Vedi ruoli)",
                        options=opz_filt.keys(),
                        format_func=lambda x: opz_filt[x], # Qui si vedono i ruoli!
                        default=def_mems,
                        placeholder="Aggiungi operai..."
                    )
                
                if st.form_submit_button("💾 Salva Modifiche", type="primary"):
                    try:
                        cid_db = new_capo_id if new_capo_id != 0 else None
                        shift_service.update_squadra_details(s_id_edit, new_name, cid_db)
                        
                        final_mems = set(sel_mems)
                        if cid_db: final_mems.add(cid_db)
                        
                        shift_service.update_membri_squadra(s_id_edit, list(final_mems))
                        st.success("Aggiornato!"); st.cache_data.clear(); st.rerun()
                    except Exception as e: st.error(f"Errore: {e}")

            # Delete
            with st.expander("🚨 Elimina Squadra"):
                st.warning(f"Eliminare **{s_obj['nome_squadra']}**?")
                if st.button("Conferma Eliminazione", key=f"del_{s_id_edit}"):
                    shift_service.delete_squadra(s_id_edit)
                    st.success("Eliminata."); st.cache_data.clear(); st.rerun()