from crewai import Task
from profilo_azienda import PROFILO_AZIENDA

def crea_task_ricerca(agente, regione, settore, num_aziende=3):
    return Task(
        description=(
            f"Sei il commerciale di un'azienda italiana produttrice di viteria speciale e tiranteria. "
            f"Il tuo obiettivo è trovare {num_aziende} aziende in '{regione}' nel settore '{settore}' "
            f"che siano potenziali clienti.\n\n"
            f"PROFILO DELL'AZIENDA CHE RAPPRESENTI (usalo per qualificare i prospect):\n{PROFILO_AZIENDA}\n\n"
            f"Per qualificare un'azienda come buon prospect, valuta:\n"
            f"- Usano bulloneria critica o certificata (flangie, scambiatori, valvole, strutture in pressione)?\n"
            f"- Potrebbero aver bisogno di materiali speciali (B7, L7, 42CD4, inox, superleghe)?\n"
            f"- Operano in settori dove contano qualità e certificazioni ISO/TÜV?\n"
            f"- Potrebbero apprezzare piccole serie su misura o consegne rapide?\n\n"
            f"Trova esattamente {num_aziende} aziende concrete e reali, con sito web verificato."
        ),
        expected_output=(
            f"Una lista in formato testo semplice di esattamente {num_aziende} aziende. "
            "Per ogni azienda scrivi:\n"
            "- Nome azienda e città\n"
            "- Sito web\n"
            "- Descrizione attività\n"
            "- Perché è un buon prospect (collegamento specifico ai prodotti/materiali/settori dell'azienda fornitrice)\n"
            "NON includere tag XML, codice o comandi. Solo testo leggibile."
        ),
        agent=agente
    )

def crea_task_contatti(agente, lista_aziende):
    return Task(
        description=(
            f"IMPORTANTE: completa la ricerca per TUTTE le aziende nella lista prima di dare la risposta finale.\n\n"
            f"Stai cercando contatti per proporre forniture di viteria speciale e tiranteria certificata. "
            f"Il profilo dell'azienda fornitrice è il seguente:\n{PROFILO_AZIENDA}\n\n"
            f"Aziende da contattare:\n{lista_aziende}\n\n"
            f"Per ogni azienda, individua il contatto più rilevante per questo tipo di fornitura:\n"
            f"1. Prima scelta: Responsabile Acquisti / Procurement Manager / Supply Chain Manager\n"
            f"2. Seconda scelta: Responsabile Ufficio Tecnico (se la fornitura è su disegno)\n"
            f"3. Terza scelta: Direttore Generale o Operations Manager\n\n"
            f"Per ogni contatto cerca:\n"
            f"- Nome e cognome\n"
            f"- Ruolo esatto\n"
            f"- Email diretta (o aziendale generica se non disponibile)\n"
            f"- Telefono se disponibile\n\n"
            f"Cerca sul sito aziendale, pagina contatti, LinkedIn, Google."
        ),
        expected_output=(
            "Una lista in formato testo semplice con per ogni azienda:\n"
            "- Nome azienda\n"
            "- Nome e cognome del contatto\n"
            "- Ruolo\n"
            "- Email\n"
            "- Telefono (se disponibile)\n"
            "NON includere tag XML, codice o comandi. Solo testo leggibile. "
            "Se non trovi il contatto diretto, indica almeno l'email generica aziendale."
        ),
        agent=agente
    )
