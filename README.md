# Lead Assignment System

This project implements a **lead management and assignment system** with:
- A normalized PostgreSQL schema.
- Audit logging for compliance and traceability.
- An automated simulator that generates leads periodically.
- An assigner that distributes leads to sellers based on business rules.

---

## Assumptions

- Each **lead** belongs to exactly **one business line** and **one country**.
- Each **seller** only works in **one business line**.
- Sellers have a **maximum number of leads** they can handle simultaneously.
- Audit logs must capture **every insert, update, and delete**.
- Leads are unique by their **document number**.
- Simulation runs **continuously** until manually stopped.

---

## Setup

### 1. Create a `.env`
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=lead_management
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword

# Simulation config
SIMULATION_INTERVAL=10   # seconds between cycles
LEADS_MIN=1
LEADS_MAX=5
```

---

### 2. Start PostgreSQL with Docker Compose
```bash
docker compose up -d
```

---

### 3. Start the simulator
```bash
python simulator.py
```
or
```bash
python3 simulator.py
```

---

### 4. Stop the simulator
```bash
CTRL + C
```
or
```bash
python3 simulator.py
```

---

# Part 1 — Data Architecture

The schema was designed to ensure **data consistency, traceability, and realistic lead assignment management**.  
It follows a normalized structure that separates concerns (**entities, relationships, and history**) and enforces integrity through primary/foreign keys and constraints.

---

## Entity-Relation
<img width="1046" height="662" alt="lead-assigner-er" src="https://github.com/user-attachments/assets/e16b531b-00a3-44be-8eba-c8d0b658131d" />

---

## 📌 General Modeling Justification

### 🔹 Auditability (`audit_logs`)
Every change must be traceable for compliance and debugging.  
Database triggers ensure that inserts, updates, and deletes are logged with metadata such as timestamps and IP address.

### 🔹 Reference Data (`countries`, `document_types`, `business_lines`, `assignment_statuses`)
These tables provide controlled vocabularies to avoid free-text inconsistencies and ensure realistic relationships between entities.  
For example, a lead must belong to a valid country and business line.

### 🔹 Actors (`leads`, `sellers`)
These are the **core entities** of the system.  
- Leads represent potential clients.  
- Sellers are responsible for managing them.  
Both are linked to business lines, ensuring logical and valid assignments.

### 🔹 Assignments (`assignments`, `assignment_records`)
- `assignments` represent the **current relationship** between a lead and a seller.  
- `assignment_records` capture the **historical changes**, providing full traceability over time.

---

## 📌 Column-level Justification

### `audit_logs`
- **table_name, action** → identify what was modified and the type of operation.  
- **old_value, new_value** → store row snapshots as JSON for before/after states.  
- **changed_at, ip_address** → provide accountability of when and from where changes occurred.  

### `countries`
- **name** → human-readable country name.  
- **code** → short ISO-like code for uniqueness and easy referencing.  

### `document_types`
- **name** → defines valid document categories (e.g., Passport, ID Card, Driver License).  

### `business_lines`
- **name** → short identifier of the business line.  
- **description** → provides context for operators and allows future scaling.  

### `assignment_statuses`
- **name** → controlled status values (e.g., Pending, Assigned, In Progress).  

### `leads`
- **document_number** → unique identifier per lead (national ID, passport, etc.).  
- **given_name, surname** → personal identification.  
- **phone, email** → contact information for follow-ups.  
- **business_line_id, country_id, document_type_id** → foreign keys ensuring coherent attributes and valid references.  

### `sellers`
- **document_number** → unique seller identifier.  
- **given_name, surname, phone, email** → identification and contact information.  
- **max_leads_count** → workload management (how many leads a seller can handle).  
- **is_active** → allows temporary deactivation instead of permanent deletion.  
- **business_line_id** → ensures sellers only receive leads from their business line.  

### `assignments`
- **assignment_id** → primary key for unique assignment tracking.  
- **assigned_at** → timestamp of when the lead was assigned.  
- **seller_document_number, lead_document_number** → establish the relationship between seller and lead.  
- **assignment_status_id** → current state of the assignment.  

### `assignment_records`
- **assignment_record_id** → unique key for versioned history.  
- **assigned_at** → when the assignment was created.  
- **seller_document_number, lead_document_number** → reference the actors.  
- **assignment_status_id** → state at the time of recording.  
- **updated_at** → when this version was logged.  
- **assignment_id** → foreign key linking to the parent assignment.  

---

# Part 2 — Assignment Logic

The lead assignment logic is implemented in **`assigner.py`**, which ensures that all leads are traceable and assigned to eligible sellers according to realistic business constraints.  
It provides a clear separation between **database access**, **helper utilities**, and the **core assignment process**.

---

## 📌 General Logic Justification

- **Traceability** → Logging is applied at each critical step (lead insertion, assignment, error handling).  
- **Consistency** → Every lead always has a corresponding record in `assignments` (default: `Pending`).  
- **Realism** → Sellers cannot exceed their workload capacity (`max_leads_count`) and can only receive leads from their own business line.  
- **Resilience** → Exceptions are caught and logged; transactions are committed step by step to avoid partial inconsistencies.  

---

## 📌 Code Structure

### 🔹 Logging Setup
- Logs are written both to a **file** (`logs/lead_assigner.log`) and **console output**.  
- Provides timestamped, leveled logs for **debugging and auditing**.  

### 🔹 Database Configuration
- Reads connection parameters (`host`, `port`, `database`, `user`, `password`) from environment variables.  
- `get_connection()` returns a **new PostgreSQL connection**, ensuring fresh sessions for each execution.

---

## 📌 Assignment Helpers

### `get_status_id(cursor, status_name)`
- Ensures the requested status (e.g., `Pending`, `Assigned`) exists in `assignment_statuses`.  
- If not found, it creates it dynamically.  
- Guarantees that **statuses are controlled** and no free-text values are used.  

### `ensure_pending_assignments(cursor)`
- Ensures every lead has an entry in `assignments`.  
- If missing, inserts a record with:  
  - `status = Pending`  
  - `seller_document_number = NULL`  
- Guarantees that **new leads are always ready for assignment**.  

---

## 📌 Fetchers

### `fetch_pending_leads(cursor)`
- Retrieves leads linked to assignments with status **`Pending`**.  
- Ordered consistently for deterministic assignment cycles.  
- Ensures the system only processes **unassigned leads**.  

### `fetch_eligible_sellers(cursor)`
- Retrieves active sellers along with:  
  - Their **business line**  
  - Their **maximum workload capacity**  
  - Their **current number of active assignments** (`Assigned` or `In Progress`)  
- Ensures that **only eligible sellers** (active and under capacity) are considered.  

---

## 📌 Assignment Logic

### `is_lead_assignable(lead, seller)`
- Restriction 1: Seller must belong to the **same business line** as the lead.  
- Restriction 2: Seller must not exceed **`max_leads_count`**.  
- Returns `True` only if both conditions are satisfied.  

### `assign_leads_to_sellers(cursor, leads, sellers)`
- Iterates through pending leads.  
- For each lead, finds the **first eligible seller** (greedy approach).  
- Updates the assignment:  
  - `seller_document_number`  
  - `assignment_status_id = Assigned`  
  - `assigned_at = NOW()`  
- Increments seller’s workload counter.  
- Logs each assignment for **traceability**.  

---

## 📌 Main Process

### `assign_leads()`
1. **Step 1 — Ensure pending assignments**  
   - Calls `ensure_pending_assignments()` so that no lead is left untracked.  

2. **Step 2 — Fetch pending leads**  
   - Retrieves all leads waiting for assignment.  

3. **Step 3 — Fetch eligible sellers**  
   - Loads sellers with available capacity.  

4. **Step 4 — Perform assignment**  
   - Calls `assign_leads_to_sellers()` to update records.  
   - Commits changes to the database.  

5. **Step 5 — Logging and cleanup**  
   - Logs how many leads were assigned.  
   - Ensures cursor/connection are properly closed.  

---

## 📌 Business Restrictions Enforced

- A lead **cannot exist without an assignment** → always at least `Pending`.  
- A lead **can only be assigned** to a seller in the same business line.  
- A seller **cannot exceed their workload** (`max_leads_count`).  
- Sellers marked as **inactive** are excluded automatically.  
- Assignment status transitions are **explicitly controlled** (e.g., Pending → Assigned).  

---

✅ This implementation ensures:  
- **Scalability** — More assignment rules can be added without breaking the structure.  
- **Auditability** — Logs and controlled statuses guarantee traceability.  
- **Reliability** — Database transactions ensure no inconsistent state is left behind.  

# Part 3 — Simulation & Automation

The **lead simulator** is implemented in `simulator.py`.  
Its goal is to **generate realistic leads periodically** and trigger the assignment process automatically.  
It provides a controlled environment for testing the system under different workloads, while respecting database constraints.

---

## 📌 General Logic Justification

- **Realism** → Leads are generated with random but coherent attributes (valid business line, country, document type).  
- **Automation** → Cycles run at fixed intervals (`SIMULATION_INTERVAL`) until manually stopped.  
- **Scalability** → The number of leads per cycle is determined by a probability distribution, simulating unpredictable workloads.  
- **Integration** → After inserting leads, the simulator directly calls `assigner.assign_leads()` to ensure the pipeline is end-to-end.  
- **Resilience** → Errors are caught and logged without crashing the loop.  

---

## 📌 Code Structure

### 🔹 Configuration
- Loads environment variables (`.env`) to keep parameters flexible:
  - **Database connection** → `POSTGRES_HOST`, `POSTGRES_PORT`, etc.  
  - **Simulation parameters** → `SIMULATION_INTERVAL`, `LEADS_MIN`, `LEADS_MAX`.  
- Enables quick reconfiguration without modifying the code.  

### 🔹 Database Connection
- `get_connection()` returns a fresh PostgreSQL connection for each cycle.  
- Ensures **transactional safety** and avoids dangling connections.  

---

## 📌 Helpers

### `pick_random_id(cursor, table, id_col)`
- Retrieves a **random valid foreign key** from the reference table.  
- Ensures that generated leads always respect **referential integrity**.  

### `generate_fake_lead(cursor, i)`
- Generates realistic attributes:  
  - **document_number** → unique numeric identifier.  
  - **given_name, surname** → chosen from predefined sets.  
  - **phone, email** → valid formats with random suffixes.  
  - **business_line_id, country_id, document_type_id** → selected from existing reference tables.  
- Ensures **data consistency** and prevents invalid inserts.  

### `insert_lead(cursor, lead)`
- Inserts a new lead into `leads`.  
- Uses `ON CONFLICT (document_number) DO NOTHING` to avoid duplicates.  
- Logs whether the lead was **inserted** or **skipped**.  

---

## 📌 Simulation Cycle

### `run_simulation_cycle(cycle_num)`
1. **Select number of leads**  
   - Chooses how many leads to generate based on weighted probabilities:  
     - 1 lead (25%), 2 leads (20%), 3 leads (10%), 4 leads (20%), 5 leads (25%).  
   - Adapts to configured `LEADS_MIN` and `LEADS_MAX`.  

2. **Generate leads**  
   - Calls `generate_fake_lead()` and `insert_lead()` for each lead.  
   - Commits the transaction after all inserts.  

3. **Trigger assignment**  
   - Calls `assigner.assign_leads()` to immediately distribute new leads.  

4. **Error handling**  
   - Exceptions are logged with cycle information to aid debugging.  

---

## 📌 Main Loop

### `main()`
- Starts the simulator with a **cycle counter**.  
- Runs indefinitely until stopped with **Ctrl+C** or a termination signal.  
- Between cycles:  
  - Logs cycle number.  
  - Runs `run_simulation_cycle()`.  
  - Sleeps for `SIMULATION_INTERVAL` seconds.  

- Graceful shutdown is supported:  
  - Intercepts `SIGINT` and `SIGTERM`.  
  - Stops the loop safely and logs the shutdown.  

---

## 📌 Business Restrictions Enforced

- Leads always reference valid **business lines, countries, and document types**.  
- Duplicate leads (by `document_number`) are **skipped automatically**.  
- Each cycle inserts a **random number of leads**, simulating real demand variability.  
- Assignments are performed immediately after insertion, ensuring the system is always up-to-date.  
- Simulator never leaves the database in a **half-committed state** due to explicit commits.  

---

✅ This simulation ensures:  
- **Controlled testing** under variable workloads.  
- **Reliable automation** of the lead lifecycle (insert → assign).  
- **Traceability** through logs for every cycle and operation.  
- **Consistency** by respecting all schema constraints and assignment logic.  
