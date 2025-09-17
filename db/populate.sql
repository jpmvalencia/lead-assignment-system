-- Countries
INSERT INTO lead_management.countries (name, code)
VALUES
  ('United States', 'US'),
  ('Canada', 'CA'),
  ('Mexico', 'MX'),
  ('Colombia', 'CO'),
  ('Brazil', 'BR');

-- Document types
INSERT INTO lead_management.document_types (name)
VALUES
  ('Passport'),
  ('Driver License'),
  ('ID Card'),
  ('Tax ID');

-- Business lines
INSERT INTO lead_management.business_lines (name, description)
VALUES
  ('Sales', 'Sales department for managing customer relations'),
  ('Marketing', 'Marketing department for managing campaigns'),
  ('Support', 'Customer support department'),
  ('Operations', 'Operations and logistics department');

-- Assignment statuses
INSERT INTO lead_management.assignment_statuses (name)
VALUES
  ('Pending'),
  ('Assigned'),
  ('In Progress');

-- Sellers (seed a few so assignments can be tested)
INSERT INTO lead_management.sellers (
    document_number, given_name, surname, phone, email,
    max_leads_count, is_active, business_line_id
)
VALUES
  ('1001', 'Alice', 'Brown', '+57 3011111111', 'alice.brown@example.com', 50, TRUE, 1),
  ('1002', 'Bob', 'Davis', '+57 3022222222', 'bob.davis@example.com', 30, TRUE, 2),
  ('1003', 'Charlie', 'Evans', '+57 3033333333', 'charlie.evans@example.com', 40, TRUE, 3),
  ('1004', 'Diana', 'Lopez', '+57 3044444444', 'diana.lopez@example.com', 25, TRUE, 1);
