import concurrent.futures
import os
import re
import sys
import time

# load_dotenv PRIMA di qualsiasi import che usa os.getenv a livello di modulo
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("SERPER_API_KEY", os.getenv("SERPER_API_KEY") or "")

import streamlit as st
from crewai import Crew
from agents import crea_prospector, crea_contact_hunter, crea_email_sender
from tasks import (
    crea_task_ricerca,
    crea_task_contatti_lead,
    crea_task_email,
)
from analyst import crea_analyst, crea_task_analisi, parse_leads_json
from database import (
    salva_leads, carica_leads, aggiorna_stato_lead,
    aggiungi_cliente_esistente, carica_clienti_esistenti,
    aggiorna_leads_campagna,
)
from profilo_azienda import PROFILO_AZIENDA


def kickoff_con_retry(crew, max_tentativi=3, attesa=30):
    for tentativo in range(1, max_tentativi + 1):
        try:
            return str(crew.kickoff())
        except ValueError as e:
            msg = str(e)
            if "Invalid response from LLM call" in msg or "None or empty" in msg:
                return (
                    "Ricerca incompleta: l'agente ha esaurito il numero massimo di operazioni. "
                    "Riprovare o aumentare il numero di aziende cercate."
                )
            raise
        except Exception as e:
            msg = str(e)
            is_overloaded = "529" in msg or "500" in msg or "overloaded" in msg.lower()
            if is_overloaded and tentativo < max_tentativi:
                st.warning(f"Server Anthropic sovraccarico, riprovo tra 30 secondi... (tentativo {tentativo}/{max_tentativi})")
                time.sleep(attesa)
            else:
                raise


def _parse_contatti_per_lead(testo_contatti, leads):
    """Parsa l'output del Contact Hunter e restituisce {lead_id: [contatto_dict]}."""
    if not testo_contatti:
        return {l.get("id"): [] for l in leads}

    risultato = {}
    lines = testo_contatti.split('\n')
    role_keywords = [
        'responsabile', 'manager', 'direttore', 'director', 'head',
        'chief', 'procurement', 'acquisti', 'tecnico', 'operations',
        'purchasing', 'supply chain', 'ceo', 'cto', 'coo', 'vp', 'vice',
    ]

    for lead in leads:
        lead_id = lead.get("id")
        nome_lead = lead.get("nome", "")
        if not nome_lead:
            risultato[lead_id] = []
            continue

        # Find the line in the text that first mentions this company
        section_start = None
        for i, line in enumerate(lines):
            if nome_lead.lower() in line.lower():
                section_start = i
                break

        if section_start is None:
            # Fallback: match on the longest word (>3 chars) of the company name
            parole = [w for w in nome_lead.split() if len(w) > 3]
            for parola in parole:
                for i, line in enumerate(lines):
                    if parola.lower() in line.lower():
                        section_start = i
                        break
                if section_start is not None:
                    break

        if section_start is None:
            risultato[lead_id] = []
            continue

        # Find section end: next company mention or at most 15 lines
        section_end = min(section_start + 15, len(lines))
        other_leads = [l for l in leads if l.get("id") != lead_id and l.get("nome")]
        for j in range(section_start + 2, section_end):
            for other in other_leads:
                if other["nome"].lower() in lines[j].lower():
                    section_end = j
                    break
            else:
                continue
            break

        section_text = '\n'.join(lines[section_start:section_end])

        contatto = {"nome_contatto": "", "ruolo": "", "email": "", "telefono": ""}

        # Email
        emails_found = re.findall(r'\b[\w.+\-]+@[\w.\-]+\.\w+\b', section_text)
        if emails_found:
            contatto["email"] = emails_found[0]

        # Phone (sequence of 7+ digits, possibly with spaces/dashes)
        for phone_match in re.finditer(r'(?:\+?[\d][\d\s\-\.\(\)]{6,})', section_text):
            cleaned = re.sub(r'[\s\-\.\(\)]', '', phone_match.group())
            if len(cleaned) >= 7 and cleaned.lstrip('+').isdigit():
                contatto["telefono"] = phone_match.group().strip()
                break

        # Name and role from individual lines
        for line in lines[section_start:section_end]:
            stripped = line.strip(' -•:*\t')
            if not stripped or '@' in stripped:
                continue
            if re.search(r'\d{5,}', stripped):
                continue
            lower = stripped.lower()
            if any(kw in lower for kw in role_keywords):
                if not contatto["ruolo"]:
                    contatto["ruolo"] = stripped
            elif (
                not contatto["nome_contatto"]
                and 2 <= len(stripped.split()) <= 4
                and stripped[0].isupper()
                and nome_lead.lower() not in lower
                and not any(kw in lower for kw in ['sito', 'http', 'www', 'email', 'tel', 'fax', 'phone'])
            ):
                contatto["nome_contatto"] = stripped

        if any(v for v in contatto.values()):
            risultato[lead_id] = [contatto]
        else:
            risultato[lead_id] = []

    # Fallback: per ogni lead senza email valida, genera contatto generico aziendale
    for lead in leads:
        lid = lead.get("id")
        entry = risultato.get(lid)
        has_email = entry and entry[0].get("email")
        if not has_email:
            risultato[lid] = [_fallback_contatto_generico(lead)]

    return risultato


def _fallback_contatto_generico(lead):
    """Genera un contatto generico di fallback dal sito aziendale del lead."""
    sito = lead.get("sito", "")
    email_gen = ""
    if sito:
        domain = re.sub(r'^https?://(www\.)?', '', sito.strip().rstrip('/'))
        domain = domain.split('/')[0].split('?')[0]
        if domain and '.' in domain:
            email_gen = f"info@{domain}"
    msg = (
        f"Contatto diretto non trovato - utilizzare email generica: {email_gen}"
        if email_gen
        else "Contatto diretto non trovato - verificare sito aziendale"
    )
    return {"nome_contatto": msg, "ruolo": "", "email": email_gen, "telefono": ""}


def _parse_email_per_lead(testo_email, leads):
    """Parsa l'output dell'Email Sender e restituisce {lead_id: email_string}."""
    if not testo_email:
        return {}

    risultato = {}

    # Try multiple separator patterns in order of preference
    sep_patterns = [
        r'(?:^|\n)={3,}\s*(?:\n|$)',   # ===
        r'(?:^|\n)-{3,}\s*(?:\n|$)',   # ---
        r'(?:^|\n)#{3,}\s*(?:\n|$)',   # ###
    ]
    blocks = []
    for sep in sep_patterns:
        parts = [b.strip() for b in re.split(sep, testo_email) if b.strip() and len(b.strip()) > 50]
        if len(parts) >= 1:
            blocks = parts
            break

    # If no separator found, treat entire text as one block (single-lead case)
    if not blocks:
        blocks = [testo_email.strip()] if len(testo_email.strip()) > 50 else []

    def _match_lead(nome_nel_blocco, leads_list, already_matched):
        """Returns (lead_id, lead) for the first matching unmatched lead, or None."""
        for lead in leads_list:
            lid = lead.get("id")
            if lid in already_matched:
                continue
            nome_lead = lead.get("nome", "")
            if not nome_lead:
                continue
            nl = nome_lead.lower()
            nb = nome_nel_blocco.lower()
            if nl in nb or nb in nl:
                return lid
            parole = [w for w in nome_lead.split() if len(w) > 3]
            if any(p.lower() in nb for p in parole):
                return lid
        return None

    # First pass: match blocks that have an AZIENDA: header
    unmatched_blocks = []
    for block in blocks:
        # Support AZIENDA:, **AZIENDA:**, ## AZIENDA: etc.
        match = re.search(r'(?:\*{0,2}#{0,3}\s*)AZIENDA:\*{0,2}\s*(.+)', block, re.IGNORECASE)
        if not match:
            unmatched_blocks.append(block)
            continue
        nome_nel_blocco = match.group(1).strip().strip('*#').strip()
        lid = _match_lead(nome_nel_blocco, leads, risultato)
        if lid is not None:
            risultato[lid] = block

    # Second pass: for any remaining unmatched block, try matching by lead name anywhere in the block
    unmatched_leads = [l for l in leads if l.get("id") not in risultato]
    for block in unmatched_blocks:
        if not unmatched_leads:
            break
        for lead in unmatched_leads:
            nome_lead = lead.get("nome", "")
            if not nome_lead:
                continue
            parole = [w for w in nome_lead.split() if len(w) > 3]
            if nome_lead.lower() in block.lower() or any(p.lower() in block.lower() for p in parole):
                risultato[lead.get("id")] = block
                unmatched_leads = [l for l in unmatched_leads if l.get("id") != lead.get("id")]
                break

    # Last resort: single lead, single block
    if not risultato and len(leads) == 1 and len(blocks) == 1:
        risultato[leads[0].get("id")] = blocks[0]

    return risultato


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

# ── Funzione helper per mostrare lead ─────────────────────────────────────────
def _mostra_leads(leads, allow_stato_change=True):
    STATI = ["da_contattare", "email_pronta", "contattato", "non_interessante"]
    STATO_ICON = {"da_contattare": "📬", "email_pronta": "✉️", "contattato": "✅", "non_interessante": "❌"}

    for lead in leads:
        score = lead.get("score", 0)
        badge = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
        stato = lead.get("stato", "da_contattare")
        icona_stato = STATO_ICON.get(stato, "📬")
        lead_id = lead.get("id", 0)

        label = (
            f"{badge} {lead.get('nome', 'N/D')} — {lead.get('citta', '')} "
            f"| Score: {score}/10 | {icona_stato} {stato}"
        )

        with st.expander(label, expanded=False):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**Settore:** {lead.get('settore', 'N/D')}")
                st.markdown(f"**Sito:** {lead.get('sito', 'N/D')}")
                st.markdown(f"**Descrizione:** {lead.get('descrizione', 'N/D')}")
                if lead.get("notizie_recenti") and lead["notizie_recenti"] != "Nessuna notizia recente trovata":
                    st.markdown(f"**Notizie recenti:** {lead['notizie_recenti']}")
                if lead.get("motivazione_score"):
                    st.caption(f"Score motivazione: {lead['motivazione_score']}")
                if lead.get("data_ricerca"):
                    st.caption(f"Ricerca: {lead['data_ricerca']} | Area: {lead.get('area_ricerca', 'N/D')}")

            with col2:
                if allow_stato_change:
                    try:
                        idx = STATI.index(stato)
                    except ValueError:
                        idx = 0
                    nuovo_stato = st.selectbox(
                        "Stato",
                        STATI,
                        index=idx,
                        key=f"stato_{lead_id}"
                    )
                    if nuovo_stato != stato:
                        aggiorna_stato_lead(lead_id, nuovo_stato)
                        st.rerun()
                else:
                    st.markdown(f"**{icona_stato} {stato}**")


# ── Session state ─────────────────────────────────────────────────────────────
PAGINE = ["🔍 Nuova ricerca", "📊 Lead salvati", "📧 Email pronte", "🚫 Clienti esistenti"]

for key, default in [
    ("risultato_ricerca", None),
    ("leads_trovati", []),
    ("ultima_ricerca_settore", None),
    ("ultima_ricerca_area", None),
    ("campagna_attiva", False),
    ("ultima_pagina_radio", PAGINE[0]),
    ("risultato_contatti_campagna", None),
    ("risultato_email_campagna", None),
    ("leads_per_campagna", []),
    ("debug_email_campagna", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Impostazioni")

    pagina_nav = st.radio("Navigazione", PAGINE)

    # Se l'utente cambia pagina via radio, disattiva la campagna
    if pagina_nav != st.session_state.ultima_pagina_radio:
        st.session_state.campagna_attiva = False
        st.session_state.ultima_pagina_radio = pagina_nav

    st.divider()

    with st.expander("🏭 Profilo azienda", expanded=False):
        st.markdown(f"```\n{PROFILO_AZIENDA.strip()}\n```")

    st.divider()

    # ── Bottone Fase 2 ────────────────────────────────────────────────────────
    _tutti = carica_leads()
    leads_pending = [l for l in _tutti if l.get("stato") == "da_contattare"]
    n_pending = len(leads_pending)
    n_email_pronte = sum(1 for l in _tutti if l.get("stato") == "email_pronta")

    if n_email_pronte > 0:
        st.caption(f"✉️ {n_email_pronte} email pronte da inviare")
    if n_pending > 0:
        st.caption(f"📬 {n_pending} lead pronti per la campagna")
        if st.button("📧 Avvia campagna email", use_container_width=True, type="primary"):
            st.session_state.leads_per_campagna = leads_pending
            st.session_state.campagna_attiva = True
            st.rerun()
    else:
        if n_email_pronte == 0:
            st.caption("Nessun lead da contattare")
        st.button("📧 Avvia campagna email", use_container_width=True, disabled=True)

# ── Routing ───────────────────────────────────────────────────────────────────
if st.session_state.campagna_attiva:
    pagina = "campagna_email"
else:
    pagina = pagina_nav


# ══════════════════════════════════════════════════════════════════════════════
# FASE 1 — NUOVA RICERCA
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "🔍 Nuova ricerca":
    st.title("🎯 Sales Hunter")
    st.subheader("Fase 1 — Trova e valuta i prospect")

    col1, col2 = st.columns(2)

    with col1:
        settore = st.selectbox(
            "Settore merceologico",
            [
                "Valvole industriali",
                "Oil & Gas",
                "Energia e rinnovabili",
                "Scambiatori di calore",
                "Compressori industriali",
                "Idrogeno e CCUS",
                "EPC Contractor / Engineering",
                "Impianti industriali",
                "Trattamento emissioni (Aria/Acqua)",
                "Caldareria e serbatoi",
                "Cantieristica navale",
                "Industria chimica",
                "Carpenteria metallica",
                "Costruzioni e infrastrutture",
                "Sollevamento e mezzi pesanti",
                "Data Center e infrastrutture IA",
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
            placeholder="Es: Lombardia, Germania, Arabia Saudita, UAE, GCC, Stoccolma..."
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

        max_iter = num_aziende * 6

        # Step 1 — Prospector
        with st.spinner("🔍 Prospector: ricerca aziende in corso..."):
            prospector = crea_prospector(max_iter=max_iter)
            task_ricerca = crea_task_ricerca(prospector, area, settore_finale, num_aziende)
            crew1 = Crew(agents=[prospector], tasks=[task_ricerca], verbose=False)
            st.session_state.risultato_ricerca = kickoff_con_retry(crew1)

        # Step 2 — Analyst
        with st.spinner("📊 Analyst: valutazione score e notizie recenti..."):
            analyst = crea_analyst(max_iter=max_iter)
            task_analisi = crea_task_analisi(
                analyst,
                str(st.session_state.risultato_ricerca),
                settore_finale,
                area
            )
            crew2 = Crew(agents=[analyst], tasks=[task_analisi], verbose=False)
            output_analisi = kickoff_con_retry(crew2)

        # Parse JSON e salva lead strutturati
        leads_parsati = parse_leads_json(output_analisi)

        if leads_parsati:
            n_salvati = salva_leads(leads_parsati, settore_finale, area)
            st.session_state.leads_trovati = leads_parsati
            st.session_state.ultima_ricerca_settore = settore_finale
            st.session_state.ultima_ricerca_area = area
            st.success(f"✅ {n_salvati} lead salvati con score in leads.json")
        else:
            st.warning("⚠️ Impossibile parsare i lead come JSON. Output grezzo mostrato sotto.")
            st.session_state.leads_trovati = []
            st.text_area("Output Analyst (grezzo)", output_analisi, height=300)

    # Mostra i lead trovati nell'ultima ricerca
    if st.session_state.leads_trovati:
        if st.session_state.ultima_ricerca_settore:
            st.info(
                f"Ultima ricerca: **{st.session_state.ultima_ricerca_settore}** "
                f"in **{st.session_state.ultima_ricerca_area}**"
            )
        st.markdown("### 📊 Lead trovati e valutati")
        _mostra_leads(st.session_state.leads_trovati, allow_stato_change=False)
        st.caption("Vai a **Lead salvati** per gestire gli stati e avviare la campagna email.")


# ══════════════════════════════════════════════════════════════════════════════
# LEAD SALVATI
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📊 Lead salvati":
    st.title("📊 Lead salvati")

    tutti_leads = carica_leads()

    if not tutti_leads:
        st.info("Nessun lead ancora. Avvia una ricerca dalla pagina **Nuova ricerca**.")
    else:
        STATI_LS = ["da_contattare", "email_pronta", "contattato", "non_interessante"]
        STATO_ICON_LS = {"da_contattare": "📬", "email_pronta": "✉️", "contattato": "✅", "non_interessante": "❌"}

        # ── Valori unici per dropdown filtri ──────────────────────────────────
        settori_unici = sorted(set(l.get("settore", "") for l in tutti_leads if l.get("settore")))
        aree_uniche = sorted(set(l.get("area_ricerca", "") for l in tutti_leads if l.get("area_ricerca")))

        # ── Riga 1: filtri testuali ───────────────────────────────────────────
        col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1.3, 1.3, 1.2])
        with col_f1:
            filtro_stato = st.selectbox("Stato", ["Tutti"] + STATI_LS)
        with col_f2:
            filtro_settore = st.selectbox("Settore", ["Tutti"] + settori_unici)
        with col_f3:
            filtro_area = st.selectbox("Paese / Area", ["Tutte"] + aree_uniche)
        with col_f4:
            ordina = st.selectbox("Ordina per", ["Score ↓", "Nome ↑", "Data ↓", "Paese ↑"])

        # ── Riga 2: slider score + contatori ─────────────────────────────────
        col_sl, col_cnt = st.columns([3, 2])
        with col_sl:
            score_min = st.slider("Score minimo", min_value=1, max_value=10, value=1)
        with col_cnt:
            st.caption(
                f"📬 {sum(1 for l in tutti_leads if l.get('stato') == 'da_contattare')} da_contattare  "
                f"| ✉️ {sum(1 for l in tutti_leads if l.get('stato') == 'email_pronta')} email_pronta  "
                f"| ✅ {sum(1 for l in tutti_leads if l.get('stato') == 'contattato')} contattato  "
                f"| ❌ {sum(1 for l in tutti_leads if l.get('stato') == 'non_interessante')} non_interessante"
            )

        # ── Applica filtri ────────────────────────────────────────────────────
        leads_filtrati = tutti_leads
        if filtro_stato != "Tutti":
            leads_filtrati = [l for l in leads_filtrati if l.get("stato") == filtro_stato]
        if filtro_settore != "Tutti":
            leads_filtrati = [l for l in leads_filtrati if l.get("settore") == filtro_settore]
        if filtro_area != "Tutte":
            leads_filtrati = [l for l in leads_filtrati if l.get("area_ricerca") == filtro_area]
        leads_filtrati = [l for l in leads_filtrati if l.get("score", 0) >= score_min]

        # ── Applica ordinamento ───────────────────────────────────────────────
        if ordina == "Score ↓":
            leads_filtrati = sorted(leads_filtrati, key=lambda l: l.get("score", 0), reverse=True)
        elif ordina == "Nome ↑":
            leads_filtrati = sorted(leads_filtrati, key=lambda l: l.get("nome", "").lower())
        elif ordina == "Data ↓":
            leads_filtrati = sorted(leads_filtrati, key=lambda l: l.get("data_ricerca", ""), reverse=True)
        elif ordina == "Paese ↑":
            leads_filtrati = sorted(leads_filtrati, key=lambda l: l.get("area_ricerca", "").lower())

        st.divider()

        # ── Barra azioni: conteggio + seleziona/deseleziona ───────────────────
        col_cnt2, col_sa, col_da = st.columns([3, 1.2, 1])
        with col_cnt2:
            st.markdown(f"**{len(leads_filtrati)}** lead trovati")
        with col_sa:
            if st.button("☑ Seleziona tutti i filtrati", use_container_width=True):
                for l in tutti_leads:
                    st.session_state[f"sel_{l.get('id', 0)}"] = False
                for l in leads_filtrati:
                    st.session_state[f"sel_{l.get('id', 0)}"] = True
                st.rerun()
        with col_da:
            if st.button("☐ Deseleziona tutti", use_container_width=True):
                for l in tutti_leads:
                    st.session_state[f"sel_{l.get('id', 0)}"] = False
                st.rerun()

        st.divider()

        # ── Lista lead con checkbox ───────────────────────────────────────────
        for lead in leads_filtrati:
            score = lead.get("score", 0)
            badge = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
            stato = lead.get("stato", "da_contattare")
            icona_stato = STATO_ICON_LS.get(stato, "📬")
            lead_id = lead.get("id", 0)
            default_checked = (stato == "da_contattare")

            col_cb, col_main = st.columns([0.04, 0.96])
            with col_cb:
                st.checkbox(
                    label="seleziona",
                    value=default_checked,
                    key=f"sel_{lead_id}",
                    label_visibility="collapsed"
                )
            with col_main:
                label = (
                    f"{badge} {lead.get('nome', 'N/D')} — {lead.get('citta', '')} "
                    f"| Score: {score}/10 | {icona_stato} {stato}"
                )
                with st.expander(label, expanded=False):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**Settore:** {lead.get('settore', 'N/D')}")
                        st.markdown(f"**Sito:** {lead.get('sito', 'N/D')}")
                        st.markdown(f"**Descrizione:** {lead.get('descrizione', 'N/D')}")
                        if lead.get("notizie_recenti") and lead["notizie_recenti"] != "Nessuna notizia recente trovata":
                            st.markdown(f"**Notizie recenti:** {lead['notizie_recenti']}")
                        if lead.get("motivazione_score"):
                            st.caption(f"Score motivazione: {lead['motivazione_score']}")
                        if lead.get("data_ricerca"):
                            st.caption(f"Ricerca: {lead['data_ricerca']} | Area: {lead.get('area_ricerca', 'N/D')}")
                    with col2:
                        try:
                            idx = STATI_LS.index(stato)
                        except ValueError:
                            idx = 0
                        nuovo_stato = st.selectbox(
                            "Stato",
                            STATI_LS,
                            index=idx,
                            key=f"stato_{lead_id}"
                        )
                        if nuovo_stato != stato:
                            aggiorna_stato_lead(lead_id, nuovo_stato)
                            st.rerun()

        st.divider()

        # ── Bottone campagna ──────────────────────────────────────────────────
        leads_selezionati = [
            l for l in tutti_leads
            if st.session_state.get(f"sel_{l.get('id', 0)}", l.get("stato") == "da_contattare")
        ]
        n_sel = len(leads_selezionati)

        if n_sel > 0:
            if st.button(
                f"📧 Avvia campagna email per {n_sel} selezionati",
                type="primary",
                use_container_width=True
            ):
                st.session_state.leads_per_campagna = leads_selezionati
                st.session_state.campagna_attiva = True
                st.rerun()
        else:
            st.button(
                "📧 Avvia campagna email per i selezionati",
                disabled=True,
                use_container_width=True
            )


# ══════════════════════════════════════════════════════════════════════════════
# FASE 2 — CAMPAGNA EMAIL
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "campagna_email":
    st.title("📧 Campagna Email")
    st.subheader("Fase 2 — Contact Hunter + Email Sender")

    leads_per_campagna = st.session_state.get("leads_per_campagna") or []
    leads_da_contattare = leads_per_campagna if leads_per_campagna else [
        l for l in carica_leads() if l.get("stato") == "da_contattare"
    ]

    if not leads_da_contattare:
        st.info("Nessun lead con stato **da_contattare**. Modifica gli stati dalla pagina Lead salvati.")
        if st.button("← Torna ai lead"):
            st.session_state.campagna_attiva = False
            st.rerun()
        st.stop()

    st.markdown(f"**{len(leads_da_contattare)} lead** pronti per la campagna:")
    for l in leads_da_contattare:
        score = l.get("score", 0)
        badge = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
        st.caption(f"{badge} {l.get('nome', 'N/D')} — {l.get('citta', '')} | Score {score}/10")

    st.divider()

    max_iter_c = len(leads_da_contattare) * 6

    # Step 1 — Contact Hunter
    if not st.session_state.risultato_contatti_campagna:
        if st.button("🔎 Trova contatti", type="primary", use_container_width=True):
            with st.spinner("🔎 Contact Hunter: ricerca contatti in corso..."):
                contact_hunter = crea_contact_hunter(max_iter=max_iter_c)
                task_contatti = crea_task_contatti_lead(contact_hunter, leads_da_contattare)
                crew_c = Crew(agents=[contact_hunter], tasks=[task_contatti], verbose=False)
                timeout_sec = max(300, len(leads_da_contattare) * 90)
                risultato_raw = ""
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(kickoff_con_retry, crew_c)
                        risultato_raw = future.result(timeout=timeout_sec)
                except concurrent.futures.TimeoutError:
                    st.warning(
                        f"⏱ Timeout ({timeout_sec}s): il Contact Hunter non ha completato in tempo. "
                        "Sono stati applicati contatti generici di fallback per i lead non trovati."
                    )
                except Exception as e:
                    st.warning(
                        f"⚠️ Errore durante la ricerca contatti: {str(e)[:200]}. "
                        "Sono stati applicati contatti generici di fallback."
                    )
                st.session_state.risultato_contatti_campagna = (
                    risultato_raw or "Ricerca contatti non completata - contatti generici applicati."
                )
            # Salva subito i contatti in leads.json (persistenza immediata)
            contatti_per_lead = _parse_contatti_per_lead(
                str(st.session_state.risultato_contatti_campagna), leads_da_contattare
            )
            aggiorna_leads_campagna({
                l["id"]: {"contatti_trovati": contatti_per_lead.get(l["id"], [])}
                for l in leads_da_contattare
            })
            st.rerun()
    else:
        st.success("✅ Contatti trovati")
        with st.expander("📋 Risultati Contact Hunter", expanded=False):
            st.markdown(st.session_state.risultato_contatti_campagna)

        # Step 2 — Email Sender
        if not st.session_state.risultato_email_campagna:
            if st.button("✉️ Genera email personalizzate", type="primary", use_container_width=True):
                # Debug: snapshot of what will be passed to the email composer
                leads_info_debug = "\n".join([
                    f"• {l.get('nome','?')} | score={l.get('score','?')} | "
                    f"desc={'✓' if l.get('descrizione') else '✗ MANCANTE'} | "
                    f"notizie={'✓' if l.get('notizie_recenti') else '✗ MANCANTI'} | "
                    f"sito={l.get('sito','?')}"
                    for l in leads_da_contattare
                ])
                contatti_debug = str(st.session_state.risultato_contatti_campagna)

                with st.spinner("✉️ Email Sender: redazione email in corso..."):
                    email_sender = crea_email_sender(max_iter=6)
                    task_email = crea_task_email(
                        email_sender,
                        leads_da_contattare,
                        contatti_debug
                    )
                    crew_e = Crew(agents=[email_sender], tasks=[task_email], verbose=False)
                    st.session_state.risultato_email_campagna = kickoff_con_retry(crew_e)

                # Parse and save emails
                email_per_lead = _parse_email_per_lead(
                    str(st.session_state.risultato_email_campagna), leads_da_contattare
                )

                # Store debug info in session state (visible after rerun)
                st.session_state.debug_email_campagna = {
                    "leads_debug": leads_info_debug,
                    "contatti_preview": contatti_debug[:600],
                    "output_raw": str(st.session_state.risultato_email_campagna)[:3000],
                    "parsed_count": len(email_per_lead),
                    "total": len(leads_da_contattare),
                    "parsed_nomi": [
                        next((l["nome"] for l in leads_da_contattare if l["id"] == lid), str(lid))
                        for lid in email_per_lead
                    ],
                }

                # BUG FIX: set "email_pronta" only for leads where email was actually parsed;
                # leave others as "da_contattare" so they remain actionable
                aggiorna_leads_campagna({
                    l["id"]: {
                        "email_generate": (
                            [email_per_lead[l["id"]]] if l["id"] in email_per_lead else []
                        ),
                        "stato": "email_pronta" if l["id"] in email_per_lead else l.get("stato", "da_contattare"),
                    }
                    for l in leads_da_contattare
                })
                st.rerun()
        else:
            n_parsed = st.session_state.debug_email_campagna.get("parsed_count", "?") if st.session_state.debug_email_campagna else "?"
            n_total = st.session_state.debug_email_campagna.get("total", "?") if st.session_state.debug_email_campagna else "?"
            if isinstance(n_parsed, int) and isinstance(n_total, int) and n_parsed < n_total:
                st.warning(f"⚠️ Email generate solo per {n_parsed}/{n_total} lead. Verifica il debug qui sotto.")
            else:
                st.success("✅ Email generate! Lead aggiornati a stato **email_pronta**.")
            st.info("Vai a **📧 Email pronte** dalla sidebar per rivedere, modificare e segnare come contattati.")

            # Debug expander — always shown after generation, expanded if there were parse failures
            if st.session_state.debug_email_campagna:
                dbg = st.session_state.debug_email_campagna
                parse_ok = dbg.get("parsed_count", 0) == dbg.get("total", 0)
                with st.expander(
                    f"🔍 Debug Email Sender: {dbg.get('parsed_count',0)}/{dbg.get('total',0)} email parsate"
                    + (" ✅" if parse_ok else " ⚠️ parsing incompleto"),
                    expanded=not parse_ok
                ):
                    st.markdown("**Dati passati all'Email Sender:**")
                    st.code(dbg.get("leads_debug", ""), language=None)
                    st.markdown("**Contatti passati (anteprima 600 chars):**")
                    st.code(dbg.get("contatti_preview", ""), language=None)
                    st.markdown(f"**Output grezzo LLM (prime 3000 chars):**")
                    st.code(dbg.get("output_raw", ""), language=None)
                    if dbg.get("parsed_nomi"):
                        st.markdown(f"**Lead con email parsata:** {', '.join(dbg['parsed_nomi'])}")

            if st.button("🔄 Nuova campagna (reset risultati)"):
                st.session_state.risultato_contatti_campagna = None
                st.session_state.risultato_email_campagna = None
                st.session_state.leads_per_campagna = []
                st.session_state.campagna_attiva = False
                st.rerun()

    if st.button("← Torna ai lead"):
        st.session_state.campagna_attiva = False
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL PRONTE
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📧 Email pronte":
    st.title("📧 Email pronte")
    st.subheader("Rivedi, modifica e segna come contattati")

    tutti_leads = carica_leads()
    leads_email_pronti = [l for l in tutti_leads if l.get("stato") == "email_pronta"]

    if not leads_email_pronti:
        st.info(
            "Nessuna email pronta. Avvia una campagna email dalla pagina **Lead salvati** "
            "o dalla sidebar per generare le email."
        )
    else:
        st.caption(f"✉️ {len(leads_email_pronti)} lead con email pronte")
        st.divider()

        for lead in leads_email_pronti:
            lead_id = lead.get("id")
            score = lead.get("score", 0)
            badge = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
            contatti = lead.get("contatti_trovati", [])
            email_generate = lead.get("email_generate", [])

            label = f"{badge} {lead.get('nome', 'N/D')} — {lead.get('citta', '')} | Score: {score}/10"
            with st.expander(label, expanded=True):
                col_info, col_azioni = st.columns([3, 1])

                with col_info:
                    st.markdown(f"**Settore:** {lead.get('settore', 'N/D')}")
                    st.markdown(f"**Sito:** {lead.get('sito', 'N/D')}")

                    st.markdown("---")

                    # ── Selettore contatti ────────────────────────────────
                    if contatti:
                        opzioni = [
                            f"{c.get('nome_contatto', 'N/D')} — {c.get('ruolo', 'N/D')} ({c.get('email', 'N/D')})"
                            for c in contatti
                        ]
                        idx_sel = st.selectbox(
                            "Contatto selezionato",
                            range(len(opzioni)),
                            format_func=lambda i: opzioni[i],
                            key=f"contatto_sel_{lead_id}",
                        )
                        c_sel = contatti[idx_sel]
                        if c_sel.get("telefono"):
                            st.caption(f"📞 {c_sel['telefono']}")
                    else:
                        st.warning("Nessun contatto strutturato trovato per questo lead.")
                        idx_sel = 0

                    # ── Email modificabile ────────────────────────────────
                    if email_generate:
                        email_idx = min(idx_sel, len(email_generate) - 1)
                        email_testo = email_generate[email_idx]
                    else:
                        email_testo = ""

                    st.text_area(
                        "Email (modificabile prima dell'invio)",
                        value=email_testo,
                        height=350,
                        key=f"email_edit_{lead_id}",
                    )

                with col_azioni:
                    st.markdown(f"**Score:** {score}/10")
                    if lead.get("motivazione_score"):
                        st.caption(lead["motivazione_score"])
                    st.markdown("---")
                    if st.button(
                        "✅ Segna come contattato",
                        key=f"contattato_{lead_id}",
                        use_container_width=True,
                        type="primary",
                    ):
                        aggiorna_stato_lead(lead_id, "contattato")
                        st.rerun()
                    if st.button(
                        "❌ Non interessante",
                        key=f"non_int_{lead_id}",
                        use_container_width=True,
                    ):
                        aggiorna_stato_lead(lead_id, "non_interessante")
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# CLIENTI ESISTENTI
# ══════════════════════════════════════════════════════════════════════════════
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
