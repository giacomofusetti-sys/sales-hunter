import streamlit as st
import os
import sys
import time
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
from crewai import Crew
from agents import crea_prospector, crea_contact_hunter
from tasks import crea_task_ricerca, crea_task_contatti
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from database import salva_ricerca, carica_ricerche, aggiungi_cliente_esistente, carica_clienti_esistenti
from profilo_azienda import PROFILO_AZIENDA

load_dotenv()
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")

def kickoff_con_retry(crew, max_tentativi=3, attesa=30):
    for tentativo in range(1, max_tentativi + 1):
        try:
            return str(crew.kickoff())
        except Exception as e:
            msg = str(e)
            is_overloaded = "529" in msg or "500" in msg or "overloaded" in msg.lower()
            if is_overloaded and tentativo < max_tentativi:
                st.warning(f"Server Anthropic sovraccarico, riprovo tra 30 secondi... (tentativo {tentativo}/{max_tentativi})")
                time.sleep(attesa)
            else:
                raise

st.set_page_config(page_title="Sales Hunter", page_icon="🎯", layout="wide")

# ── Industrial Tech Theme ─────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Palette ───────────────────────────────────────── */
:root {
    --bg-main:    #0a0e1a;
    --bg-card:    #111827;
    --bg-hover:   #1a2234;
    --bg-sidebar: #0d1320;
    --accent:     #3b82f6;
    --accent-2:   #06b6d4;
    --accent-dim: #1d4ed8;
    --text-prim:  #f1f5f9;
    --text-sec:   #94a3b8;
    --border:     #1e3a5f;
    --success:    #10b981;
    --error:      #ef4444;
    --info:       #3b82f6;
    --font-mono:  'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
}

/* ── Global ────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"] {
    background-color: var(--bg-main) !important;
    color: var(--text-prim) !important;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

[data-testid="stHeader"] {
    background-color: var(--bg-main) !important;
    border-bottom: 1px solid var(--border);
}

/* ── Ambient glow background ───────────────────────── */
[data-testid="stAppViewContainer"]::before {
    content: '';
    position: fixed;
    inset: 0;
    background:
        radial-gradient(ellipse at 10% 90%, rgba(59,130,246,0.07) 0%, transparent 50%),
        radial-gradient(ellipse at 90% 10%, rgba(6,182,212,0.07) 0%, transparent 50%),
        radial-gradient(ellipse at 50% 50%, rgba(30,58,95,0.12) 0%, transparent 65%);
    pointer-events: none;
    z-index: 0;
}

/* ── Sidebar ───────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * {
    color: var(--text-prim) !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-family: var(--font-mono) !important;
    font-size: 0.9rem !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    color: var(--accent-2) !important;
}
[data-testid="stSidebar"] .stRadio label {
    padding: 8px 12px;
    border-radius: 4px;
    border-left: 2px solid transparent;
    transition: all .2s ease;
    font-family: var(--font-mono);
    font-size: 0.82rem;
    letter-spacing: 0.6px;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(59,130,246,0.08);
    border-left-color: var(--accent);
    padding-left: 16px;
}

/* ── Code blocks in sidebar (expander Profilo Azienda) ── */
[data-testid="stSidebar"] pre,
[data-testid="stSidebar"] code,
[data-testid="stSidebar"] .stCodeBlock,
[data-testid="stSidebar"] .stCodeBlock > div,
[data-testid="stSidebar"] .stCodeBlock pre,
[data-testid="stSidebar"] .highlight,
[data-testid="stSidebar"] .highlight pre,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] pre,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] code {
    background-color: var(--bg-main) !important;
    color: var(--text-prim) !important;
    border: 1px solid var(--border) !important;
}
/* forza tutti gli span di colorazione sintattica a testo leggibile */
[data-testid="stSidebar"] pre span,
[data-testid="stSidebar"] code span,
[data-testid="stSidebar"] .highlight span {
    color: var(--text-prim) !important;
    background: transparent !important;
}

/* ── Main content area ─────────────────────────────── */
[data-testid="stMainBlockContainer"],
.main .block-container {
    background-color: var(--bg-main) !important;
    padding-top: 2rem;
}

/* ── Typography — monospace headings ───────────────── */
h1, h2, h3 {
    font-family: var(--font-mono) !important;
    color: var(--text-prim) !important;
    font-weight: 700 !important;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}
h4, h5, h6 {
    color: var(--text-prim) !important;
    font-weight: 600 !important;
}
h1 {
    padding-left: 1rem;
    padding-bottom: 0.5rem;
    border-left: 3px solid var(--accent);
    border-bottom: 1px solid var(--border);
    background: linear-gradient(90deg, rgba(59,130,246,0.07), transparent 70%);
    position: relative;
}
h1::after {
    content: '';
    position: absolute;
    bottom: -1px; left: 0;
    width: 60px; height: 2px;
    background: var(--accent-2);
}
h2 {
    border-left: 2px solid var(--accent-2);
    padding-left: 0.7rem;
    color: var(--accent-2) !important;
}
h3 {
    color: var(--accent) !important;
    font-size: 0.95rem !important;
    letter-spacing: 1.5px;
}
p, li, span, label, div {
    color: var(--text-prim) !important;
}

/* ── Form labels — monospace uppercase ─────────────── */
.stSelectbox label,
.stTextInput label,
.stSlider label,
.stRadio label {
    font-family: var(--font-mono) !important;
    font-size: 0.75rem !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    color: var(--text-sec) !important;
}

/* ── Cards / expanders ─────────────────────────────── */
[data-testid="stExpander"],
[data-testid="stVerticalBlock"] > div[data-testid="element-container"] {
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 4px;
}
details > summary {
    background-color: var(--bg-card) !important;
    color: var(--accent) !important;
    border-radius: 6px;
    padding: 10px 14px !important;
    font-weight: 600;
    font-family: var(--font-mono);
    font-size: 0.82rem;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    border-left: 3px solid var(--accent) !important;
    transition: background .2s;
}
details > summary:hover {
    background-color: var(--bg-hover) !important;
}
details[open] > summary {
    border-bottom: 1px solid var(--border);
    border-radius: 6px 6px 0 0;
    color: var(--accent-2) !important;
    border-left-color: var(--accent-2) !important;
}
details > div {
    background-color: var(--bg-card) !important;
    border-radius: 0 0 6px 6px;
    padding: 12px 16px;
}

/* ── Buttons — bordered ghost style ────────────────── */
.stButton > button {
    background: transparent !important;
    color: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    border-radius: 4px !important;
    font-family: var(--font-mono) !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 1.2px !important;
    text-transform: uppercase !important;
    padding: 10px 22px !important;
    transition: all .25s ease !important;
    box-shadow: 0 0 8px rgba(59,130,246,0.15) !important;
}
.stButton > button:hover {
    background: rgba(59,130,246,0.12) !important;
    border-color: var(--accent-2) !important;
    color: var(--accent-2) !important;
    box-shadow: 0 0 22px rgba(59,130,246,0.4), inset 0 0 15px rgba(59,130,246,0.06) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"] {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    box-shadow: 0 0 14px rgba(59,130,246,0.25), inset 0 0 12px rgba(59,130,246,0.04) !important;
}
.stButton > button[kind="primary"]:hover {
    background: rgba(59,130,246,0.18) !important;
    box-shadow: 0 0 30px rgba(59,130,246,0.55), inset 0 0 20px rgba(59,130,246,0.08) !important;
    border-color: var(--accent-2) !important;
    color: #fff !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
    box-shadow: 0 0 8px rgba(59,130,246,0.2) !important;
}

/* ── Inputs / selects / sliders ────────────────────── */
.stTextInput input,
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    background-color: var(--bg-card) !important;
    color: var(--text-prim) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    font-family: var(--font-mono) !important;
    font-size: 0.88rem !important;
}
.stTextInput input:focus,
div[data-baseweb="input"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.18), 0 0 12px rgba(59,130,246,0.12) !important;
}
[data-baseweb="popover"] *,
[data-baseweb="menu"] * {
    background-color: var(--bg-card) !important;
    color: var(--text-prim) !important;
    font-family: var(--font-mono) !important;
}
[data-baseweb="option"]:hover {
    background-color: rgba(59,130,246,0.1) !important;
}
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background-color: var(--accent) !important;
    box-shadow: 0 0 8px rgba(59,130,246,0.6) !important;
}
.stSlider [data-baseweb="slider"] div[data-testid="stSlider-track"] {
    background: var(--accent) !important;
}

/* ── Alerts ─────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 4px !important;
    border-left-width: 3px !important;
    background-color: var(--bg-card) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.85rem !important;
}
div[data-baseweb="notification"][kind="info"],
.stInfo {
    background-color: rgba(59,130,246,0.08) !important;
    border-color: var(--info) !important;
}
div[data-baseweb="notification"][kind="positive"],
.stSuccess {
    background-color: rgba(16,185,129,0.08) !important;
    border-color: var(--success) !important;
}
div[data-baseweb="notification"][kind="negative"],
.stError {
    background-color: rgba(239,68,68,0.08) !important;
    border-color: var(--error) !important;
}

/* ── Spinner ───────────────────────────────────────── */
.stSpinner > div {
    border-top-color: var(--accent) !important;
}

/* ── Divider ───────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1.5rem 0 !important;
}

/* ── Caption / small text ──────────────────────────── */
.stCaption, small, [data-testid="stCaptionContainer"] {
    color: var(--text-sec) !important;
    font-size: .78rem !important;
    font-family: var(--font-mono) !important;
    letter-spacing: 0.5px;
}

/* ── Hexagonal decorative elements ─────────────────── */
.hex-bg {
    position: fixed;
    clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
    pointer-events: none;
    z-index: 0;
}
.hex-bg-1 {
    width: 340px; height: 340px;
    background: var(--accent);
    opacity: 0.035;
    top: -100px; right: 8%;
    animation: hex-drift 7s ease-in-out infinite;
}
.hex-bg-2 {
    width: 220px; height: 220px;
    background: var(--accent-2);
    opacity: 0.04;
    bottom: 12%; left: -55px;
    animation: hex-drift 9s ease-in-out infinite reverse;
}
.hex-bg-3 {
    width: 130px; height: 130px;
    background: var(--accent);
    opacity: 0.03;
    top: 42%; right: 3%;
    animation: hex-drift 11s ease-in-out infinite;
    animation-delay: 3s;
}
.hex-bg-4 {
    width: 80px; height: 80px;
    background: var(--accent-2);
    opacity: 0.05;
    top: 20%; left: 5%;
    animation: hex-drift 8s ease-in-out infinite reverse;
    animation-delay: 1.5s;
}
@keyframes hex-drift {
    0%, 100% { opacity: var(--o, 0.035); transform: translateY(0px) rotate(0deg); }
    50%       { opacity: calc(var(--o, 0.035) * 1.8); transform: translateY(-12px) rotate(3deg); }
}

/* ── Scrollbar ─────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg-main); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
</style>

<!-- Hexagonal decorative shapes -->
<div class="hex-bg hex-bg-1"></div>
<div class="hex-bg hex-bg-2"></div>
<div class="hex-bg hex-bg-3"></div>
<div class="hex-bg hex-bg-4"></div>
""", unsafe_allow_html=True)
# ─────────────────────────────────────────────────────────────────────────────

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

    st.divider()
    with st.expander("🏭 Profilo azienda", expanded=False):
        st.markdown(f"```\n{PROFILO_AZIENDA.strip()}\n```")

# PAGINA 1 - NUOVA RICERCA
if pagina == "🔍 Nuova ricerca":
    st.title("🎯 Sales Hunter")
    st.subheader("Trova clienti per viteria speciale e tiranteria")

    col1, col2 = st.columns(2)

    with col1:
        settore = st.selectbox(
            "Settore merceologico",
            [
                "Scambiatori di calore",
                "Valvole industriali",
                "Carpenteria metallica",
                "Oil & Gas",
                "Impianti industriali",
                "Cantieristica navale",
                "Energia e rinnovabili",
                "Costruzioni e infrastrutture",
                "Industria chimica",
                "Movimento terra",
                "Ferroviario",
                "Manutenzione industriale",
                "Macchine agricole",
                "Altro (specifica sotto)"
            ]
        )
        settore_custom = st.text_input("Settore personalizzato (opzionale)")

    with col2:
        area = st.text_input(
            "Area geografica",
            placeholder="Es: Lombardia, Germania, Stoccolma, Sud America..."
        )

    num_aziende = st.slider("Numero di aziende da trovare", min_value=3, max_value=10, value=3)

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

        max_iter = num_aziende * 4

        with st.spinner("🔍 L'agente sta cercando aziende..."):
            prospector = crea_prospector(max_iter=max_iter)
            task_ricerca = crea_task_ricerca(prospector, area, settore_finale, num_aziende)
            crew1 = Crew(agents=[prospector], tasks=[task_ricerca], verbose=False)
            st.session_state.risultato_ricerca = kickoff_con_retry(crew1)

        with st.spinner("📋 L'agente sta cercando i contatti..."):
            contact_hunter = crea_contact_hunter(max_iter=max_iter)
            task_contatti = crea_task_contatti(contact_hunter, str(st.session_state.risultato_ricerca))
            crew2 = Crew(agents=[contact_hunter], tasks=[task_contatti], verbose=False)
            st.session_state.risultato_contatti = kickoff_con_retry(crew2)

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

