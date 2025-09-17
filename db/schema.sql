CREATE SCHEMA lead_management;

CREATE TABLE lead_management.audit_logs (
  audit_log_id SERIAL,
  table_name VARCHAR(25),
  action VARCHAR(10),
  old_value TEXT,
  new_value TEXT,
  changed_at TIMESTAMP,
  ip_address INET
);

CREATE TABLE lead_management.countries (
  country_id SERIAL,
  name VARCHAR(255),
  code VARCHAR(3)
);

CREATE TABLE lead_management.document_types (
  document_type_id SERIAL,
  name VARCHAR(100)
);

CREATE TABLE lead_management.business_lines (
  business_line_id SERIAL,
  name VARCHAR(100),
  description TEXT
);

CREATE TABLE lead_management.assignment_statuses (
  assignment_status_id SERIAL,
  name VARCHAR(100)
);

CREATE TABLE lead_management.leads (
  document_number VARCHAR(20),
  given_name VARCHAR(100),
  surname VARCHAR(100),
  phone VARCHAR(20),
  email VARCHAR(255),
  business_line_id INT,
  country_id INT,
  document_type_id INT
);


CREATE TABLE lead_management.sellers (
  document_number VARCHAR(20),
  given_name VARCHAR(100),
  surname VARCHAR(100),
  phone VARCHAR(20),
  email VARCHAR(255),
  max_leads_count INT,
  is_active BOOLEAN,
  business_line_id INT
);

CREATE TABLE lead_management.assignments (
  assignment_id SERIAL,
  assigned_at TIMESTAMP,
  seller_document_number VARCHAR(20),
  lead_document_number VARCHAR(20),
  assignment_status_id INT
);

CREATE TABLE lead_management.assignment_records (
  assignment_record_id SERIAL,
  assigned_at TIMESTAMP,
  seller_document_number VARCHAR(20),
  lead_document_number VARCHAR(20),
  assignment_status_id INT,
  updated_at TIMESTAMP,
  assignment_id INT
);

-- Primary keys
ALTER TABLE lead_management.audit_logs
  ADD CONSTRAINT pk_audit_log_id PRIMARY KEY (audit_log_id);

ALTER TABLE lead_management.countries
  ADD CONSTRAINT pk_country_id PRIMARY KEY (country_id);

ALTER TABLE lead_management.document_types
  ADD CONSTRAINT pk_document_type_id PRIMARY KEY (document_type_id);

ALTER TABLE lead_management.business_lines
  ADD CONSTRAINT pk_business_line_id PRIMARY KEY (business_line_id);

ALTER TABLE lead_management.assignment_statuses
  ADD CONSTRAINT pk_assignment_status_id PRIMARY KEY (assignment_status_id);

ALTER TABLE lead_management.leads
  ADD CONSTRAINT pk_document_number PRIMARY KEY (document_number);

ALTER TABLE lead_management.sellers
  ADD CONSTRAINT pk_seller_document_number PRIMARY KEY (document_number);

ALTER TABLE lead_management.assignments
  ADD CONSTRAINT pk_assignment_id PRIMARY KEY (assignment_id);

ALTER TABLE lead_management.assignment_records
  ADD CONSTRAINT pk_assignment_record_id PRIMARY KEY (assignment_record_id);

-- Not null
ALTER TABLE lead_management.audit_logs
  ADD CONSTRAINT nn_audit_log_table_name CHECK (table_name IS NOT NULL),
  ADD CONSTRAINT nn_audit_log_action CHECK (action IS NOT NULL),
  ADD CONSTRAINT nn_audit_log_old_value CHECK (old_value IS NOT NULL),
  ADD CONSTRAINT nn_audit_log_new_value CHECK (new_value IS NOT NULL),
  ADD CONSTRAINT nn_audit_log_changed_at CHECK (changed_at IS NOT NULL),
  ADD CONSTRAINT nn_audit_log_ip_address CHECK (ip_address IS NOT NULL);

ALTER TABLE lead_management.countries
  ADD CONSTRAINT nn_country_name CHECK (name IS NOT NULL),
  ADD CONSTRAINT nn_country_code CHECK (code IS NOT NULL);

ALTER TABLE lead_management.document_types
  ADD CONSTRAINT nn_document_type_name CHECK (name IS NOT NULL);

ALTER TABLE lead_management.business_lines
  ADD CONSTRAINT nn_business_line_name CHECK (name IS NOT NULL);

ALTER TABLE lead_management.leads
  ADD CONSTRAINT nn_lead_given_name CHECK (given_name IS NOT NULL),
  ADD CONSTRAINT nn_lead_surname CHECK (surname IS NOT NULL),
  ADD CONSTRAINT nn_lead_phone CHECK (phone IS NOT NULL),
  ADD CONSTRAINT nn_lead_email CHECK (email IS NOT NULL),
  ADD CONSTRAINT nn_lead_business_line_id CHECK (business_line_id IS NOT NULL),
  ADD CONSTRAINT nn_lead_country_id CHECK (country_id IS NOT NULL),
  ADD CONSTRAINT nn_lead_document_type_id CHECK (document_type_id IS NOT NULL);

ALTER TABLE lead_management.sellers
  ADD CONSTRAINT nn_seller_given_name CHECK (given_name IS NOT NULL),
  ADD CONSTRAINT nn_seller_surname CHECK (surname IS NOT NULL),
  ADD CONSTRAINT nn_seller_phone CHECK (phone IS NOT NULL),
  ADD CONSTRAINT nn_seller_email CHECK (email IS NOT NULL),
  ADD CONSTRAINT nn_seller_business_line_id CHECK (business_line_id IS NOT NULL);

ALTER TABLE lead_management.assignments
  ADD CONSTRAINT nn_assignment_assigned_at CHECK (assigned_at IS NOT NULL),
  ADD CONSTRAINT nn_assignment_lead_document_number CHECK (lead_document_number IS NOT NULL),
  ADD CONSTRAINT nn_assignment_status_id CHECK (assignment_status_id IS NOT NULL);

ALTER TABLE lead_management.assignment_records
  ADD CONSTRAINT nn_assignment_record_assigned_at CHECK (assigned_at IS NOT NULL),
  ADD CONSTRAINT nn_assignment_record_lead_document_number CHECK (lead_document_number IS NOT NULL),
  ADD CONSTRAINT nn_assignment_record_status_id CHECK (assignment_status_id IS NOT NULL),
  ADD CONSTRAINT nn_assignment_record_updated_at CHECK (updated_at IS NOT NULL),
  ADD CONSTRAINT nn_assignment_record_assignment_id CHECK (assignment_id IS NOT NULL);

-- Unique constraints
ALTER TABLE lead_management.countries
  ADD CONSTRAINT un_country_code UNIQUE (code);

ALTER TABLE lead_management.document_types
  ADD CONSTRAINT un_document_type_name UNIQUE (name);

ALTER TABLE lead_management.business_lines
  ADD CONSTRAINT un_business_line_name UNIQUE (name);

ALTER TABLE lead_management.leads
  ADD CONSTRAINT un_lead_email UNIQUE (email);

ALTER TABLE lead_management.sellers
  ADD CONSTRAINT un_seller_email UNIQUE (email);

ALTER TABLE lead_management.assignment_statuses
  ADD CONSTRAINT un_assignment_status_name UNIQUE (name);

-- Foreign keys
ALTER TABLE lead_management.leads
  ADD CONSTRAINT fk_business_line_id FOREIGN KEY (business_line_id) REFERENCES lead_management.business_lines(business_line_id),
  ADD CONSTRAINT fk_country_id FOREIGN KEY (country_id) REFERENCES lead_management.countries(country_id),
  ADD CONSTRAINT fk_document_type_id FOREIGN KEY (document_type_id) REFERENCES lead_management.document_types(document_type_id);

ALTER TABLE lead_management.sellers
  ADD CONSTRAINT fk_seller_business_line FOREIGN KEY (business_line_id) REFERENCES lead_management.business_lines(business_line_id);

ALTER TABLE lead_management.assignments
  ADD CONSTRAINT fk_seller_document_number FOREIGN KEY (seller_document_number) REFERENCES lead_management.sellers(document_number),
  ADD CONSTRAINT fk_lead_document_number FOREIGN KEY (lead_document_number) REFERENCES lead_management.leads(document_number),
  ADD CONSTRAINT fk_assignment_status_id FOREIGN KEY (assignment_status_id) REFERENCES lead_management.assignment_statuses(assignment_status_id);

ALTER TABLE lead_management.assignment_records
  ADD CONSTRAINT fk_assignment_id FOREIGN KEY (assignment_id) REFERENCES lead_management.assignments(assignment_id);

-- Defaults
ALTER TABLE lead_management.sellers
  ALTER COLUMN max_leads_count SET DEFAULT 10,
  ALTER COLUMN is_active SET DEFAULT TRUE;

-- Functions
CREATE OR REPLACE FUNCTION lead_management.fn_audit_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_old TEXT;
    v_new TEXT;
    v_ip  INET;
BEGIN
    SELECT inet_client_addr() INTO v_ip;

    IF (TG_OP = 'DELETE') THEN
        v_old := row_to_json(OLD)::text;
        v_new := 'DELETE';
        INSERT INTO lead_management.audit_logs(table_name, action, old_value, new_value, changed_at, ip_address)
        VALUES (TG_TABLE_NAME, TG_OP, v_old, v_new, NOW(), v_ip);
        RETURN OLD;

    ELSIF (TG_OP = 'INSERT') THEN
        v_old := 'INSERT';
        v_new := row_to_json(NEW)::text;
        INSERT INTO lead_management.audit_logs(table_name, action, old_value, new_value, changed_at, ip_address)
        VALUES (TG_TABLE_NAME, TG_OP, v_old, v_new, NOW(), v_ip);
        RETURN NEW;

    ELSIF (TG_OP = 'UPDATE') THEN
        v_old := row_to_json(OLD)::text;
        v_new := row_to_json(NEW)::text;
        INSERT INTO lead_management.audit_logs(table_name, action, old_value, new_value, changed_at, ip_address)
        VALUES (TG_TABLE_NAME, TG_OP, v_old, v_new, NOW(), v_ip);
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Función para poblar assignment_records
CREATE OR REPLACE FUNCTION lead_management.fn_assignment_history()
RETURNS TRIGGER AS $$
BEGIN
    -- Cuando se inserta un assignment, registramos el estado inicial
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO lead_management.assignment_records(
            assigned_at,
            seller_document_number,
            lead_document_number,
            assignment_status_id,
            updated_at,
            assignment_id
        )
        VALUES (
            NEW.assigned_at,
            NEW.seller_document_number,
            NEW.lead_document_number,
            NEW.assignment_status_id,
            NOW(),
            NEW.assignment_id
        );
        RETURN NEW;
    END IF;

    -- Cuando se actualiza un assignment, guardamos la versión anterior
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO lead_management.assignment_records(
            assigned_at,
            seller_document_number,
            lead_document_number,
            assignment_status_id,
            updated_at,
            assignment_id
        )
        VALUES (
            OLD.assigned_at,
            OLD.seller_document_number,
            OLD.lead_document_number,
            OLD.assignment_status_id,
            NOW(),
            OLD.assignment_id
        );
        INSERT INTO lead_management.assignment_records(
            assigned_at,
            seller_document_number,
            lead_document_number,
            assignment_status_id,
            updated_at,
            assignment_id
        )
        VALUES (
            NEW.assigned_at,
            NEW.seller_document_number,
            NEW.lead_document_number,
            NEW.assignment_status_id,
            NOW(),
            NEW.assignment_id
        );
        RETURN NEW;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Triggers
CREATE TRIGGER trg_audit_countries
  AFTER INSERT OR UPDATE OR DELETE ON lead_management.countries
  FOR EACH ROW EXECUTE FUNCTION lead_management.fn_audit_trigger();

CREATE TRIGGER trg_audit_document_types
  AFTER INSERT OR UPDATE OR DELETE ON lead_management.document_types
  FOR EACH ROW EXECUTE FUNCTION lead_management.fn_audit_trigger();

CREATE TRIGGER trg_audit_business_lines
  AFTER INSERT OR UPDATE OR DELETE ON lead_management.business_lines
  FOR EACH ROW EXECUTE FUNCTION lead_management.fn_audit_trigger();

CREATE TRIGGER trg_audit_assignment_statuses
  AFTER INSERT OR UPDATE OR DELETE ON lead_management.assignment_statuses
  FOR EACH ROW EXECUTE FUNCTION lead_management.fn_audit_trigger();

CREATE TRIGGER trg_audit_leads
  AFTER INSERT OR UPDATE OR DELETE ON lead_management.leads
  FOR EACH ROW EXECUTE FUNCTION lead_management.fn_audit_trigger();

CREATE TRIGGER trg_audit_sellers
  AFTER INSERT OR UPDATE OR DELETE ON lead_management.sellers
  FOR EACH ROW EXECUTE FUNCTION lead_management.fn_audit_trigger();

CREATE TRIGGER trg_audit_assignments
  AFTER INSERT OR UPDATE OR DELETE ON lead_management.assignments
  FOR EACH ROW EXECUTE FUNCTION lead_management.fn_audit_trigger();

CREATE TRIGGER trg_audit_assignment_records
  AFTER INSERT OR UPDATE OR DELETE ON lead_management.assignment_records
  FOR EACH ROW EXECUTE FUNCTION lead_management.fn_audit_trigger();

CREATE TRIGGER trg_assignment_history
  AFTER INSERT OR UPDATE ON lead_management.assignments
  FOR EACH ROW
  EXECUTE FUNCTION lead_management.fn_assignment_history();

