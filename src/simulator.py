import os
import time
import signal
import random
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import assigner
from assigner import logger

# --- Load configuration from .env ---
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": os.getenv("POSTGRES_PORT"),
    "database": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}

# Simulation parameters
SIMULATION_INTERVAL = int(os.getenv("SIMULATION_INTERVAL", 30))
LEADS_MIN = int(os.getenv("LEADS_MIN", 1))
LEADS_MAX = int(os.getenv("LEADS_MAX", 5))

# --- Database connection ---
def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- Helpers ---
def pick_random_id(cursor, table, id_col):
    cursor.execute(f"SELECT {id_col} FROM lead_management.{table} ORDER BY RANDOM() LIMIT 1")
    return cursor.fetchone()[0]

def generate_fake_lead(cursor, i):
    """Generate a lead with valid foreign key references."""
    business_line_id = pick_random_id(cursor, "business_lines", "business_line_id")
    country_id = pick_random_id(cursor, "countries", "country_id")
    document_type_id = pick_random_id(cursor, "document_types", "document_type_id")

    doc_num = str(random.randint(100000000, 9999999999))
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

def insert_lead(cursor, lead):
    """Insert a lead without creating an assignment."""
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
    if row:
        logger.info(f"Lead {row[0]} inserted.")
    else:
        logger.warning(f"Lead {lead[0]} already exists, skipping.")

def run_simulation_cycle(cycle_num):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        lead_range = list(range(LEADS_MIN, LEADS_MAX + 1))

        default_weights = {
            1: 0.25,
            2: 0.20,
            3: 0.10,
            4: 0.20,
            5: 0.25
        }

        # Adapt distribution to the configured range
        weights = [default_weights.get(n, 0.01) for n in lead_range]
        total = sum(weights)
        weights = [w / total for w in weights]

        n_leads = random.choices(lead_range, weights=weights)[0]

        logger.info(f"Generating {n_leads} leads in cycle {cycle_num}.")

        for i in range(n_leads):
            lead = generate_fake_lead(cursor, f"{cycle_num}_{i}")
            insert_lead(cursor, lead)

        conn.commit()
        cursor.close()
        conn.close()

        # Call assigner to handle assignments
        assigner.assign_leads()

    except Exception as e:
        logger.error(f"Error in simulation cycle {cycle_num}: {e}")

# --- Main loop ---
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
