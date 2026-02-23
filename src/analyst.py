import os
import json
import re
from crewai import Agent, Task, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from profilo_azienda import PROFILO_AZIENDA

search_tool = SerperDevTool()
scrape_tool = ScrapeWebsiteTool()

claude = LLM(
    model="anthropic/claude-haiku-4-5-20251001",
    api_key=os.getenv("ANTHROPIC_API_KEY")
)


def crea_analyst(max_iter=12):
    return Agent(
        role="Analista di Prospect Commerciali B2B",
        goal=(
            "Valutare ogni azienda identificata dal Prospector, assegnare uno score da 1 a 10 "
            "e cercare notizie recenti per identificare i migliori prospect per viteria speciale "
            "e tiranteria certificata.\n\n"
            f"PROFILO DELL'AZIENDA CHE RAPPRESENTI:\n{PROFILO_AZIENDA}"
        ),
        backstory=(
            "Sei un analista commerciale B2B specializzato nel settore industriale. "
            "Lavori per un produttore italiano di viteria speciale e tiranteria certificata. "
            "Il tuo compito è valutare la qualità di ogni prospect, cercarne notizie recenti "
            "(nuovi impianti, contratti, espansioni, certificazioni) e produrre un punteggio "
            "numerico da 1 a 10 con motivazione chiara e concisa.\n\n"
            f"PROFILO DELL'AZIENDA CHE RAPPRESENTI:\n{PROFILO_AZIENDA}\n\n"
            "Criteri di scoring:\n"
            "8-10: Settore critico (oil & gas, navale, energy), usa materiali certificati "
            "(B7, L7, 42CD4, inox, superleghe), notizie recenti di crescita o nuovi impianti. "
            "Bonus se il prospect lavora con diametri grandi (>M80) dove il commercio non arriva, "
            "o se usa superleghe/acciai speciali su range M6–M80 dove il vantaggio competitivo è massimo.\n"
            "5-7: Settore industriale con probabile uso di bulloneria speciale o certificata\n"
            "1-4: Settore a bassa rilevanza, dimensioni ridotte, scarse informazioni disponibili"
        ),
        tools=[search_tool, scrape_tool],
        verbose=True,
        llm=claude,
        max_iter=max_iter
    )


def crea_task_analisi(agente, lista_aziende, settore, area):
    return Task(
        description=(
            f"Analizza le aziende identificate nel settore '{settore}' nell'area '{area}'.\n\n"
            f"AZIENDE DA ANALIZZARE:\n{lista_aziende}\n\n"
            f"Per ogni azienda:\n"
            f"1. Cerca su Google notizie recenti (ultimi 12 mesi): nuovi contratti, espansioni, "
            f"   nuovi impianti, acquisizioni, certificazioni ottenute, bandi vinti\n"
            f"2. Consulta il sito aziendale se necessario per verificare prodotti e dimensioni\n"
            f"3. Assegna uno score da 1 a 10 in base alla compatibilità con il profilo fornitore\n"
            f"   Nel valutare lo score considera:\n"
            f"   - Il prospect usa bulloneria di grande diametro (>M80)? Questi sono quasi introvabili "
            f"dal commercio: score alto anche su materiali comuni.\n"
            f"   - Il prospect usa superleghe o acciai speciali (Inconel, B7, 42CD4, duplex) in range "
            f"M6–M80? Massimo vantaggio competitivo del fornitore.\n"
            f"   - Il prospect usa solo bulloneria standard in acciai comuni su piccoli diametri? "
            f"Score più basso, alta concorrenza commerciale.\n"
            f"4. Scrivi una motivazione concisa per lo score (2-3 frasi), citando se possibile "
            f"il range di diametri e i materiali probabilmente usati dal prospect.\n\n"
            f"PROFILO FORNITORE (usa per valutare compatibilità):\n{PROFILO_AZIENDA}\n\n"
            f"IMPORTANTE: Analizza TUTTE le aziende elencate prima di rispondere. "
            f"Rispondi SOLO con un array JSON valido, nessun testo prima o dopo il JSON."
        ),
        expected_output=(
            'Rispondi ESCLUSIVAMENTE con un array JSON valido. Nessun testo prima o dopo. '
            'Ogni elemento deve avere esattamente questi campi:\n'
            '[\n'
            '  {\n'
            '    "nome": "Nome Azienda Srl",\n'
            '    "citta": "Milano",\n'
            '    "settore": "Valvole industriali",\n'
            '    "sito": "www.azienda.it",\n'
            '    "descrizione": "Produttore di valvole per impianti industriali ad alta pressione",\n'
            '    "score": 8,\n'
            '    "motivazione_score": "Opera in oil & gas con bulloneria certificata B7/L7. '
            'Espansione recente in nuovi impianti ENI.",\n'
            '    "notizie_recenti": "Giugno 2024: vinto contratto impianto ENI da 2M euro",\n'
            '    "stato": "da_contattare"\n'
            '  }\n'
            ']\n'
            'Il campo "stato" deve essere sempre "da_contattare" per i nuovi lead. '
            'Il campo "score" deve essere un numero intero da 1 a 10.'
        ),
        agent=agente
    )


def parse_leads_json(testo_output):
    """Estrae e parsa l'array JSON dall'output dell'Analyst."""
    testo = testo_output.strip()

    # Tentativo diretto
    try:
        data = json.loads(testo)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Cerca blocco JSON in markdown (```json ... ``` o ``` ... ```)
    match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', testo)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # Cerca array JSON grezzo nel testo
    match = re.search(r'\[[\s\S]*\]', testo)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    return []
