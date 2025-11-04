-- Add new columns to soc_inventory table
ALTER TABLE soc_inventory
ADD COLUMN location_3 VARCHAR(100),
ADD COLUMN specification1 VARCHAR(100),
ADD COLUMN specification2 VARCHAR(100),
ADD COLUMN specification3 VARCHAR(100),
ADD COLUMN project_code VARCHAR(50),
ADD COLUMN department VARCHAR(50);