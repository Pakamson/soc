-- Add created_at and updated_at timestamp columns to soc_inventory table
ALTER TABLE soc_inventory
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Create a function to automatically update the updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create a trigger to call the function before any UPDATE on soc_inventory
DROP TRIGGER IF EXISTS update_soc_inventory_updated_at ON soc_inventory;
CREATE TRIGGER update_soc_inventory_updated_at
    BEFORE UPDATE ON soc_inventory
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
