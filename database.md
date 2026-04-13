# SeeMusic 数据库说明

> 说明：本文档以当前 ORM 模型 [`backend/db/models.py`](/home/xianz/SeeMusic/backend/db/models.py) 为准。项目启动时会读取根目录 `.env`，通过 `SSH_*` + `MYSQL_*` 连接远程 MySQL；`DB_*` 保留为运行时兼容/回退配置。

## 变更概览

- `user`：用户基础表，支撑登录、注册、个人中心和权限隔离。
- `project`：新增 `analysis_id`，用于把扒谱项目和分析任务关联起来。
- `sheet`：保存生成的谱面 JSON、调号、拍号、速度等信息。
- `report`：新增，保存音准/节奏评分与错误点。
- `community_post`：新增，保存社区帖子与互动数据。
- `audio_analysis`：新增，保存音频分析任务与结果。
- `pitch_sequence`：新增，保存音高曲线采样点。
- `user_history`：新增，保存用户操作历史。
- `export_record`：记录导出结果文件。

## 通用约定

- MySQL 下主键使用 `BIGINT` 自增；SQLite 下会自动兼容为 `INTEGER`。
- `create_time` / `update_time` 统一由数据库时间戳自动维护。
- JSON 字段包括 `note_data`、`error_points`、`tags`、`params`、`metadata`。
- 布尔字段 `is_public`、`is_reference` 在 MySQL 中按 `TINYINT(1)` 存储。
- `project.analysis_id` 目前是业务字段，不是数据库外键；`pitch_sequence.analysis_id` 外键指向 `audio_analysis.analysis_id`。

## 1. user（用户表）

作用：用户登录、注册、个人中心、权限隔离。
关联页面：登录页、个人中心、社区、历史记录。

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
关联页面：我的项目、历史记录、扒谱结果页。

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
关联页面：乐谱编辑页、导出页、社区发布页。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 乐谱主键，自增。 |
| project_id | BIGINT FK | 关联 `project.id`，非空，带索引。 |
| score_id | VARCHAR(64) | 乐谱唯一标识，供 API 使用，唯一，可空。 |
| note_data | JSON | 音符与五线谱结构 JSON，非空。 |
| bpm | INT | 曲速，默认 `120`。 |
| key_sign | VARCHAR(10) | 调号，默认 `C`。 |
| time_sign | VARCHAR(10) | 拍号，默认 `4/4`。 |
| update_time | DATETIME | 乐谱最后修改时间，自动更新。 |

## 4. export_record（导出记录表）

作用：记录用户的导出操作和导出文件。
关联页面：导出页、历史记录、个人中心。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 导出记录主键，自增。 |
| project_id | BIGINT FK | 关联 `project.id`，非空，带索引。 |
| format | VARCHAR(32) | 导出格式，例如 `pdf` / `png` / `midi`。 |
| file_url | VARCHAR(500) | 导出文件路径，可空。 |
| create_time | DATETIME | 导出操作时间，自动生成。 |
| update_time | DATETIME | 导出记录最后更新时间，自动更新。 |

## 5. report（评估报告表，新增）

作用：存储音准、节奏打分结果，以及练习/分析中的错误点。
关联页面：智能评估页、练习报告页、导出页。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 报告主键，自增。 |
| project_id | BIGINT FK | 关联 `project.id`，非空，带索引。 |
| pitch_score | FLOAT | 音准得分，可空。 |
| rhythm_score | FLOAT | 节奏得分，可空。 |
| total_score | FLOAT | 综合总分，可空。 |
| error_points | JSON | 错误点 JSON，可空。 |
| export_url | VARCHAR(500) | 报告文件路径，可空。 |
| create_time | DATETIME | 报告生成时间，自动生成。 |
| update_time | DATETIME | 报告最后更新时间，自动更新。 |

## 6. community_post（乐谱社区表，新增）

作用：存储用户发布的社区帖子，以及浏览、点赞等互动数据。
关联页面：乐谱社区、个人中心、帖子详情页。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 帖子主键，自增。 |
| user_id | BIGINT FK | 关联 `user.id`，非空，带索引。 |
| sheet_id | BIGINT FK | 关联 `sheet.id`，非空，带索引。 |
| title | VARCHAR(255) | 帖子标题，非空。 |
| content | TEXT | 帖子正文，可空。 |
| tags | JSON | 标签数组，可空，默认空列表。 |
| is_public | BOOLEAN | 是否公开，默认 `true`。 |
| like_count | INT | 点赞数，默认 `0`。 |
| view_count | INT | 浏览量，默认 `0`。 |
| create_time | DATETIME | 帖子发布时间，自动生成。 |
| update_time | DATETIME | 帖子最后更新时间，自动更新。 |

## 7. audio_analysis（音频分析表，新增）

作用：存储音高检测、节拍检测、音频分离等分析任务与结果。
对应 API：音高识别、实时音准、节拍检测、多轨分离。
关联页面：音高识别页、实时音准页、歌唱评测页、音频上传页、历史记录页。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 分析记录主键，自增。 |
| user_id | BIGINT FK | 关联 `user.id`，非空，带索引。 |
| analysis_id | VARCHAR(64) | 分析任务唯一 ID，唯一且非空。 |
| file_name | VARCHAR(255) | 音频文件名，可空。 |
| file_url | VARCHAR(500) | 音频文件路径，可空。 |
| sample_rate | INT | 采样率，可空。 |
| duration | FLOAT | 音频时长，可空。 |
| bpm | INT | 检测到的节拍速度，可空。 |
| status | INT | 任务状态，`0=处理中` / `1=成功` / `2=失败`。 |
| params | JSON | 分析参数 JSON，默认空对象。 |
| create_time | DATETIME | 创建时间，自动生成。 |
| update_time | DATETIME | 更新时间，自动更新。 |

## 8. pitch_sequence（音高序列表，新增）

作用：存储音高时间点、频率、音符信息，用于对比和图表渲染。
对应 API：音高对比、音高曲线图、实时音准。
关联页面：音高对比页、音高曲线图页、歌唱评测结果页、实时音准页。

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

> 这个表只保存序列采样点，不包含 `create_time` / `update_time`。

## 9. user_history（用户历史记录表，新增）

作用：记录用户的音频、乐谱和分析操作历史。
对应 API：个人中心历史记录、历史管理。
关联页面：个人中心历史记录页、我的项目页、最近操作页。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK | 历史记录主键，自增。 |
| user_id | BIGINT FK | 关联 `user.id`，非空，带索引。 |
| type | VARCHAR(32) | 记录类型，例如 `score` / `audio` / `analysis`。 |
| resource_id | VARCHAR(64) | 关联资源 ID，可空。 |
| title | VARCHAR(255) | 历史记录标题，非空。 |
| metadata | JSON | 附加信息 JSON，默认空对象。 |
| create_time | DATETIME | 记录生成时间，自动生成。 |

> ORM 中该列映射为 `metadata_`，是为了避开 SQLAlchemy 里 `metadata` 的保留属性名。
