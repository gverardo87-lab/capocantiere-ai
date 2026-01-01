# file: server/pages/12_Gestione_Squadre.py (Versione 17.4 - Hierarchy & Readiness NO CLONE)
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
st.markdown("Gestione operativa con gerarchia dei ruoli e controllo di prontezza.")

# --- HELPER: GERARCHIA E ICONE ---
def get_role_metadata(role_name: str) -> tuple[str, int]:
    """
    Restituisce (Icona, Priorità). 
    Priorità più bassa = appare prima in lista (0=Capo ... 9=Manovale).
    """
    if not isinstance(role_name, str): return "👷", 9
    r = role_name.lower()
    
    # Livello 0: Comando
    if 'capo' in r or 'preposto' in r or 'responsabile' in r: return "👑", 0
    # Livello 1: Specializzati Tecnici
    if 'saldat' in r: return "👨‍🏭", 1
    if 'carpent' in r: return "🔨", 1
    if 'elettri' in r: return "⚡", 1
    # Livello 2: Operatori Macchine
    if 'gruista' in r or 'movim' in r: return "🏗️", 2
    if 'autist' in r: return "🚛", 2
    # Livello 3: Generici
    if 'manoval' in r: return "🦺", 3
    
    return "👷", 9 # Default

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=30)
def load_data_hierarchical():
    dipendenti = shift_service.get_dipendenti_df(solo_attivi=True)
    squadre = shift_service.get_squadre()
    
    # 1. Arricchiamo il DF con priorità per l'ordinamento
    dipendenti['icona'], dipendenti['priority'] = zip(*dipendenti['ruolo'].apply(get_role_metadata))
    
    # 2. Ordiniamo: Prima per Ruolo (Priority), poi Alfabetico
    dipendenti = dipendenti.sort_values(by=['priority', 'cognome', 'nome'])
    
    return dipendenti, squadre

try:
    df_dipendenti, lista_squadre = load_data_hierarchical()
    
    # Mappa Display Gerarchica (quella che si vede nei menu)
    opzioni_dipendenti_display = {}
    dip_role_map = {} 
    
    for index, row in df_dipendenti.iterrows():
        ruolo = row['ruolo'] if pd.notna(row['ruolo']) else "N/D"
        # La stringa display rispetta l'ordinamento del DF caricato
        opzioni_dipendenti_display[index] = f"{row['cognome']} {row['nome']} | {row['icona']} {ruolo}"
        dip_role_map[index] = ruolo

    # Calcolo Occupati Globali (per nascondere chi è già impegnato)
    dipendenti_occupati_global = set()
    squadra_members_map = {} 
    
    for s in lista_squadre:
        mems = shift_service.get_membri_squadra(s['id_squadra'])
        squadra_members_map[s['id_squadra']] = mems
        dipendenti_occupati_global.update(mems)

    opzioni_squadre = {s['id_squadra']: s['nome_squadra'] for s in lista_squadre}

except Exception as e:
    st.error(f"Dati non disponibili: {e}")
    st.stop()

# --- 1. DASHBOARD "CONTROL ROOM" (CON SEMAFORO) ---
st.subheader("Stato Operativo Squadre")
if not lista_squadre:
    st.info("Nessuna squadra definita.")
else:
    # CSS per badge e semafori
    st.markdown("""
    <style>
    .skill-badge { background-color:#e8f0fe; color:#1a73e8; padding:2px 6px; border-radius:4px; font-size:0.8em; border:1px solid #d2e3fc; margin-right:4px; }
    .status-ok { border-left: 4px solid #34a853; padding-left: 8px; }
    .status-warn { border-left: 4px solid #fbbc04; padding-left: 8px; }
    .status-crit { border-left: 4px solid #ea4335; padding-left: 8px; }
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(3)
    for idx, squadra in enumerate(lista_squadre):
        with cols[idx % 3]:
            s_id = squadra['id_squadra']
            s_nome = squadra['nome_squadra']
            s_capo_id = squadra['id_caposquadra']
            membri_ids = squadra_members_map.get(s_id, [])
            
            # -- CALCOLO READINESS (SEMAFORO) --
            has_capo = s_capo_id is not None and s_capo_id > 0
            has_members = len(membri_ids) > 0
            
            if not has_capo:
                status_icon = "🔴"
                status_class = "status-crit"
                status_msg = "Manca Capo"
            elif not has_members:
                status_icon = "🟠"
                status_class = "status-warn"
                status_msg = "Vuota"
            else:
                status_icon = "🟢"
                status_class = "status-ok"
                status_msg = "Operativa"

            # -- SKILL BREAKDOWN --
            ruoli = [dip_role_map.get(m, "") for m in membri_ids]
            badges = []
            for r, c in Counter([r for r in ruoli if r]).items():
                icon, _ = get_role_metadata(r)
                badges.append(f"{c}x {icon}")
            
            badges_html = "".join([f"<span class='skill-badge'>{b}</span>" for b in badges])

            # -- RENDER CARD --
            with st.container(border=True):
                # Header con semaforo
                st.markdown(f"<div class='{status_class}'><h4>{status_icon} {s_nome}</h4></div>", unsafe_allow_html=True)
                
                # Capo
                if has_capo:
                    capo_nom = df_dipendenti.loc[s_capo_id]['cognome'] + " " + df_dipendenti.loc[s_capo_id]['nome']
                    st.caption(f"👑 **{capo_nom}**")
                else:
                    st.caption(f"⚠️ {status_msg}")

                # Skills
                if badges_html: st.markdown(badges_html, unsafe_allow_html=True)
                else: st.caption("Nessuna risorsa assegnata.")

                # Dettaglio
                with st.expander(f"Dettagli ({len(membri_ids)})"):
                    for m in membri_ids:
                        dn = opzioni_dipendenti_display.get(m, f"ID {m}")
                        st.markdown(f"- {dn}")

st.divider()

# --- 2. GESTIONE (CREA / MODIFICA) ---
tab1, tab2 = st.tabs(["➕ Crea Nuova Squadra", "✏️ Modifica Squadra"])

with tab1:
    st.subheader("Crea Nuova Squadra")
    with st.form("new_squadra_form", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        with c1: 
            nome_nuova = st.text_input("Nome Squadra")
        with c2:
            # Filtro: Solo Liberi (Non mostrare chi è già occupato)
            # Mostra prima i Capi grazie all'ordinamento del DF caricato
            opz_capo_create = {0: "Nessuno"}
            opz_capo_create.update({
                k: v for k, v in opzioni_dipendenti_display.items() 
                if k not in dipendenti_occupati_global
            })
            
            capo_id = st.selectbox("Caposquadra", options=opz_capo_create.keys(), format_func=lambda x: opz_capo_create[x], key="new_capo")
        
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
        s_id_edit = st.selectbox("Seleziona Squadra da Modificare", options=opzioni_squadre.keys(), format_func=lambda x: opzioni_squadre[x])
        
        if s_id_edit:
            s_obj = next(s for s in lista_squadre if s['id_squadra'] == s_id_edit)
            m_ids = squadra_members_map.get(s_id_edit, [])

            # Filtro Intelligente: Mostra (Liberi + Membri Attuali)
            occupati_altrove = dipendenti_occupati_global - set(m_ids)
            
            # Dizionario ordinato secondo la logica gerarchica (Capi prima)
            opz_filt = {
                k: v for k, v in opzioni_dipendenti_display.items() 
                if k not in occupati_altrove
            }
            
            opz_capo_filt = {0: "Nessuno"}; opz_capo_filt.update(opz_filt)

            with st.form(f"edit_{s_id_edit}"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.markdown("##### Dettagli")
                    new_name = st.text_input("Nome", value=s_obj['nome_squadra'])
                    
                    cur_capo = s_obj['id_caposquadra'] if s_obj['id_caposquadra'] else 0
                    if cur_capo != 0 and cur_capo not in opz_capo_filt:
                        opz_capo_filt[cur_capo] = opzioni_dipendenti_display.get(cur_capo, "Sconosciuto")
                    
                    new_capo_id = st.selectbox(
                        "Caposquadra (👑)", 
                        options=opz_capo_filt.keys(), 
                        format_func=lambda x: opz_capo_filt[x], 
                        index=list(opz_capo_filt.keys()).index(cur_capo) if cur_capo in opz_capo_filt else 0
                    )

                with c2:
                    st.markdown("##### Membri & Competenze")
                    def_mems = [m for m in m_ids if m in opz_filt]
                    
                    sel_mems = st.multiselect(
                        "Componi la squadra (Ordinati per Ruolo)",
                        options=opz_filt.keys(),
                        format_func=lambda x: opz_filt[x],
                        default=def_mems,
                        placeholder="Aggiungi operai..."
                    )
                
                st.caption("💡 L'elenco è ordinato per grado: Capi -> Specializzati -> Manovali.")
                
                if st.form_submit_button("💾 Salva Modifiche", type="primary"):
                    try:
                        cid_db = new_capo_id if new_capo_id != 0 else None
                        shift_service.update_squadra_details(s_id_edit, new_name, cid_db)
                        
                        final_mems = set(sel_mems)
                        if cid_db: final_mems.add(cid_db)
                        
                        shift_service.update_membri_squadra(s_id_edit, list(final_mems))
                        st.success("Aggiornato!"); st.cache_data.clear(); st.rerun()
                    except Exception as e: st.error(f"Errore: {e}")

            st.markdown("---")
            with st.expander("🚨 Zona Pericolo"):
                st.warning(f"Eliminare **{s_obj['nome_squadra']}**?")
                if st.button("Conferma Eliminazione", key=f"del_{s_id_edit}", type="secondary"):
                    shift_service.delete_squadra(s_id_edit)
                    st.success("Eliminata."); st.cache_data.clear(); st.rerun()