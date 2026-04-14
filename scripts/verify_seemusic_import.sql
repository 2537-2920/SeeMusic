USE `SeeMusic`;

SHOW TABLES;

SELECT 'user' AS table_name, COUNT(*) AS row_count FROM `user`
UNION ALL SELECT 'project', COUNT(*) FROM `project`
UNION ALL SELECT 'sheet', COUNT(*) FROM `sheet`
UNION ALL SELECT 'report', COUNT(*) FROM `report`
UNION ALL SELECT 'community_post', COUNT(*) FROM `community_post`
UNION ALL SELECT 'export_record', COUNT(*) FROM `export_record`
UNION ALL SELECT 'audio_analysis', COUNT(*) FROM `audio_analysis`
UNION ALL SELECT 'pitch_sequence', COUNT(*) FROM `pitch_sequence`
UNION ALL SELECT 'user_history', COUNT(*) FROM `user_history`;
