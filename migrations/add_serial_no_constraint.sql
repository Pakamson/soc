-- First ensure we have a migrations folder
ALTER TABLE soc_inventory ADD CONSTRAINT soc_inventory_serial_no_key UNIQUE (serial_no);