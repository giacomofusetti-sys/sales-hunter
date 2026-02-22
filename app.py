import streamlit as st
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
from crewai import Crew
from agents import crea_prospector, crea_contact_hunter
from tasks import crea_task_ricerca, crea_task_contatti
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from database import salva_ricerca, carica_ricerche, aggiungi_cliente_esistente, carica_clienti_esistenti

load_dotenv()
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")

st.set_page_config(page_title="Sales Hunter", page_icon="🎯", layout="wide")

# Inizializzazione session state
if "risultato_ricerca" not in st.session_state:
    st.session_state.risultato_ricerca = None
if "risultato_contatti" not in st.session_state:
    st.session_state.risultato_contatti = None
if "ultima_ricerca_settore" not in st.session_state:
    st.session_state.ultima_ricerca_settore = None
if "ultima_ricerca_area" not in st.session_state:
    st.session_state.ultima_ricerca_area = None

# Menu laterale
with st.sidebar:
    st.title("⚙️ Impostazioni")
    pagina = st.radio("Navigazione", ["🔍 Nuova ricerca", "📁 Storico ricerche", "🚫 Clienti esistenti"])

# PAGINA 1 - NUOVA RICERCA
if pagina == "🔍 Nuova ricerca":
    st.title("🎯 Sales Hunter")
    st.subheader("Trova clienti per viteria speciale e tiranteria")

    col1, col2 = st.columns(2)

    with col1:
        settore = st.selectbox(
            "Settore merceologico",
            [
                "Carpenteria metallica",
                "Oil & Gas",
                "Cantieristica navale",
                "Energia e rinnovabili",
                "Impianti industriali",
                "Costruzioni e infrastrutture",
                "Industria chimica",
                "Macchine agricole",
                "Industria farmaceutica",
                "Altro (specifica sotto)"
            ]
        )
        settore_custom = st.text_input("Settore personalizzato (opzionale)")

    with col2:
        area = st.text_input(
            "Area geografica",
            placeholder="Es: Lombardia, Germania, Stoccolma, Sud America..."
        )

    col3, col4 = st.columns(2)
    with col3:
        num_aziende = st.slider("Numero di aziende da trovare", min_value=3, max_value=10, value=3)
    with col4:
        velocita = st.slider("Velocità vs qualità", min_value=5, max_value=15, value=8)

    st.divider()

    if st.button("🚀 Avvia ricerca", type="primary", use_container_width=True):

        if not area:
            st.error("⚠️ Inserisci un'area geografica per continuare.")
            st.stop()

        settore_finale = settore_custom if settore_custom else settore
        clienti_esistenti = carica_clienti_esistenti()

        st.info(f"🔍 Ricerca in corso: **{settore_finale}** in **{area}**")

        if clienti_esistenti:
            st.caption(f"⚠️ Verranno esclusi {len(clienti_esistenti)} clienti già esistenti")

        with st.spinner("🔍 L'agente sta cercando aziende..."):
            prospector = crea_prospector(max_iter=velocita)
            task_ricerca = crea_task_ricerca(prospector, area, settore_finale, num_aziende)
            crew1 = Crew(agents=[prospector], tasks=[task_ricerca], verbose=False)
            st.session_state.risultato_ricerca = str(crew1.kickoff())

        with st.spinner("📋 L'agente sta cercando i contatti..."):
            contact_hunter = crea_contact_hunter(max_iter=velocita)
            task_contatti = crea_task_contatti(contact_hunter, st.session_state.risultato_ricerca)
            crew2 = Crew(agents=[contact_hunter], tasks=[task_contatti], verbose=False)
            st.session_state.risultato_contatti = str(crew2.kickoff())

        st.session_state.ultima_ricerca_settore = settore_finale
        st.session_state.ultima_ricerca_area = area

        # Salva nel database
        id_ricerca = salva_ricerca(settore_finale, area, st.session_state.risultato_ricerca, st.session_state.risultato_contatti)
        st.caption(f"💾 Ricerca salvata nel database (ID: {id_ricerca})")

    # Mostra risultati dalla session state (persistono tra i cambi pagina)
    if st.session_state.risultato_ricerca:
        if st.session_state.ultima_ricerca_settore:
            st.info(f"Ultima ricerca: **{st.session_state.ultima_ricerca_settore}** in **{st.session_state.ultima_ricerca_area}**")
        st.success("✅ Aziende trovate!")
        st.markdown("### 🏭 Aziende identificate")
        st.markdown(st.session_state.risultato_ricerca)
        st.divider()
        st.success("✅ Contatti trovati!")
        st.markdown("### 📋 Contatti commerciali")
        st.markdown(st.session_state.risultato_contatti)

# PAGINA 2 - STORICO RICERCHE
elif pagina == "📁 Storico ricerche":
    st.title("📁 Storico ricerche")

    ricerche = carica_ricerche()

    if not ricerche:
        st.info("Nessuna ricerca ancora salvata.")
    else:
        for r in reversed(ricerche):
            with st.expander(f"🔍 #{r['id']} — {r['settore']} in {r['area']} — {r['data']}"):
                st.markdown("**🏭 Aziende trovate:**")
                st.markdown(r["aziende"])
                st.divider()
                st.markdown("**📋 Contatti:**")
                st.markdown(r["contatti"])

# PAGINA 3 - CLIENTI ESISTENTI
elif pagina == "🚫 Clienti esistenti":
    st.title("🚫 Clienti esistenti")
    st.caption("Inserisci i clienti già acquisiti per escluderli dalle ricerche future.")

    clienti = carica_clienti_esistenti()

    if clienti:
        st.markdown("**Clienti attualmente in lista:**")
        for c in clienti:
            st.write(f"• {c}")
    else:
        st.info("Nessun cliente inserito ancora.")

    st.divider()
    nuovo_cliente = st.text_input("Aggiungi cliente esistente")
    if st.button("➕ Aggiungi"):
        if nuovo_cliente:
            aggiungi_cliente_esistente(nuovo_cliente)
            st.success(f"✅ {nuovo_cliente} aggiunto!")
            st.rerun()
        else:
            st.error("⚠️ Inserisci il nome del cliente.")

