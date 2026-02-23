import json
import os
from datetime import datetime

DB_FILE = "leads.json"


def carica_db():
    if not os.path.exists(DB_FILE):
        return {"leads": [], "clienti_esistenti": [], "ricerche": []}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def salva_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def salva_ricerca(settore, area, risultato_aziende, risultato_contatti):
    db = carica_db()
    ricerca = {
        "id": len(db["ricerche"]) + 1,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "settore": settore,
        "area": area,
        "aziende": risultato_aziende,
        "contatti": risultato_contatti,
        "stato": "completata"
    }
    db["ricerche"].append(ricerca)
    salva_db(db)
    return ricerca["id"]


def aggiungi_cliente_esistente(nome):
    db = carica_db()
    if nome not in db["clienti_esistenti"]:
        db["clienti_esistenti"].append(nome)
        salva_db(db)


def carica_clienti_esistenti():
    db = carica_db()
    return db["clienti_esistenti"]


def carica_ricerche():
    db = carica_db()
    return db["ricerche"]


def salva_leads(nuovi_leads, settore, area):
    """Salva lead strutturati (output Analyst) nel database."""
    db = carica_db()
    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")

    existing_ids = [l.get("id", 0) for l in db.get("leads", [])]
    next_id = max(existing_ids, default=0) + 1

    for i, lead in enumerate(nuovi_leads):
        lead["id"] = next_id + i
        lead["data_ricerca"] = data_ora
        lead.setdefault("settore", settore)
        lead["area_ricerca"] = area
        lead.setdefault("stato", "da_contattare")

    db.setdefault("leads", []).extend(nuovi_leads)
    salva_db(db)
    return len(nuovi_leads)


def carica_leads():
    """Carica tutti i lead strutturati."""
    db = carica_db()
    return db.get("leads", [])


def aggiorna_stato_lead(lead_id, nuovo_stato):
    """Aggiorna lo stato di un singolo lead."""
    db = carica_db()
    for lead in db.get("leads", []):
        if lead.get("id") == lead_id:
            lead["stato"] = nuovo_stato
            break
    salva_db(db)

