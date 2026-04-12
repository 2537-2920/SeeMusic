USE `SeeMusic`;

SHOW TABLES;

SELECT 'user' AS table_name, COUNT(*) AS row_count FROM `user`
UNION ALL SELECT 'project', COUNT(*) FROM `project`
UNION ALL SELECT 'sheet', COUNT(*) FROM `sheet`
UNION ALL SELECT 'report', COUNT(*) FROM `report`
UNION ALL SELECT 'audio_analysis', COUNT(*) FROM `audio_analysis`;
