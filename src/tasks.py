from crewai import Task


def crea_task_ricerca(agente, regione, settore):
    return Task(
        description=(
            f"Cerca aziende nella regione {regione} che operano nel settore {settore} "
            f"e che potrebbero aver bisogno di viteria speciale e tiranteria. "
            f"Per ogni azienda trovata, cerca di capire: "
            f"1. Cosa fa esattamente "
            f"2. Che tipo di lavorazioni o impianti usa "
            f"3. Perché potrebbe aver bisogno di viteria speciale "
            f"4. Sito web se disponibile "
            f"Trova almeno 5 aziende concrete e reali."
        ),
        expected_output=(
            "Una lista di almeno 5 aziende con per ognuna: "
            "nome, città, descrizione attività, sito web, "
            "e motivazione per cui potrebbero essere clienti interessanti."
        ),
        agent=agente
    )

def crea_task_contatti(agente, lista_aziende):
    return Task(
        description=(
            f"Per ognuna di queste aziende, trova il contatto giusto da raggiungere:\n"
            f"{lista_aziende}\n\n"
            f"Per ogni azienda cerca:\n"
            f"1. Nome e cognome del responsabile acquisti o ufficio tecnico\n"
            f"2. Il suo ruolo esatto\n"
            f"3. Email diretta se possibile, altrimenti email generica aziendale\n"
            f"4. Numero di telefono se disponibile\n\n"
            f"Cerca sul sito aziendale, pagina contatti, LinkedIn, e Google."
        ),
        expected_output=(
            "Una lista strutturata con per ogni azienda: "
            "nome contatto, ruolo, email, telefono. "
            "Se non trovi il contatto diretto, indica almeno l'email generica aziendale."
        ),
        agent=agente
    )
