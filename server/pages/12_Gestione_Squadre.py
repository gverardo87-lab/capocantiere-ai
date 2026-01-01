# file: server/pages/12_Gestione_Squadre.py (Versione 17.6 - Dark Mode Fix)
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

# --- CSS THEME-AWARE (COMPATIBILE DARK MODE) ---
st.markdown("""
<style>
    /* Stile Card Squadra - Adattivo */
    .squad-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 5px;
    }
    .squad-title {
        font-size: 1.3rem;
        font-weight: 700;
        margin: 0;
        /* Colore rimosso: eredita automaticamente dal tema (Bianco in Dark, Nero in Light) */
    }
    .squad-capo {
        font-size: 0.95rem;
        opacity: 0.85; /* Usiamo l'opacità invece del colore per gerarchia visiva */
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 5px;
    }
    
    /* Badge Skills - Neutri e Trasparenti */
    .skill-container {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 10px;
    }
    .skill-pill {
        /* Sfondo semi-trasparente: funziona sia su sfondo bianco che nero */
        background-color: rgba(128, 128, 128, 0.15); 
        color: inherit; /* Prende il colore del testo del tema corrente */
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 500;
        border: 1px solid rgba(128, 128, 128, 0.25);
    }
    
    /* Status Indicators (Semaforo) */
    .status-dot {
        height: 12px;
        width: 12px;
        border-radius: 50%;
        display: inline-block;
    }
    .dot-green { background-color: #10b981; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.3); }
    .dot-orange { background-color: #f59e0b; box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.3); }
    .dot-red { background-color: #ef4444; box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.3); }
    
    /* Rimossa forzatura sfondo su stExpander per compatibilità totale */
</style>
""", unsafe_allow_html=True)

st.title("👥 Gestione Squadre & Risorse")
st.caption("Organizzazione operativa e allocazione competenze.")

# --- HELPER: GERARCHIA E ICONE ---
def get_role_metadata(role_name: str) -> tuple[str, int]:
    if not isinstance(role_name, str): return "👷", 9
    r = role_name.lower()
    if 'capo' in r or 'preposto' in r or 'responsabile' in r: return "👑", 0
    if 'saldat' in r: return "👨‍🏭", 1
    if 'carpent' in r: return "🔨", 1
    if 'elettri' in r: return "⚡", 1
    if 'gruista' in r or 'movim' in r: return "🏗️", 2
    if 'autist' in r: return "🚛", 2
    if 'manoval' in r: return "🦺", 3
    return "👷", 9

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=30)
def load_data_hierarchical():
    dipendenti = shift_service.get_dipendenti_df(solo_attivi=True)
    squadre = shift_service.get_squadre()
    dipendenti['icona'], dipendenti['priority'] = zip(*dipendenti['ruolo'].apply(get_role_metadata))
    dipendenti = dipendenti.sort_values(by=['priority', 'cognome', 'nome'])
    return dipendenti, squadre

try:
    df_dipendenti, lista_squadre = load_data_hierarchical()
    opzioni_dipendenti_display = {}
    dip_role_map = {} 
    
    for index, row in df_dipendenti.iterrows():
        ruolo = row['ruolo'] if pd.notna(row['ruolo']) else "N/D"
        opzioni_dipendenti_display[index] = f"{row['cognome']} {row['nome']} | {row['icona']} {ruolo}"
        dip_role_map[index] = ruolo

    dipendenti_occupati_global = set()
    squadra_members_map = {} 
    
    for s in lista_squadre:
        mems = shift_service.get_membri_squadra(s['id_squadra'])
        squadra_members_map[s['id_squadra']] = mems
        dipendenti_occupati_global.update(mems)

    opzioni_squadre = {s['id_squadra']: s['nome_squadra'] for s in lista_squadre}

except Exception as e:
    st.error(f"Errore dati: {e}"); st.stop()

# --- 1. DASHBOARD VISUALE ---
st.subheader("Control Room Squadre")

if not lista_squadre:
    st.info("Nessuna squadra definita. Inizia dalla sezione sottostante.")
else:
    cols = st.columns(3)
    for idx, squadra in enumerate(lista_squadre):
        with cols[idx % 3]:
            s_id = squadra['id_squadra']
            s_nome = squadra['nome_squadra']
            s_capo_id = squadra['id_caposquadra']
            membri_ids = squadra_members_map.get(s_id, [])
            
            # -- LOGICA STATO --
            has_capo = s_capo_id is not None and s_capo_id > 0
            has_members = len(membri_ids) > 0
            
            if not has_capo:
                dot_class = "dot-red"
                status_text = "Manca Capo"
            elif not has_members:
                dot_class = "dot-orange"
                status_text = "Vuota"
            else:
                dot_class = "dot-green"
                status_text = "Operativa"

            # -- SKILL PILLS --
            ruoli = [dip_role_map.get(m, "") for m in membri_ids]
            badges_html = ""
            if ruoli:
                counts = Counter([r for r in ruoli if r])
                badges_html = "".join([f"<span class='skill-pill'>{get_role_metadata(r)[0]} {c} {r}</span>" for r, c in counts.items()])
            else:
                badges_html = "<span style='opacity: 0.5; font-size:0.8rem; font-style:italic;'>Nessuna risorsa</span>"

            # -- CAPO DISPLAY --
            capo_display = "⚠️ Non assegnato"
            if has_capo and s_capo_id in df_dipendenti.index:
                c_row = df_dipendenti.loc[s_capo_id]
                capo_display = f"{c_row['cognome']} {c_row['nome']}"

            # -- RENDER CARD --
            with st.container(border=True):
                # Header HTML Personalizzato
                st.markdown(f"""
                <div class="squad-card-header">
                    <span class="squad-title">{s_nome}</span>
                    <span class="status-dot {dot_class}" title="{status_text}"></span>
                </div>
                <div class="squad-capo">👑 <b>{capo_display}</b></div>
                <div class="skill-container">{badges_html}</div>
                """, unsafe_allow_html=True)

                # Expander pulito per i dettagli
                with st.expander("Vedi dettagli"):
                    for m in membri_ids:
                        dn = opzioni_dipendenti_display.get(m, f"ID {m}")
                        if m == s_capo_id: st.markdown(f"**{dn}**")
                        else: st.markdown(f"• {dn}")

st.divider()

# --- 2. GESTIONE OPERATIVA ---
tab1, tab2 = st.tabs(["➕ Crea Nuova Squadra", "✏️ Modifica Squadra"])

with tab1:
    st.subheader("Crea Nuova Squadra")
    with st.form("new_squadra_form", clear_on_submit=True):
        c1, c2 = st.columns([3, 2])
        with c1: 
            nome_nuova = st.text_input("Nome Squadra", placeholder="Es. Squadra Posa 1")
        with c2:
            opz_capo_create = {0: "Nessuno"}
            opz_capo_create.update({k: v for k, v in opzioni_dipendenti_display.items() if k not in dipendenti_occupati_global})
            capo_id = st.selectbox("Caposquadra", options=opz_capo_create.keys(), format_func=lambda x: opz_capo_create[x], key="new_capo")
        
        if st.form_submit_button("Crea Squadra", type="primary", use_container_width=True):
            if not nome_nuova: st.warning("Inserisci il nome.")
            else:
                try:
                    shift_service.add_squadra(nome_nuova, capo_id if capo_id != 0 else None)
                    st.success("Creata!"); st.cache_data.clear(); st.rerun()
                except Exception as e: st.error(f"Errore: {e}")

with tab2:
    st.subheader("Modifica Squadra")
    if not opzioni_squadre:
        st.info("Nessuna squadra disponibile.")
    else:
        s_id_edit = st.selectbox("Seleziona Squadra", options=opzioni_squadre.keys(), format_func=lambda x: opzioni_squadre[x])
        
        if s_id_edit:
            s_obj = next(s for s in lista_squadre if s['id_squadra'] == s_id_edit)
            m_ids = squadra_members_map.get(s_id_edit, [])

            # Filtri
            occ_altrove = dipendenti_occupati_global - set(m_ids)
            opz_filt = {k: v for k, v in opzioni_dipendenti_display.items() if k not in occ_altrove}
            opz_capo_filt = {0: "Nessuno"}; opz_capo_filt.update(opz_filt)

            with st.form(f"edit_{s_id_edit}"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.markdown("##### 📝 Dettagli")
                    new_name = st.text_input("Nome", value=s_obj['nome_squadra'])
                    
                    cur_capo = s_obj['id_caposquadra'] or 0
                    if cur_capo != 0 and cur_capo not in opz_capo_filt:
                        opz_capo_filt[cur_capo] = opzioni_dipendenti_display.get(cur_capo, "Sconosciuto")
                    
                    new_capo_id = st.selectbox("Caposquadra", options=opz_capo_filt.keys(), format_func=lambda x: opz_capo_filt[x], index=list(opz_capo_filt.keys()).index(cur_capo) if cur_capo in opz_capo_filt else 0)

                with c2:
                    st.markdown("##### 👷 Membri")
                    def_mems = [m for m in m_ids if m in opz_filt]
                    sel_mems = st.multiselect("Componi squadra", options=opz_filt.keys(), format_func=lambda x: opz_filt[x], default=def_mems, placeholder="Cerca operaio...")
                
                if st.form_submit_button("Salva Modifiche", type="primary", use_container_width=True):
                    try:
                        cid_db = new_capo_id if new_capo_id != 0 else None
                        shift_service.update_squadra_details(s_id_edit, new_name, cid_db)
                        fm = set(sel_mems); 
                        if cid_db: fm.add(cid_db)
                        shift_service.update_membri_squadra(s_id_edit, list(fm))
                        st.success("Salvato!"); st.cache_data.clear(); st.rerun()
                    except Exception as e: st.error(str(e))

            st.markdown("---")
            with st.expander("🚨 Zona Pericolo"):
                st.write(f"Eliminazione squadra **{s_obj['nome_squadra']}**")
                if st.button("Conferma Eliminazione", key=f"del_{s_id_edit}", type="secondary"):
                    shift_service.delete_squadra(s_id_edit)
                    st.success("Cancellata."); st.cache_data.clear(); st.rerun()