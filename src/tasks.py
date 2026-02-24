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

def crea_task_contatti_lead(agente, leads):
    """Task Fase 2: trova contatti partendo da lead strutturati."""
    lista_testo = ""
    for l in leads:
        lista_testo += (
            f"- {l.get('nome', 'N/D')} ({l.get('citta', '')})\n"
            f"  Sito: {l.get('sito', 'N/D')}\n"
            f"  Settore: {l.get('settore', 'N/D')}\n"
            f"  Descrizione: {l.get('descrizione', 'N/D')}\n\n"
        )
    return Task(
        description=(
            f"IMPORTANTE: Completa la ricerca contatti per TUTTE le aziende prima di rispondere.\n\n"
            f"Stai cercando contatti per proporre forniture di viteria speciale e tiranteria certificata.\n"
            f"Profilo fornitore:\n{PROFILO_AZIENDA}\n\n"
            f"Aziende da contattare:\n{lista_testo}\n"
            f"Per ogni azienda individua il contatto più rilevante:\n"
            f"1. Prima scelta: Responsabile Acquisti / Procurement Manager\n"
            f"2. Seconda scelta: Responsabile Ufficio Tecnico\n"
            f"3. Terza scelta: Direttore Generale o Operations Manager\n\n"
            f"Cerca su sito aziendale, pagina contatti, LinkedIn, Google.\n\n"
            f"REGOLA OBBLIGATORIA: Per ogni azienda DEVI sempre produrre un risultato completo.\n"
            f"Se non trovi il contatto diretto entro 2 tentativi di ricerca, NON continuare a cercare:\n"
            f"vai sul sito aziendale, recupera l'email generica (info@, commerciale@, contatti@)\n"
            f"e il numero di telefono generico, e scrivi ESATTAMENTE:\n"
            f"'Contatto diretto non trovato - utilizzare email generica: [email trovata]'\n"
            f"MAI lasciare un'azienda senza risultato. MAI saltare un'azienda."
        ),
        expected_output=(
            "Lista testo con per ogni azienda nella lista (TUTTE, nessuna esclusa):\n"
            "- Nome azienda\n"
            "- Nome e cognome contatto (o 'Contatto diretto non trovato' se non disponibile)\n"
            "- Ruolo\n"
            "- Email (diretta o generica - OBBLIGATORIA: almeno info@dominio.com)\n"
            "- Telefono (se disponibile)\n"
            "Se non trovi il contatto diretto, scrivi ESATTAMENTE: "
            "'Contatto diretto non trovato - utilizzare email generica: [email generica]'"
        ),
        agent=agente
    )


def crea_task_email(agente, leads, contatti):
    """Task Fase 2: redige email commerciali bilinguì e personalizzate."""
    leads_info = "\n".join([
        f"- {l.get('nome', '')} | Settore: {l.get('settore', 'N/D')} | Città: {l.get('citta', 'N/D')}\n"
        f"  Descrizione: {l.get('descrizione', 'N/D')}\n"
        f"  Notizie recenti: {l.get('notizie_recenti', 'Nessuna notizia recente')}\n"
        f"  Score: {l.get('score', 'N/D')}/10 | Motivazione: {l.get('motivazione_score', '')}"
        for l in leads
    ])

    # Mappatura settore → prodotti più rilevanti da menzionare
    settori_prodotti = (
        "GUIDA PRODOTTI PER SETTORE (usa questa mappatura per personalizzare):\n"
        "- Scambiatori di calore / Heat exchangers → Tiranti e prigionieri B7/L7 ASTM A193, viti TE in 42CD4 "
        "  (rif. clienti: Alfa Laval Olmi, Boldrocchi, Wieland)\n"
        "- Oil & Gas / Petrolchimico → Tiranti B7/L7, prigionieri in Inconel/Monel/Hastelloy, "
        "  viti con trattamento Geomet o Delta-Protekt (rif. clienti: Cameron Italy/Schlumberger, SIAD Macchine Impianti, Solvay)\n"
        "- Valvole industriali → Prigionieri e viti TCE in inox 316/316L o duplex, "
        "  materiali tracciati con certificati di collaudo (rif. clienti: Cameron Italy, Emerson Process Management)\n"
        "- Navale / Cantieristica → Viti TE e prigionieri in inox 316L o superleghe, "
        "  trattamenti anticorrosione (sherardizzazione, geomet)\n"
        "- Carpenteria metallica / Costruzioni → Viti 8.8/10.9, tiranti su misura, "
        "  zincatura a caldo (rif. clienti: Tenconi, AFI Assemblage Forge Industrie)\n"
        "- Energia / Rinnovabili → Tiranti e viti in acciai speciali certificati, piccole serie su disegno\n"
        "- Industria chimica → Materiali resistenti alla corrosione (Hastelloy, duplex, PTFE-coating), "
        "  tracciabilità completa (rif. clienti: Solvay Chimica)\n"
        "\n"
        "VANTAGGI COMPETITIVI DA USARE NELL'EMAIL (in base al profilo del prospect):\n"
        "- Se il prospect usa bulloneria di GRANDE DIAMETRO (>M80, es. grandi flangie, strutture pesanti,\n"
        "  apparecchi a pressione di taglia rilevante): sottolinea che questi diametri sono\n"
        "  normalmente introvabili dal commercio e che la produzione avviene esclusivamente su ordine\n"
        "  tramite stampaggio a caldo (fino a M80) o tornitura CNC (oltre M80).\n"
        "- Se il prospect usa SUPERLEGHE o ACCIAI SPECIALI su diametri medi (M6–M80, es. Inconel,\n"
        "  Monel, Hastelloy, B7, 42CD4): sottolinea che il commercio standard non copre queste\n"
        "  combinazioni materiale/dimensione, e che la produzione su disegno è l'unica alternativa.\n"
        "- TIRANTI: nessun limite pratico di lunghezza, produzione su misura completa.\n"
        "- NON menzionare il vantaggio dimensionale se il prospect usa solo bulloneria standard\n"
        "  in acciai comuni su piccoli diametri: in quel caso la leva è certificazione e qualità.\n"
    )

    return Task(
        description=(
            f"Redigi email commerciali B2B personalizzate per ogni azienda prospect, "
            f"in DOPPIA VERSIONE: prima in italiano, poi in inglese.\n\n"
            f"PROFILO AZIENDA FORNITRICE:\n{PROFILO_AZIENDA}\n\n"
            f"{settori_prodotti}\n"
            f"LEAD (con dettagli, settore e notizie recenti):\n{leads_info}\n\n"
            f"CONTATTI TROVATI DAL CONTACT HUNTER:\n{contatti}\n\n"
            f"ISTRUZIONI DETTAGLIATE PER OGNI EMAIL:\n\n"
            f"1. OGGETTO — deve essere tecnico e specifico, non generico:\n"
            f"   Formato suggerito: '[Prodotto rilevante] certificati per [settore prospect] – [nome azienda prospect]'\n"
            f"   Esempio: 'Tiranti B7/L7 ASTM A193 per scambiatori a fascio tubiero – [Nome Azienda]'\n\n"
            f"2. APERTURA (2-3 righe) — gancio personalizzato:\n"
            f"   - Se ci sono notizie recenti (nuovo impianto, acquisizione, espansione, gara vinta): usale!\n"
            f"   - Altrimenti: commenta il settore dell'azienda con una osservazione tecnica pertinente\n"
            f"   - Mai iniziare con 'Mi chiamo' o 'La contatto perché'\n\n"
            f"3. CORPO (3-4 righe) — proposta di valore specifica:\n"
            f"   - Menziona esplicitamente 1-2 prodotti specifici coerenti con il settore del prospect\n"
            f"   - Se rilevante, cita le capacità dimensionali come leva commerciale:\n"
            f"     es. 'produciamo viti fino a M80 con stampaggio a caldo e oltre tramite tornitura CNC,\n"
            f"     con tiranti senza limiti di lunghezza' — utile per prospect con esigenze fuori standard\n"
            f"   - Cita 1-2 clienti del portfolio già attivi in quel settore come referenza credibile\n"
            f"     (usa solo clienti reali dal profilo: Alfa Laval Olmi, Cameron Italy, SIAD, Boldrocchi, Emerson, Solvay, ecc.)\n"
            f"   - Evidenzia i punti di forza più rilevanti per quel cliente: piccole serie, "
            f"     consegne rapide, certificazioni ISO 9001 + TÜV SÜD, tracciabilità materiali\n\n"
            f"4. CALL TO ACTION — concreta, non generica:\n"
            f"   - Proponi una call di 20 minuti o una visita in sede la settimana successiva\n"
            f"   - Non scrivere solo 'sono disponibile per qualsiasi informazione'\n\n"
            f"5. FIRMA:\n"
            f"   [Nome Commerciale]\n"
            f"   Area Manager – [Zona geografica del prospect]\n"
            f"   [Nome Azienda] | Viteria Speciale & Tiranteria Certificata\n"
            f"   Tel: [numero] | Email: [email]\n\n"
            f"REGOLE:\n"
            f"- Max 180 parole per versione (IT e EN)\n"
            f"- Tono: professionale, tecnico, diretto — non freddo, non da template automatico\n"
            f"- La versione inglese deve essere una vera traduzione adattata, non letterale\n"
            f"- Ogni email deve sembrare scritta a mano per quella specifica azienda"
        ),
        expected_output=(
            "Per ogni azienda, il blocco completo separato da '===':\n\n"
            "AZIENDA: [nome]\n"
            "A: [nome contatto] – [ruolo]\n\n"
            "── VERSIONE ITALIANA ──\n"
            "Oggetto: [oggetto in italiano]\n\n"
            "[corpo email in italiano]\n\n"
            "[firma]\n\n"
            "── ENGLISH VERSION ──\n"
            "Subject: [subject in English]\n\n"
            "[email body in English]\n\n"
            "[signature]\n\n"
            "===\n"
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
