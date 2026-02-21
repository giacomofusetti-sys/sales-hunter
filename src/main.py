import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__)))

from dotenv import load_dotenv
from crewai import Crew
from agents import crea_prospector, crea_contact_hunter
from tasks import crea_task_ricerca, crea_task_contatti

load_dotenv()

os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")

# Parametri di ricerca
REGIONE = "Lombardia"
SETTORE = "carpenteria metallica"

# Crea agenti
prospector = crea_prospector()
contact_hunter = crea_contact_hunter()

# Crea task di ricerca
task_ricerca = crea_task_ricerca(prospector, REGIONE, SETTORE)

# Crea task contatti (prende l'output del task precedente)
task_contatti = crea_task_contatti(contact_hunter, "{{task_ricerca.output}}")

# Crea ed esegui la crew con entrambi gli agenti in sequenza
crew = Crew(
    agents=[prospector, contact_hunter],
    tasks=[task_ricerca, task_contatti],
    verbose=True
)

print(f"\n🔍 Avvio ricerca clienti in {REGIONE} - settore: {SETTORE}\n")
risultato = crew.kickoff()
print("\n✅ RISULTATO FINALE:\n")
print(risultato)
