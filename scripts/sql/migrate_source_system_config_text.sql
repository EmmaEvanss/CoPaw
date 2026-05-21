ALTER TABLE swe_source_system_config
    ADD COLUMN config_text LONGTEXT NULL AFTER source_id;

UPDATE swe_source_system_config
SET config_text = CAST(config_json AS CHAR CHARACTER SET utf8mb4)
WHERE config_text IS NULL;

ALTER TABLE swe_source_system_config
    MODIFY COLUMN config_text LONGTEXT NOT NULL;

ALTER TABLE swe_source_system_config
    DROP COLUMN config_json;
