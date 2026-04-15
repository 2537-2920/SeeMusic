USE `SeeMusic`;

SHOW TABLES;

SELECT 'user' AS table_name, COUNT(*) AS row_count FROM `user`
UNION ALL SELECT 'project', COUNT(*) FROM `project`
UNION ALL SELECT 'sheet', COUNT(*) FROM `sheet`
UNION ALL SELECT 'report', COUNT(*) FROM `report`
UNION ALL SELECT 'community_post', COUNT(*) FROM `community_post`
UNION ALL SELECT 'community_comment', COUNT(*) FROM `community_comment`
UNION ALL SELECT 'community_like', COUNT(*) FROM `community_like`
UNION ALL SELECT 'community_favorite', COUNT(*) FROM `community_favorite`
UNION ALL SELECT 'export_record', COUNT(*) FROM `export_record`
UNION ALL SELECT 'audio_analysis', COUNT(*) FROM `audio_analysis`
UNION ALL SELECT 'pitch_sequence', COUNT(*) FROM `pitch_sequence`
UNION ALL SELECT 'user_history', COUNT(*) FROM `user_history`;

SELECT 'report.report_id' AS schema_item, EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'report' AND column_name = 'report_id'
) AS present
UNION ALL SELECT 'report.analysis_id', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'report' AND column_name = 'analysis_id'
)
UNION ALL SELECT 'report.metadata', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'report' AND column_name = 'metadata'
)
UNION ALL SELECT 'community_post.community_score_id', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'community_score_id'
)
UNION ALL SELECT 'community_post.score_id', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'score_id'
)
UNION ALL SELECT 'community_post.author_name', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'author_name'
)
UNION ALL SELECT 'community_post.subtitle', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'subtitle'
)
UNION ALL SELECT 'community_post.style', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'style'
)
UNION ALL SELECT 'community_post.instrument', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'instrument'
)
UNION ALL SELECT 'community_post.price', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'price'
)
UNION ALL SELECT 'community_post.cover_url', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'cover_url'
)
UNION ALL SELECT 'community_post.source_file_name', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'source_file_name'
)
UNION ALL SELECT 'community_post.favorite_count', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'favorite_count'
)
UNION ALL SELECT 'community_post.download_count', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'community_post' AND column_name = 'download_count'
)
UNION ALL SELECT 'audio_analysis.result', EXISTS(
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'audio_analysis' AND column_name = 'result'
)
ORDER BY schema_item;
