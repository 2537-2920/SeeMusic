数据库连接信息（同WiFi WHU-STU-5G）
主机地址：找我查
端口：3306
用户名：root
密码：Ctrl20242028
数据库名：SeeMusic
字符集：utf8mb4

数据库表说明
1）用户表 user
作用：登录、注册、个人中心、权限隔离
用到页面：登录页、个人中心、社区、历史记录
字段：
id（主键，自增，唯一标识用户）
username（用户名，唯一非空）
password（加密后的密码，非空）
nickname（用户昵称，可选）
email（邮箱，唯一，登录 / 注册使用）
avatar（用户头像路径，可选）
create_time（账号创建时间，自动生成）
update_time（信息更新时间，自动更新）

2）扒谱项目表 project
作用：存储每一次用户的扒谱任务，关联音频、进度、所属用户
用到页面：我的项目、历史记录、扒谱结果页
字段：
id（主键，自增，唯一标识项目）
user_id（关联用户表 id，非空，索引）
title（项目名称，非空）
audio_url（原始音频文件路径，可选）
duration（音频时长，单位秒，可选）
status（项目状态：0 = 处理中 / 1 = 完成 / 2 = 失败，默认 0）
analysis_id（关联音频分析表 ID，可选）
create_time（项目创建时间，自动生成）
update_time（项目最后更新时间，自动更新）

3）乐谱数据表 sheet
作用：存储扒谱生成的五线谱结构、音符、节拍等核心数据
用到页面：乐谱编辑页、导出页、社区发布页
字段：
id（主键，自增，唯一标识乐谱）
project_id（关联项目表 id，非空，索引）
score_id（乐谱唯一标识 ID，供 API 使用，唯一）
note_data（音符 JSON 数据，存储五线谱结构，非空）
bpm（乐曲速度，默认 120，可选）
key_sign（调号，默认 C，可选）
time_sign（拍号，默认 4/4，可选）
update_time（乐谱最后修改时间，自动更新）

4）评估报告表 report
作用：存储音准、节奏打分结果，练习评估数据
用到页面：智能评估页、练习报告页、导出页
字段：
id（主键，自增，唯一标识报告）
project_id（关联项目表 id，非空，索引）
pitch_score（音准得分，可选）
rhythm_score（节奏得分，可选）
total_score（综合总分，可选）
error_points（错误点 JSON 数据，存储偏差位置，可选）
export_url（报告文件路径，可选）
create_time（报告生成时间，自动生成）
update_time（报告最后更新时间，自动更新）

5）乐谱社区表 community_post
作用：存储用户发布的社区乐谱帖子，互动数据
用到页面：乐谱社区、个人中心、帖子详情页
字段：
id（主键，自增，唯一标识帖子）
user_id（关联用户表 id，非空，索引）
sheet_id（关联乐谱表 id，非空，索引）
title（帖子标题，非空）
content（帖子正文描述，可选）
tags（帖子标签，JSON 格式，可选）
is_public（是否公开，默认 1 公开）
like_count（点赞数，默认 0，可选）
view_count（浏览量，默认 0，可选）
create_time（帖子发布时间，自动生成）
update_time（帖子最后更新时间，自动更新）

6）导出记录表 export_record
作用：记录用户的导出操作，关联导出文件
用到页面：导出页、历史记录、个人中心
字段：
id（主键，自增，唯一标识导出记录）
project_id（关联项目表 id，非空，索引）
format（导出格式：midi/pdf/image，非空）
file_url（导出文件路径，可选）
create_time（导出操作时间，自动生成）
update_time（导出记录最后更新时间，自动更新）

7）音频分析表 audio_analysis
作用：存储音高检测、节拍检测、音频分离任务与结果
对应 API：音高识别、实时音准、节拍检测、多轨分离
用到页面：音高识别页、实时音准页、歌唱评测页、音频上传页、历史记录页
字段：
id（主键，自增）
user_id（用户 ID，非空）
analysis_id（分析任务唯一 ID，唯一非空）
file_name（音频文件名）
file_url（音频文件路径）
sample_rate（采样率）
duration（音频时长）
bpm（检测到的节拍速度）
status（任务状态：0 处理中 / 1 成功 / 2 失败）
params（分析参数，JSON 格式）
create_time（创建时间，自动生成）
update_time（更新时间，自动更新）

8）音高序列表 pitch_sequence
作用：存储音高时间、频率、音符，用于对比与图表渲染
对应 API：音高对比、音高曲线图、实时音准
用到页面：音高对比页、音高曲线图页、歌唱评测结果页、实时音准页
字段：
id（主键，自增）
analysis_id（关联分析任务 ID，非空）
time（时间点，秒，非空）
frequency（音高频率）
note（音符名称，如 A4）
confidence（置信度）
cents_offset（音分偏差值）
is_reference（是否为参考音轨：0 用户 / 1 原唱）

9）用户历史记录表 user_history
作用：记录用户音频、乐谱、分析操作历史
对应 API：个人中心历史记录、历史管理
用到页面：个人中心历史记录页、我的项目页、最近操作页
字段：
id（主键，自增）
user_id（用户 ID，非空）
type（记录类型：score/audio/analysis）
resource_id（关联资源 ID）
title（历史记录标题）
metadata（附加信息，JSON 格式）
create_time（记录生成时间，自动生成）

10）用户登录令牌表 user_token
作用：存储用户登录后的 Token 身份凭证，用于快速校验用户 ID、管理登录过期、实现登录态保持
对应 API：用户登录、用户登出、登录鉴权、自动登录
用到页面：所有需要登录权限的页面、请求身份校验、登录状态保持
字段：
id（主键，自增）
user_id（用户 ID，非空，关联 user 表主键）
token（登录令牌，非空，用于身份识别）
expired_time（Token 过期时间，固定 2 小时有效期）
created_at（记录生成时间，自动生成）
