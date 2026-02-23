import os
from crewai import Agent, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from profilo_azienda import PROFILO_AZIENDA

search_tool = SerperDevTool()
scrape_tool = ScrapeWebsiteTool()

claude = LLM(
    model="anthropic/claude-haiku-4-5-20251001",
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

def crea_prospector(max_iter=12):
    return Agent(
        role="Ricercatore di Potenziali Clienti B2B",
        goal=(
            "Trovare aziende nel settore e nell'area indicati che abbiano un bisogno concreto "
            "di viteria speciale, tiranteria e bulloneria certificata, e che siano un buon match "
            "per i prodotti, i materiali e le capacità produttive dell'azienda fornitrice.\n\n"
            f"PROFILO DELL'AZIENDA CHE RAPPRESENTI:\n{PROFILO_AZIENDA}"
        ),
        backstory=(
            "Sei un esperto di sviluppo commerciale B2B nel settore industriale. "
            "Lavori per conto di un produttore italiano di viteria speciale e tiranteria. "
            "Conosci a fondo cosa produce e vende questa azienda, i suoi punti di forza e i suoi clienti tipo.\n\n"
            f"PROFILO DELL'AZIENDA CHE RAPPRESENTI:\n{PROFILO_AZIENDA}\n\n"
            "Quando cerchi potenziali clienti, valuti se usano materiali come 42CD4, B7, L7, inox o superleghe, "
            "se operano in settori dove la bulloneria certificata è critica (oil & gas, navale, energia, impianti), "
            "se potrebbero apprezzare forniture su misura, piccole serie o consegne rapide. "
            "Sai cercare su Google, leggere siti aziendali e qualificare un lead in modo preciso."
        ),
        tools=[search_tool, scrape_tool],
        verbose=True,
        llm=claude,
        max_iter=max_iter
    )

def crea_contact_hunter(max_iter=12):
    return Agent(
        role="Cacciatore di Contatti Commerciali",
        goal=(
            "Per ogni azienda trovata, individuare il contatto più rilevante da raggiungere "
            "per proporre forniture di viteria speciale e tiranteria certificata.\n\n"
            f"PROFILO DELL'AZIENDA CHE RAPPRESENTI:\n{PROFILO_AZIENDA}"
        ),
        backstory=(
            "Sei un esperto nel trovare i contatti giusti per campagne di sviluppo commerciale B2B. "
            "Lavori per conto di un produttore italiano di viteria speciale e tiranteria. "
            "Sai esattamente a chi rivolgerti in azienda per proporre questo tipo di fornitura.\n\n"
            f"PROFILO DELL'AZIENDA CHE RAPPRESENTI:\n{PROFILO_AZIENDA}\n\n"
            "Per questo tipo di prodotto, il contatto ideale è il responsabile acquisti o procurement, "
            "oppure il responsabile ufficio tecnico se la fornitura è su disegno. "
            "Sai cercare su siti aziendali, LinkedIn, pagine contatti e database pubblici. "
            "Non ti fermi a email generiche: cerchi nomi e ruoli reali."
        ),
        tools=[search_tool, scrape_tool],
        verbose=True,
        llm=claude,
        max_iter=max_iter
    )