import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import DictCursor
import os
from datetime import datetime
import logging

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

def fetch_pending_leads(cursor):
    """Fetches leads that have not been assigned yet."""
    cursor.execute("""
        SELECT l.document_number, l.business_line_id
        FROM lead_management.leads l
        LEFT JOIN lead_management.assignments a
        ON l.document_number = a.lead_document_number
        WHERE a.lead_document_number IS NULL
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

def is_lead_assignable(lead, seller):
    """Checks if a lead can be assigned to a specific seller."""
    if lead["business_line_id"] != seller["business_line_id"]:
        return False
    if seller["current_leads"] >= seller["max_leads_count"]:
        return False
    return True

def get_status_id(cursor, status_name="Assigned"):
    """Fetches the assignment_status_id for a given status name.
    If not found, inserts it and returns the new id.
    """
    clean_name = status_name.strip()    # remove leading/trailing spaces

    # Try to fetch existing status (case-insensitive)
    cursor.execute("""
        SELECT assignment_status_id
        FROM lead_management.assignment_statuses
        WHERE LOWER(name) = LOWER(%s)
    """, (clean_name,))
    row = cursor.fetchone()

    if row:
        return row['assignment_status_id']

    # If not found, insert it
    cursor.execute("""
        INSERT INTO lead_management.assignment_statuses (name)
        VALUES (%s)
        RETURNING assignment_status_id
    """, (clean_name,))
    new_row = cursor.fetchone()
    logger.info(f"Inserted new assignment status '{clean_name}' with id {new_row['assignment_status_id']}.")
    return new_row['assignment_status_id']

def assign_leads_to_sellers(cursor, leads, sellers):
    """Generates the list of assignments to insert, applying validations."""
    assignments = []
    status_id = get_status_id(cursor, "Assigned")  # fetch once
    for lead in leads:
        eligible = [seller for seller in sellers if is_lead_assignable(lead, seller)]
        if eligible:
            seller = eligible[0]  # assign to the first available seller
            assignments.append((
                datetime.now(),
                seller['document_number'],
                lead['document_number'],
                status_id
            ))
            seller['current_leads'] += 1
            logger.info(f"Assigned lead {lead['document_number']} to seller {seller['document_number']}.")
    return assignments

def insert_assignments(cursor, assignments):
    """Inserts assignments into the database."""
    if assignments:
        cursor.executemany("""
            INSERT INTO lead_management.assignments
            (assigned_at, seller_document_number, lead_document_number, assignment_status_id)
            VALUES (%s, %s, %s, %s)
        """, assignments)
        logger.info(f"Inserted {len(assignments)} assignments into the database.")

def assign_leads():
    """Main function: fetches leads and sellers, performs assignment."""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        leads = fetch_pending_leads(cursor)
        if not leads:
            logger.info("No pending leads.")
            return

        sellers = fetch_eligible_sellers(cursor)
        if not sellers:
            logger.info("No eligible sellers.")
            return

        assignments = assign_leads_to_sellers(cursor, leads, sellers)
        insert_assignments(cursor, assignments)
        conn.commit()
        logger.info(f"{len(assignments)} leads have been assigned successfully.")

    except Exception as e:
        logger.error(f"Error assigning leads: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    assign_leads()
