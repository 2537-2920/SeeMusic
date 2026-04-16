# SeeMusic 数据库说明

> 说明：本文档以当前 ORM 模型 [`backend/db/models.py`](SeeMusic/backend/db/models.py) 和增量迁移脚本 [`seemusic_db_migration_20260415.sql`](SeeMusic/seemusic_db_migration_20260415.sql) 为准。项目启动时会读取根目录 `.env`，通过 `SSH_*` + `MYSQL_*` 连接远程 MySQL；`DB_*` 保留为运行时兼容/回退配置。

## 变更概览

- `report`：补充 `report_id`、`analysis_id`、`metadata`，并允许旧数据的 `project_id` 为空。
- `community_post`：补充社区业务字段与互动计数，允许旧数据的 `user_id` / `sheet_id` 为空。
- `audio_analysis`：补充 `result` JSON 字段，并允许旧数据的 `user_id` 为空；当前音高主存储改为 `note events`。
- `community_comment`：新增，保存社区评论。
- `community_like`：新增，保存社区点赞记录。
- `community_favorite`：新增，保存社区收藏记录。
- `pitch_sequence`：从默认主存储降级为按需生成的逐点缓存表。

## 通用约定

- MySQL 下主键使用 `BIGINT` 自增；SQLite 下会自动兼容为 `INTEGER`。
- `create_time` / `update_time` 统一由数据库时间戳自动维护。
- JSON 字段包括 `note_data`、`error_points`、`tags`、`params`、`result`、`metadata`。
- 布尔字段 `is_public`、`is_reference` 在 MySQL 中按 `TINYINT(1)` 存储。
- `project.analysis_id` 是业务关联字段，不是数据库外键；`pitch_sequence.analysis_id` 外键指向 `audio_analysis.analysis_id`。
- ORM 中 `report.metadata` 和 `user_history.metadata` 分别映射为 `metadata_`，用于避开 SQLAlchemy 的保留属性名。
- 一次性全清当前 `.env` 指向 MySQL 应用数据时，可使用 [`scripts/clear_current_mysql_data.py`](/home/xianz/SeeMusic/scripts/clear_current_mysql_data.py)；该脚本只 `TRUNCATE` 应用表，不改表结构。

## 1. user（用户表）

作用：用户登录、注册、个人中心、权限隔离。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 用户主键，自增。 |
| username | VARCHAR(50) | 用户名，唯一，非空。 |
| password | VARCHAR(100) | 加密后的密码，非空。 |
| nickname | VARCHAR(50) | 用户昵称，可空。 |
| avatar | VARCHAR(255) | 头像路径，可空。 |
| email | VARCHAR(128) | 邮箱，唯一，可空。 |
| create_time | DATETIME | 账号创建时间，自动生成。 |
| update_time | DATETIME | 信息更新时间，自动更新。 |

## 2. project（扒谱项目表）

作用：记录每一次扒谱任务，关联音频、进度和所属用户。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 项目主键，自增。 |
| user_id | BIGINT FK | 关联 `user.id`，非空，带索引。 |
| title | VARCHAR(100) | 项目名称，非空。 |
| audio_url | VARCHAR(500) | 原始音频文件路径，可空。 |
| duration | FLOAT | 音频时长，单位秒，可空。 |
| status | INT | 项目状态，`0=处理中` / `1=完成` / `2=失败`，默认 `0`。 |
| analysis_id | VARCHAR(64) | 关联分析任务的业务 ID，可空。 |
| create_time | DATETIME | 项目创建时间，自动生成。 |
| update_time | DATETIME | 项目最后更新时间，自动更新。 |

## 3. sheet（乐谱数据表）

作用：存储扒谱生成的五线谱结构、音符和基础谱面参数。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 乐谱主键，自增。 |
| project_id | BIGINT FK | 关联 `project.id`，非空，带索引。 |
| score_id | VARCHAR(64) | 乐谱唯一标识，唯一，可空。 |
| note_data | JSON | 音符与五线谱结构 JSON，非空。 |
| bpm | INT | 曲速，默认 `120`。 |
| key_sign | VARCHAR(10) | 调号，默认 `C`。 |
| time_sign | VARCHAR(10) | 拍号，默认 `4/4`。 |
| update_time | DATETIME | 乐谱最后修改时间，自动更新。 |

## 4. export_record（导出记录表）

作用：记录用户的导出操作和导出文件。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 导出记录主键，自增。 |
| project_id | BIGINT FK | 关联 `project.id`，非空，带索引。 |
| format | VARCHAR(32) | 导出格式，例如 `pdf` / `png` / `midi`。 |
| file_url | VARCHAR(500) | 导出文件路径，可空。 |
| create_time | DATETIME | 导出操作时间，自动生成。 |
| update_time | DATETIME | 导出记录最后更新时间，自动更新。 |

## 5. report（评估报告表）

作用：存储音准、节奏打分结果，以及练习/分析中的错误点。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 报告主键，自增。 |
| report_id | VARCHAR(64) | 报告业务 ID，唯一，非空。 |
| project_id | BIGINT FK | 关联 `project.id`，可空，用于兼容历史数据。 |
| analysis_id | VARCHAR(64) | 关联分析任务的业务 ID，可空，带索引。 |
| pitch_score | FLOAT | 音准得分，可空。 |
| rhythm_score | FLOAT | 节奏得分，可空。 |
| total_score | FLOAT | 综合总分，可空。 |
| error_points | JSON | 错误点 JSON，可空。 |
| export_url | VARCHAR(500) | 报告文件路径，可空。 |
| metadata | JSON | 额外上下文信息，默认空对象，非空。 |
| create_time | DATETIME | 报告生成时间，自动生成。 |
| update_time | DATETIME | 报告最后更新时间，自动更新。 |

## 6. community_post（乐谱社区表）

作用：存储用户发布的社区帖子，以及浏览、点赞、收藏、下载等互动数据。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 帖子主键，自增。 |
| user_id | BIGINT FK | 关联 `user.id`，可空，用于兼容历史数据。 |
| sheet_id | BIGINT FK | 关联 `sheet.id`，可空，用于兼容历史数据。 |
| community_score_id | VARCHAR(64) | 社区帖子业务 ID，唯一，非空。 |
| score_id | VARCHAR(64) | 乐谱业务 ID，唯一，非空。 |
| title | VARCHAR(255) | 帖子标题，非空。 |
| author_name | VARCHAR(100) | 展示用作者名，默认 `社区用户`。 |
| subtitle | VARCHAR(255) | 副标题，可空。 |
| content | TEXT | 帖子正文，可空。 |
| style | VARCHAR(64) | 风格标签，可空。 |
| instrument | VARCHAR(64) | 乐器类型，可空。 |
| price | FLOAT | 价格，默认 `0`。 |
| cover_url | VARCHAR(500) | 封面图地址，可空。 |
| source_file_name | VARCHAR(255) | 原始文件名，可空。 |
| file_content_base64 | LONGTEXT | PDF 等文件内容的 Base64 编码，可空。 |
| file_content_type | VARCHAR(64) | 文件 MIME 类型，默认 `application/pdf`。 |
| tags | JSON | 标签数组，默认空列表。 |
| is_public | BOOLEAN | 是否公开，默认 `true`。 |
| like_count | INT | 点赞数，默认 `0`。 |
| favorite_count | INT | 收藏数，默认 `0`。 |
| download_count | INT | 下载数，默认 `0`。 |
| view_count | INT | 浏览量，默认 `0`。 |
| create_time | DATETIME | 帖子发布时间，自动生成。 |
| update_time | DATETIME | 帖子最后更新时间，自动更新。 |

## 7. community_comment（社区评论表）

作用：保存社区帖子评论内容。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 评论主键，自增。 |
| comment_id | VARCHAR(64) | 评论业务 ID，唯一，非空。 |
| post_id | BIGINT FK | 关联 `community_post.id`，非空，带索引。 |
| user_id | BIGINT FK | 关联 `user.id`，可空，删除用户后置空。 |
| username | VARCHAR(100) | 评论展示用户名，非空。 |
| avatar_url | VARCHAR(500) | 评论用户头像，可空。 |
| content | TEXT | 评论正文，非空。 |
| create_time | DATETIME | 评论创建时间，自动生成。 |

## 8. community_like（社区点赞表）

作用：保存帖子点赞行为，支持游客或登录用户去重。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 点赞记录主键，自增。 |
| post_id | BIGINT FK | 关联 `community_post.id`，非空，带索引。 |
| actor_key | VARCHAR(128) | 点赞行为主体标识，和 `post_id` 组成唯一约束。 |
| user_id | BIGINT FK | 关联 `user.id`，可空，删除用户后置空。 |
| create_time | DATETIME | 点赞时间，自动生成。 |

## 9. community_favorite（社区收藏表）

作用：保存帖子收藏行为，支持游客或登录用户去重。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 收藏记录主键，自增。 |
| post_id | BIGINT FK | 关联 `community_post.id`，非空，带索引。 |
| actor_key | VARCHAR(128) | 收藏行为主体标识，和 `post_id` 组成唯一约束。 |
| user_id | BIGINT FK | 关联 `user.id`，可空，删除用户后置空。 |
| create_time | DATETIME | 收藏时间，自动生成。 |

## 10. audio_analysis（音频分析表）

作用：存储音高检测、节拍检测、音频分离等分析任务与结果。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 分析记录主键，自增。 |
| user_id | BIGINT FK | 关联 `user.id`，可空，用于兼容历史数据。 |
| analysis_id | VARCHAR(64) | 分析任务唯一 ID，唯一且非空。 |
| file_name | VARCHAR(255) | 音频文件名，可空。 |
| file_url | VARCHAR(500) | 音频文件路径，可空。 |
| sample_rate | INT | 采样率，可空。 |
| duration | FLOAT | 音频时长，可空。 |
| bpm | INT | 检测到的节拍速度，可空。 |
| status | INT | 任务状态，`0=处理中` / `1=成功` / `2=失败`。 |
| params | JSON | 分析参数 JSON，默认空对象。 |
| result | JSON | 分析结果 JSON，默认空对象。音高场景下主存 `{ pitch_sequence_format: "note_events", pitch_sequence: [...], pitch_meta: {...} }`。 |
| create_time | DATETIME | 创建时间，自动生成。 |
| update_time | DATETIME | 更新时间，自动更新。 |

## 11. pitch_sequence（音高序列缓存表）

作用：按需缓存逐点音高时间序列，用于对比和图表渲染；默认持久化不再写入该表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 序列点主键，自增。 |
| analysis_id | VARCHAR(64) FK | 关联 `audio_analysis.analysis_id`，非空，带索引。 |
| time | FLOAT | 时间点，单位秒，非空。 |
| frequency | FLOAT | 音高频率，可空。 |
| note | VARCHAR(32) | 音符名称，例如 `A4`，可空。 |
| confidence | FLOAT | 置信度，可空。 |
| cents_offset | FLOAT | 音分偏差值，可空。 |
| is_reference | BOOLEAN | 是否为参考音轨，默认 `false`。 |

> 该表只保存序列采样点，不包含 `create_time` / `update_time`。
> 当前默认链路会先把逐帧音高压缩为音符事件，落到 `audio_analysis.result` 中；只有 `/pitch/compare`、`/charts/pitch-curve` 等确实需要逐点曲线时，才会把展开后的点写入本表作为缓存。
> 建议索引：`ix_pitch_sequence_analysis_id_is_reference (analysis_id, is_reference)`，用于加速按需缓存写入与音高曲线读取。

## 12. user_history（用户历史记录表）

作用：记录用户的音频、乐谱和分析操作历史。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 历史记录主键，自增。 |
| user_id | BIGINT FK | 关联 `user.id`，非空，带索引。 |
| type | VARCHAR(32) | 记录类型，例如 `score` / `audio` / `report`。 |
| resource_id | VARCHAR(64) | 关联资源 ID，可空。 |
| title | VARCHAR(255) | 历史记录标题，非空。 |
| metadata | JSON | 附加信息 JSON，默认空对象。 |
| create_time | DATETIME | 记录生成时间，自动生成。 |

## 13. user_token（用户令牌表）

作用：保存登录令牌与过期时间，用于会话鉴权与登出失效。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 令牌记录主键，自增。 |
| user_id | BIGINT FK | 关联 `user.id`，非空，带索引。 |
| token | VARCHAR(128) | 登录令牌，唯一，非空，带索引。 |
| expired_time | DATETIME | 令牌过期时间，非空。 |
| created_at | DATETIME | 令牌创建时间，自动生成。 |
