# SeeMusic 数据库说明

> 本文档以当前 ORM 模型 [backend/db/models.py](backend/db/models.py) 为主，并与迁移脚本 [seemusic_db_migration_20260415.sql](seemusic_db_migration_20260415.sql) 对齐。

## 1. 总览

当前核心表如下：

- `user`：用户基础信息。
- `user_token`：登录态 token（新增）。
- `project`：扒谱项目。
- `sheet`：乐谱内容。
- `export_record`：导出记录。
- `report`：评估报告（已扩展 `report_id` / `analysis_id` / `metadata`）。
- `community_post`：社区帖子（已扩展多字段）。
- `community_comment`：社区评论（新增）。
- `community_like`：社区点赞（新增）。
- `community_favorite`：社区收藏（新增）。
- `audio_analysis`：音频分析（已新增 `result` JSON）。
- `pitch_sequence`：音高序列点。
- `user_history`：用户历史记录。

## 2. 通用约定

- 主键：MySQL 使用 `BIGINT AUTO_INCREMENT`，SQLite 兼容为 `INTEGER`。
- 时间字段：多数表使用 `create_time`，部分表还包含自动更新的 `update_time`。
- JSON 字段：`note_data`、`error_points`、`metadata`、`tags`、`params`、`result`。
- 业务 ID 字段：`analysis_id`、`score_id`、`community_score_id`、`report_id`、`comment_id`。
- 重要外键：`pitch_sequence.analysis_id -> audio_analysis.analysis_id`（不是走主键 id）。

## 3. 表结构

### 3.1 user

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| username | VARCHAR(50) | 唯一，非空 |
| password | VARCHAR(100) | 非空 |
| nickname | VARCHAR(50) | 可空 |
| avatar | VARCHAR(255) | 可空 |
| email | VARCHAR(128) | 唯一，可空 |
| create_time | DATETIME | 自动生成 |
| update_time | DATETIME | 自动更新 |

### 3.2 user_token

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| user_id | BIGINT FK | 指向 `user.id`，非空，索引 |
| token | VARCHAR(128) | 唯一，非空，索引 |
| expired_time | DATETIME | 非空 |
| created_at| DATETIME | 自动生成 |

### 3.3 project

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| user_id | BIGINT FK | 指向 `user.id`，非空，索引 |
| title | VARCHAR(100) | 非空 |
| audio_url | VARCHAR(500) | 可空 |
| duration | FLOAT | 可空 |
| status | INT | 默认 `0` |
| analysis_id | VARCHAR(64) | 业务关联字段，可空 |
| create_time | DATETIME | 自动生成 |
| update_time | DATETIME | 自动更新 |

### 3.4 sheet

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| project_id | BIGINT FK | 指向 `project.id`，非空，索引 |
| score_id | VARCHAR(64) | 唯一，可空 |
| note_data | JSON | 非空 |
| bpm | INT | 默认 `120` |
| key_sign | VARCHAR(10) | 默认 `C` |
| time_sign | VARCHAR(10) | 默认 `4/4` |
| update_time | DATETIME | 自动更新 |

### 3.5 export_record

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| project_id | BIGINT FK | 指向 `project.id`，非空，索引 |
| format | VARCHAR(32) | 非空 |
| file_url | VARCHAR(500) | 可空 |
| create_time | DATETIME | 自动生成 |
| update_time | DATETIME | 自动更新 |

### 3.6 report

> 迁移重点：`project_id` 改为可空；新增 `report_id`、`analysis_id`、`metadata`。

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| report_id | VARCHAR(64) | 唯一，非空，索引 |
| project_id | BIGINT FK | 指向 `project.id`，可空，索引 |
| analysis_id | VARCHAR(64) | 可空，索引 |
| pitch_score | FLOAT | 可空 |
| rhythm_score | FLOAT | 可空 |
| total_score | FLOAT | 可空 |
| error_points | JSON | 可空 |
| export_url | VARCHAR(500) | 可空 |
| metadata | JSON | 非空，默认 `{}` |
| create_time | DATETIME | 自动生成 |
| update_time | DATETIME | 自动更新 |

### 3.7 community_post

> 迁移重点：`user_id`、`sheet_id` 改为可空；新增社区业务字段。

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| user_id | BIGINT FK | 指向 `user.id`，可空，索引 |
| sheet_id | BIGINT FK | 指向 `sheet.id`，可空，索引 |
| community_score_id | VARCHAR(64) | 唯一，非空，索引 |
| score_id | VARCHAR(64) | 唯一，非空，索引 |
| title | VARCHAR(255) | 非空 |
| author_name | VARCHAR(100) | 非空，默认 `社区用户` |
| subtitle | VARCHAR(255) | 可空 |
| content | TEXT | 可空 |
| style | VARCHAR(64) | 可空 |
| instrument | VARCHAR(64) | 可空 |
| price | FLOAT | 非空，默认 `0.0` |
| cover_url | VARCHAR(500) | 可空 |
| source_file_name | VARCHAR(255) | 可空 |
| tags | JSON | 非空，默认 `[]` |
| is_public | BOOLEAN | 非空，默认 `true` |
| like_count | INT | 非空，默认 `0` |
| favorite_count | INT | 非空，默认 `0` |
| download_count | INT | 非空，默认 `0` |
| view_count | INT | 非空，默认 `0` |
| create_time | DATETIME | 自动生成 |
| update_time | DATETIME | 自动更新 |

### 3.8 community_comment

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| comment_id | VARCHAR(64) | 唯一，非空，索引 |
| post_id | BIGINT FK | 指向 `community_post.id`，非空，索引 |
| user_id | BIGINT FK | 指向 `user.id`，可空，索引，`ON DELETE SET NULL` |
| username | VARCHAR(100) | 非空 |
| avatar_url | VARCHAR(500) | 可空 |
| content | TEXT | 非空 |
| create_time | DATETIME | 自动生成 |

### 3.9 community_like

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| post_id | BIGINT FK | 指向 `community_post.id`，非空，索引 |
| actor_key | VARCHAR(128) | 非空 |
| user_id | BIGINT FK | 指向 `user.id`，可空，索引，`ON DELETE SET NULL` |
| create_time | DATETIME | 自动生成 |

额外约束：联合唯一 `uq_community_like_post_actor (post_id, actor_key)`。

### 3.10 community_favorite

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| post_id | BIGINT FK | 指向 `community_post.id`，非空，索引 |
| actor_key | VARCHAR(128) | 非空 |
| user_id | BIGINT FK | 指向 `user.id`，可空，索引，`ON DELETE SET NULL` |
| create_time | DATETIME | 自动生成 |

额外约束：联合唯一 `uq_community_favorite_post_actor (post_id, actor_key)`。

### 3.11 audio_analysis

> 迁移重点：`user_id` 改为可空；新增 `result` JSON。

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| user_id | BIGINT FK | 指向 `user.id`，可空，索引 |
| analysis_id | VARCHAR(64) | 唯一，非空，索引 |
| file_name | VARCHAR(255) | 可空 |
| file_url | VARCHAR(500) | 可空 |
| sample_rate | INT | 可空 |
| duration | FLOAT | 可空 |
| bpm | INT | 可空 |
| status | INT | 非空，默认 `0` |
| params | JSON | 非空，默认 `{}` |
| result | JSON | 非空，默认 `{}` |
| create_time | DATETIME | 自动生成 |
| update_time | DATETIME | 自动更新 |

### 3.12 pitch_sequence

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| analysis_id | VARCHAR(64) FK | 指向 `audio_analysis.analysis_id`，非空，索引 |
| time | FLOAT | 非空 |
| frequency | FLOAT | 可空 |
| note | VARCHAR(32) | 可空 |
| confidence | FLOAT | 可空 |
| cents_offset | FLOAT | 可空 |
| is_reference | BOOLEAN | 非空，默认 `false` |

说明：该表没有 `create_time` / `update_time`。

### 3.13 user_history

| 字段 | 类型 | 约束/说明 |
| --- | --- | --- |
| id | BIGINT PK | 自增 |
| user_id | BIGINT FK | 指向 `user.id`，非空，索引 |
| type | VARCHAR(32) | 非空 |
| resource_id | VARCHAR(64) | 可空 |
| title | VARCHAR(255) | 非空 |
| metadata | JSON | 非空，默认 `{}` |
| create_time | DATETIME | 自动生成 |

说明：ORM 中属性名为 `metadata_`，数据库列名仍是 `metadata`。

## 4. 迁移与一致性说明

- 脚本 [seemusic_db_migration_20260415.sql](seemusic_db_migration_20260415.sql) 已覆盖本次主要结构变更（`report`、`community_post`、`audio_analysis`、`community_*`）。
- 若文档与代码不一致，以 [backend/db/models.py](backend/db/models.py) 为准。
