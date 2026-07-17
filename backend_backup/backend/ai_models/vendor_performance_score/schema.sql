-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS rocks;
USE rocks;

-- Create the vendor table
CREATE TABLE IF NOT EXISTS vendor (
    vendor_id VARCHAR(255) PRIMARY KEY,
    vendor_name VARCHAR(255),
    performance_score DECIMAL(5,2) DEFAULT 0.00,
    total_reviews INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Additional metadata fields you might find useful
    marketplace VARCHAR(10),
    contact_email VARCHAR(255)
);

-- Example insert (if you need dummy vendors to test updating)
-- INSERT INTO vendor (vendor_id, vendor_name, marketplace) VALUES ('V123', 'Sample Vendor LLC', 'US');
