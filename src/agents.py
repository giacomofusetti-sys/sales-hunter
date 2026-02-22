import os
from crewai import Agent, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

search_tool = SerperDevTool()
scrape_tool = ScrapeWebsiteTool()

claude = LLM(
    model="anthropic/claude-haiku-4-5-20251001",
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

def crea_prospector(max_iter=8):
    return Agent(
        role="Ricercatore di Potenziali Clienti",
        goal=(
            "Trovare aziende italiane che potrebbero aver bisogno di viteria speciale e tiranteria, "
            "nella regione e nel settore indicati."
        ),
        backstory=(
            "Sei un esperto di ricerca commerciale B2B nel mercato italiano. "
            "Conosci bene i settori industriali che utilizzano viteria speciale e tiranteria: "
            "carpenteria metallica, costruzioni, oil & gas, energia, impianti industriali, "
            "macchine agricole, cantieristica navale. "
            "Sai cercare aziende su Google, leggere i loro siti e capire se sono clienti potenziali."
        ),
        tools=[search_tool, scrape_tool],
        verbose=True,
        llm=claude,
        max_iter=max_iter
    )

def crea_contact_hunter(max_iter=8):
    return Agent(
        role="Cacciatore di Contatti Commerciali",
        goal=(
            "Trovare il contatto giusto in ogni azienda: nome, ruolo e email "
            "del responsabile acquisti o dell'ufficio tecnico."
        ),
        backstory=(
            "Sei un esperto nel trovare contatti B2B nelle aziende italiane. "
            "Sai cercare sui siti aziendali, LinkedIn, pagine ufficiali e database pubblici. "
            "Trovi sempre il nome della persona giusta da contattare, non solo info generiche."
        ),
        tools=[search_tool, scrape_tool],
        verbose=True,
        llm=claude,
        max_iter=max_iter
    )