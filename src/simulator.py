import os
import time
import signal
import random
import logging
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import assigner

# Logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "lead_simulator.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Configuración desde .env ---
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT"),
    "database": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}

# Parametrización de simulación
SIMULATION_INTERVAL = int(os.getenv("SIMULATION_INTERVAL", 30))
LEADS_MIN = int(os.getenv("LEADS_MIN", 1))
LEADS_MAX = int(os.getenv("LEADS_MAX", 5))
INITIAL_ASSIGNMENT_STATUS = os.getenv("INITIAL_ASSIGNMENT_STATUS", "Pending")


# --- Conexión ---
def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# --- Helpers ---
def get_status_id(cursor, status_name=INITIAL_ASSIGNMENT_STATUS):
    """Devuelve el assignment_status_id (case-insensitive). Crea si no existe."""
    cursor.execute(
        """
        SELECT assignment_status_id
        FROM lead_management.assignment_statuses
        WHERE LOWER(name) = LOWER(%s)
        """,
        (status_name,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        """
        INSERT INTO lead_management.assignment_statuses (name)
        VALUES (%s)
        RETURNING assignment_status_id
        """,
        (status_name,),
    )
    new_id = cursor.fetchone()[0]
    logger.info(f"Created new assignment status '{status_name}' with id {new_id}")
    return new_id


def pick_random_id(cursor, table, id_col):
    """Devuelve un id aleatorio válido de la tabla indicada."""
    cursor.execute(f"SELECT {id_col} FROM lead_management.{table} ORDER BY RANDOM() LIMIT 1")
    return cursor.fetchone()[0]


def generate_fake_lead(cursor, i):
    """Genera un lead coherente con llaves foráneas válidas."""
    business_line_id = pick_random_id(cursor, "business_lines", "business_line_id")
    country_id = pick_random_id(cursor, "countries", "country_id")
    document_type_id = pick_random_id(cursor, "document_types", "document_type_id")

    doc_num = f"L{i}{random.randint(1000, 9999)}"
    given_name = random.choice(["Juan", "Maria", "Pedro", "Ana", "Luis", "Sofia", "Carlos"])
    surname = random.choice(["Gomez", "Perez", "Martinez", "Lopez", "Rodriguez", "Mendez"])
    phone = f"+57{random.randint(3000000000, 3999999999)}"
    email = f"{given_name.lower()}.{surname.lower()}{random.randint(1,999)}@example.com"

    return (
        doc_num,
        given_name,
        surname,
        phone,
        email,
        business_line_id,
        country_id,
        document_type_id,
    )


def insert_lead_and_pending_assignment(cursor, lead):
    """Inserta un lead y crea automáticamente un assignment con estado parametrizado."""
    cursor.execute(
        """
        INSERT INTO lead_management.leads (
            document_number, given_name, surname, phone, email,
            business_line_id, country_id, document_type_id
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (document_number) DO NOTHING
        RETURNING document_number
        """,
        lead,
    )
    row = cursor.fetchone()
    if not row:
        logger.warning(f"Lead {lead[0]} already exists, skipping assignment creation.")
        return

    lead_document_number = row[0]
    status_id = get_status_id(cursor, INITIAL_ASSIGNMENT_STATUS)

    cursor.execute(
        """
        INSERT INTO lead_management.assignments (
            assigned_at, seller_document_number, lead_document_number, assignment_status_id
        )
        VALUES (NOW(), NULL, %s, %s)
        """,
        (lead_document_number, status_id),
    )
    logger.info(f"Lead {lead_document_number} inserted with assignment status '{INITIAL_ASSIGNMENT_STATUS}'.")


def run_simulation_cycle(cycle_num):
    """Ejecuta un ciclo de generación + asignación."""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        n_leads = random.randint(LEADS_MIN, LEADS_MAX)
        logger.info(f"Generating {n_leads} leads in cycle {cycle_num}.")

        for i in range(n_leads):
            lead = generate_fake_lead(cursor, f"{cycle_num}_{i}")
            insert_lead_and_pending_assignment(cursor, lead)

        conn.commit()
        cursor.close()
        conn.close()

        # Ejecuta el asignador para intentar pasar leads a "Assigned"
        assigner.assign_leads()

    except Exception as e:
        logger.error(f"Error in simulation cycle {cycle_num}: {e}")


# --- Loop principal ---
def main():
    logger.info("Starting lead simulator (Ctrl+C to stop)...")

    cycle_num = 1
    stop_requested = False

    def handle_exit(sig, frame):
        nonlocal stop_requested
        logger.info("Stop signal received, shutting down gracefully...")
        stop_requested = True

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    while not stop_requested:
        logger.info(f"--- Cycle {cycle_num} ---")
        run_simulation_cycle(cycle_num)
        cycle_num += 1
        time.sleep(SIMULATION_INTERVAL)

    logger.info("Lead simulator stopped.")


if __name__ == "__main__":
    main()
