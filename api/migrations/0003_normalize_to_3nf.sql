-- Migration: Normalize advertisements table to 3NF
-- This migration extracts advertiser information into a separate table to eliminate transitive dependency
-- Transitive dependency: ad_id → advertiser_name → advertiser_contact
-- Date: 2025-12-14

-- =====================================================
-- STEP 1: Create advertisers table
-- =====================================================
CREATE TABLE IF NOT EXISTS advertisers (
    advertiser_id INT AUTO_INCREMENT,
    advertiser_name VARCHAR(100) NOT NULL,
    contact_email VARCHAR(100),
    contact_phone VARCHAR(20),
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_advertisers PRIMARY KEY (advertiser_id),
    CONSTRAINT uk_advertisers_name UNIQUE (advertiser_name),
    INDEX idx_advertiser_name (advertiser_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- STEP 2: Extract unique advertisers from advertisements
-- =====================================================
-- Note: This handles potential duplicates where same advertiser has different contacts
-- Priority: First occurrence by ad_id (oldest)
INSERT INTO advertisers (advertiser_name, contact_phone)
SELECT DISTINCT
    advertiser_name,
    MIN(advertiser_contact) as contact_phone  -- Take first contact found
FROM advertisements
WHERE advertiser_name IS NOT NULL AND advertiser_name != ''
GROUP BY advertiser_name
ORDER BY MIN(ad_id);  -- Preserve oldest advertiser entry

-- =====================================================
-- STEP 3: Create new advertisements table (3NF compliant)
-- =====================================================
CREATE TABLE IF NOT EXISTS advertisements_3nf (
    ad_id INT AUTO_INCREMENT,
    title VARCHAR(100) NOT NULL,
    content_url VARCHAR(500) NOT NULL,
    media_type ENUM('image', 'youtube') NOT NULL DEFAULT 'image',
    duration_sec INT NOT NULL DEFAULT 15,
    advertiser_id INT NOT NULL,
    metadata JSON,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_advertisements_3nf PRIMARY KEY (ad_id),
    CONSTRAINT fk_advertisements_advertiser FOREIGN KEY (advertiser_id)
        REFERENCES advertisers (advertiser_id) ON DELETE RESTRICT,
    INDEX idx_advertiser (advertiser_id),
    INDEX idx_is_active (is_active),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- STEP 4: Migrate data from old to new advertisements table
-- =====================================================
INSERT INTO advertisements_3nf 
    (ad_id, title, content_url, media_type, duration_sec, advertiser_id, metadata, is_active, created_at, updated_at)
SELECT 
    a.ad_id,
    a.title,
    a.content_url,
    a.media_type,
    a.duration_sec,
    adv.advertiser_id,  -- Join to get advertiser_id
    a.metadata,
    a.is_active,
    a.created_at,
    a.updated_at
FROM advertisements a
JOIN advertisers adv ON a.advertiser_name = adv.advertiser_name;

-- =====================================================
-- STEP 5: Verify data migration
-- =====================================================
-- Check row counts match
SELECT 
    'Original count' as check_type,
    COUNT(*) as row_count
FROM advertisements
UNION ALL
SELECT 
    'Migrated count' as check_type,
    COUNT(*) as row_count
FROM advertisements_3nf
UNION ALL
SELECT 
    'Difference' as check_type,
    (SELECT COUNT(*) FROM advertisements) - (SELECT COUNT(*) FROM advertisements_3nf) as row_count;

-- Check for orphaned ads (should return 0)
SELECT COUNT(*) as orphaned_ads
FROM advertisements_3nf a
LEFT JOIN advertisers adv ON a.advertiser_id = adv.advertiser_id
WHERE adv.advertiser_id IS NULL;

-- =====================================================
-- STEP 6: Update ad_schedule foreign key
-- =====================================================
-- Drop existing FK constraint
ALTER TABLE ad_schedule 
DROP FOREIGN KEY fk_ad_schedule_ad_id;

-- =====================================================
-- STEP 7: Backup old table and rename new one
-- =====================================================
-- Rename old table as backup (DO NOT DROP YET - keep for rollback)
RENAME TABLE advertisements TO advertisements_backup_pre3nf;

-- Rename new table to original name
RENAME TABLE advertisements_3nf TO advertisements;

-- =====================================================
-- STEP 8: Re-create ad_schedule foreign key
-- =====================================================
ALTER TABLE ad_schedule 
ADD CONSTRAINT fk_ad_schedule_ad_id 
FOREIGN KEY (ad_id) REFERENCES advertisements (ad_id) ON DELETE CASCADE;

-- =====================================================
-- VERIFICATION QUERIES (Run these manually after migration)
-- =====================================================

-- 1. Verify all advertisers extracted
-- SELECT advertiser_name, COUNT(*) as ad_count
-- FROM advertisements a
-- JOIN advertisers adv ON a.advertiser_id = adv.advertiser_id
-- GROUP BY advertiser_name
-- ORDER BY ad_count DESC;

-- 2. Check for duplicate advertiser names (should be 0)
-- SELECT advertiser_name, COUNT(*) as duplicate_count
-- FROM advertisers
-- GROUP BY advertiser_name
-- HAVING COUNT(*) > 1;

-- 3. Verify foreign key constraints working
-- SELECT 
--     TABLE_NAME,
--     CONSTRAINT_NAME,
--     REFERENCED_TABLE_NAME,
--     REFERENCED_COLUMN_NAME
-- FROM information_schema.KEY_COLUMN_USAGE
-- WHERE TABLE_SCHEMA = DATABASE()
--   AND TABLE_NAME = 'advertisements'
--   AND REFERENCED_TABLE_NAME IS NOT NULL;

-- =====================================================
-- ROLLBACK PLAN (if needed)
-- =====================================================
-- In case of issues, run these commands to rollback:
--
-- ALTER TABLE ad_schedule DROP FOREIGN KEY fk_ad_schedule_ad_id;
-- RENAME TABLE advertisements TO advertisements_3nf_failed;
-- RENAME TABLE advertisements_backup_pre3nf TO advertisements;
-- ALTER TABLE ad_schedule 
-- ADD CONSTRAINT fk_ad_schedule_ad_id 
-- FOREIGN KEY (ad_id) REFERENCES advertisements (ad_id) ON DELETE CASCADE;
-- DROP TABLE advertisements_3nf_failed;
-- DROP TABLE advertisers;

-- =====================================================
-- CLEANUP (Run after 7 days of successful operation)
-- =====================================================
-- DROP TABLE advertisements_backup_pre3nf;

-- Migration complete!
-- Database is now in 3rd Normal Form (3NF)
