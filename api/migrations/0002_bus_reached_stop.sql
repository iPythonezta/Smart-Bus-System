-- Migration: Add reached_stop_sequence to track which stops a bus has actually reached
-- This separates the concept of "reached" (bus was at the stop) from "heading to" (current_stop_sequence)

ALTER TABLE bus_locations ADD COLUMN reached_stop_sequence INT DEFAULT NULL AFTER current_stop_sequence;

-- Initially, set reached_stop_sequence = current_stop_sequence for existing data
UPDATE bus_locations SET reached_stop_sequence = current_stop_sequence WHERE current_stop_sequence IS NOT NULL;
