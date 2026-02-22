from crewai import Task

def crea_task_ricerca(agente, regione, settore, num_aziende=3):
    return Task(
        description=(
            f"Cerca aziende nella regione {regione} che operano nel settore {settore} "
            f"e che potrebbero aver bisogno di viteria speciale e tiranteria. "
            f"Per ogni azienda trovata, cerca di capire: "
            f"1. Cosa fa esattamente "
            f"2. Che tipo di lavorazioni o impianti usa "
            f"3. Perché potrebbe aver bisogno di viteria speciale "
            f"4. Sito web se disponibile "
            f"Trova esattamente {num_aziende} aziende concrete e reali."
        ),
        expected_output=(
            f"Una lista in formato testo semplice di esattamente {num_aziende} aziende. "
            "Per ogni azienda scrivi: nome, città, sito web, descrizione attività, "
            "motivo per cui potrebbero essere clienti interessanti. "
            "NON includere tag XML, codice o comandi. Solo testo leggibile."
        ),
        agent=agente
    )

def crea_task_contatti(agente, lista_aziende):
    return Task(
        description=(
            f"Per ognuna di queste aziende, trova il contatto giusto da raggiungere:\n"
            f"{lista_aziende}\n\n"
            f"Priorità assoluta: trova il responsabile acquisti (Purchasing Manager, "
            f"Responsabile Acquisti, Supply Chain Manager, Procurement Manager). "
            f"Solo se non lo trovi, cerca il responsabile ufficio tecnico o il direttore generale.\n\n"
            f"Per ogni azienda cerca:\n"
            f"1. Nome e cognome del responsabile acquisti\n"
            f"2. Il suo ruolo esatto\n"
            f"3. Email diretta se possibile, altrimenti email generica aziendale\n"
            f"4. Numero di telefono se disponibile\n\n"
            f"Cerca sul sito aziendale, pagina contatti, LinkedIn, e Google."
        ),
        expected_output=(
            "Una lista in formato testo semplice con per ogni azienda: "
            "nome contatto, ruolo, email, telefono. "
            "NON includere tag XML, codice o comandi. Solo testo leggibile. "
            "Se non trovi il contatto diretto, indica almeno l'email generica aziendale."
        ),
        agent=agente
    )
