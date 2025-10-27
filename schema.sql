-- Drop existing table if present and create new schema matching the
-- updated structure where `cp_number` is the unique identifier.
DROP TABLE IF EXISTS soc_inventory CASCADE;

CREATE TABLE soc_inventory (
    date DATE,
    cp_number VARCHAR(50) NOT NULL,
    project_code VARCHAR(50),
    sort_code VARCHAR(50),
    department VARCHAR(100),
    lt1 VARCHAR(50),
    lt2 VARCHAR(50),
    user_name VARCHAR(100),
    port VARCHAR(50),
    item VARCHAR(100),
    usb_permission VARCHAR(50),
    os VARCHAR(100),
    mac VARCHAR(50),
    ip VARCHAR(50),
    status VARCHAR(50),
    cpu VARCHAR(100),
    ram VARCHAR(50),
    hd VARCHAR(50),
    soft1 VARCHAR(100),
    soft2 VARCHAR(100),
    soft3 VARCHAR(100),
    unlabeled VARCHAR(50),
    to_be_confirm VARCHAR(50),
    company_code VARCHAR(50),
    description_cpu VARCHAR(100),
    description_hdd_gb VARCHAR(50),
    description_ram_mb VARCHAR(50),
    amount NUMERIC(12,2),
    prn_no VARCHAR(50),
    invoice_date DATE,
    supplier_name VARCHAR(100),
    remark TEXT,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_soc_cp_number UNIQUE (cp_number)
);

-- Create function & trigger to keep last_updated in sync on UPDATE
CREATE OR REPLACE FUNCTION trg_update_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_soc_inventory_update_last_updated
    BEFORE UPDATE ON soc_inventory
    FOR EACH ROW
    EXECUTE FUNCTION trg_update_last_updated();

-- Helpful index on cp_number for lookups (unique constraint already creates an index)
CREATE INDEX IF NOT EXISTS idx_soc_inventory_cp_number ON soc_inventory (cp_number);

-- Optional: create a small view showing last update summary
CREATE OR REPLACE VIEW vw_soc_inventory_last_update AS
SELECT cp_number, last_updated
FROM soc_inventory;
