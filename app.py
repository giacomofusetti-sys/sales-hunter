import streamlit as st
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
from crewai import Crew
from agents import crea_prospector, crea_contact_hunter
from tasks import crea_task_ricerca, crea_task_contatti

load_dotenv()
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")

# Configurazione pagina
st.set_page_config(page_title="Sales Hunter", page_icon="🎯", layout="wide")

st.title("🎯 Sales Hunter")
st.subheader("Trova clienti per viteria speciale e tiranteria")

# Colonne per i filtri
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
        placeholder="Es: Lombardia, Toscana, Germania, Stoccolma, Sud America..."
    )

st.divider()

# Bottone di avvio
if st.button("🚀 Avvia ricerca", type="primary", use_container_width=True):

    # Validazione
    if not area:
        st.error("⚠️ Inserisci un'area geografica per continuare.")
        st.stop()

    # Usa valore custom se compilato
    settore_finale = settore_custom if settore_custom else settore

    st.info(f"🔍 Ricerca in corso: **{settore_finale}** in **{area}**")

    # Fase 1 - Ricerca aziende
    with st.spinner("🔍 L'agente sta cercando aziende..."):
        prospector = crea_prospector()
        task_ricerca = crea_task_ricerca(prospector, area, settore_finale)

        crew1 = Crew(
            agents=[prospector],
            tasks=[task_ricerca],
            verbose=False
        )
        risultato_ricerca = crew1.kickoff()

    st.success("✅ Aziende trovate!")
    st.markdown("### 🏭 Aziende identificate")
    st.markdown(str(risultato_ricerca))

    st.divider()

    # Fase 2 - Ricerca contatti
    with st.spinner("📋 L'agente sta cercando i contatti..."):
        contact_hunter = crea_contact_hunter()
        task_contatti = crea_task_contatti(contact_hunter, str(risultato_ricerca))

        crew2 = Crew(
            agents=[contact_hunter],
            tasks=[task_contatti],
            verbose=False
        )
        risultato_contatti = crew2.kickoff()

    st.success("✅ Contatti trovati!")
    st.markdown("### 📋 Contatti commerciali")
    st.markdown(str(risultato_contatti))

