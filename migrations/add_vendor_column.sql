-- Add vendor column to soc_inventory table
ALTER TABLE soc_inventory
ADD COLUMN vendor VARCHAR(100);
