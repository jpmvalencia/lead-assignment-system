import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import DictCursor
import os
from datetime import datetime
import logging

# --- Logging setup ---
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "lead_assigner.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- DB Config ---
load_dotenv()
DB_CONFIG = {
    "host": os.getenv('POSTGRES_HOST'),
    "port": os.getenv('POSTGRES_PORT'),
    "database": os.getenv('POSTGRES_DB'),
    "user": os.getenv('POSTGRES_USER'),
    "password": os.getenv('POSTGRES_PASSWORD')
}

def get_connection():
    """Returns a new database connection."""
    return psycopg2.connect(**DB_CONFIG)

# --- Assignment helpers ---
def get_status_id(cursor, status_name):
    """Fetches the assignment_status_id for a given status name.
    If not found, inserts it and returns the new id.
    """
    clean_name = status_name.strip()
    cursor.execute("""
        SELECT assignment_status_id
        FROM lead_management.assignment_statuses
        WHERE LOWER(name) = LOWER(%s)
    """, (clean_name,))
    row = cursor.fetchone()

    if row:
        return row['assignment_status_id']

    cursor.execute("""
        INSERT INTO lead_management.assignment_statuses (name)
        VALUES (%s)
        RETURNING assignment_status_id
    """, (clean_name,))
    new_row = cursor.fetchone()
    logger.info(f"Inserted new assignment status '{clean_name}' with id {new_row['assignment_status_id']}.")
    return new_row['assignment_status_id']

def ensure_pending_assignments(cursor):
    """
    Asegura que todos los leads tengan un registro en assignments.
    Si no existe, inserta un registro con estado 'Pending' y sin seller asignado.
    """
    pending_id = get_status_id(cursor, "Pending")

    cursor.execute("""
        SELECT l.document_number
        FROM lead_management.leads l
        LEFT JOIN lead_management.assignments a
          ON l.document_number = a.lead_document_number
        WHERE a.lead_document_number IS NULL
    """)
    new_leads = cursor.fetchall()

    if new_leads:
        to_insert = [
            (datetime.now(), None, lead['document_number'], pending_id)
            for lead in new_leads
        ]
        cursor.executemany("""
            INSERT INTO lead_management.assignments
            (assigned_at, seller_document_number, lead_document_number, assignment_status_id)
            VALUES (%s, %s, %s, %s)
        """, to_insert)
        logger.info(f"Inserted {len(to_insert)} new leads into assignments as Pending.")

# --- Fetchers ---
def fetch_pending_leads(cursor):
    """Fetches leads that are in Pending status."""
    cursor.execute("""
        SELECT l.document_number, l.business_line_id
        FROM lead_management.leads l
        JOIN lead_management.assignments a
          ON l.document_number = a.lead_document_number
        JOIN lead_management.assignment_statuses st
          ON a.assignment_status_id = st.assignment_status_id
        WHERE LOWER(st.name) = 'pending'
        ORDER BY l.document_number
    """)
    leads = cursor.fetchall()
    logger.info(f"Fetched {len(leads)} pending leads.")
    return leads

def fetch_eligible_sellers(cursor):
    """Fetches active sellers with their current number of assigned leads."""
    cursor.execute("""
        SELECT
            s.document_number,
            s.business_line_id,
            s.max_leads_count,
            COALESCE((
                SELECT COUNT(*)
                FROM lead_management.assignments a
                JOIN lead_management.assignment_statuses st
                    ON a.assignment_status_id = st.assignment_status_id
                WHERE a.seller_document_number = s.document_number
                  AND st.name IN ('Assigned', 'In Progress')
            ), 0) AS current_leads
        FROM lead_management.sellers s
        WHERE s.is_active = TRUE
    """)
    sellers = cursor.fetchall()
    logger.info(f"Fetched {len(sellers)} eligible sellers.")
    return sellers

# --- Assignment logic ---
def is_lead_assignable(lead, seller):
    """Checks if a lead can be assigned to a specific seller."""
    if lead["business_line_id"] != seller["business_line_id"]:
        return False
    if seller["current_leads"] >= seller["max_leads_count"]:
        return False
    return True

def assign_leads_to_sellers(cursor, leads, sellers):
    """Assigns pending leads to sellers (updates existing assignments)."""
    assigned_count = 0
    assigned_id = get_status_id(cursor, "Assigned")

    for lead in leads:
        eligible = [s for s in sellers if is_lead_assignable(lead, s)]
        if eligible:
            seller = eligible[0]
            cursor.execute("""
                UPDATE lead_management.assignments
                SET seller_document_number = %s,
                    assignment_status_id = %s,
                    assigned_at = %s
                WHERE lead_document_number = %s
            """, (
                seller['document_number'],
                assigned_id,
                datetime.now(),
                lead['document_number']
            ))
            seller['current_leads'] += 1
            assigned_count += 1
            logger.info(f"Assigned lead {lead['document_number']} to seller {seller['document_number']}.")

    return assigned_count

# --- Main ---
def assign_leads():
    """Main function: fetches leads and sellers, performs assignment."""
    assigned_count = 0
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        # Paso 1: asegurar que todo lead tiene assignment
        ensure_pending_assignments(cursor)
        conn.commit()

        # Paso 2: traer leads pendientes
        leads = fetch_pending_leads(cursor)
        if not leads:
            logger.info("No pending leads.")
            return assigned_count

        # Paso 3: traer vendedores
        sellers = fetch_eligible_sellers(cursor)
        if not sellers:
            logger.info("No eligible sellers.")
            return assigned_count

        # Paso 4: asignar leads
        assigned_count = assign_leads_to_sellers(cursor, leads, sellers)
        conn.commit()

        logger.info(f"{assigned_count} leads have been assigned successfully.")

    except Exception as e:
        logger.error(f"Error assigning leads: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return assigned_count

if __name__ == "__main__":
    assign_leads()
