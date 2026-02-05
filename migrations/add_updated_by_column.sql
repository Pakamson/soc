-- Add updated_by column to track which user made changes
ALTER TABLE soc_inventory
ADD COLUMN IF NOT EXISTS updated_by VARCHAR(100);

-- Add comment to document the column
COMMENT ON COLUMN soc_inventory.updated_by IS 'Username of the user who last updated this record';
