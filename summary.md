# SeeMusic 系统总结文档

## 1. 项目定位

SeeMusic 是一个面向音乐识别、自动扒谱、演奏评估、乐谱导出与社区分享的综合系统。系统同时支持西洋乐器与民族乐器的结果表达，当前核心能力包括：

- 音频上传与音高检测
- 节拍/速度检测与节奏评分
- 主旋律提取与音轨分离
- 钢琴五线谱生成与双手简化编配
- 吉他弹唱谱生成
- 古筝、笛子简谱生成与统一排版导出
- 导出、历史记录、用户系统与乐谱社区

---

## 2. 功能模块与模块层次结构

### 2.1 总体分层

系统采用“前端界面层 -> API 接口层 -> 服务编排层 -> 核心算法层 -> 数据与导出层”的分层结构：

```text
frontend/
  ├─ 页面与交互
  ├─ 结果预览
  └─ 导出触发

backend/api/
  ├─ REST 路由
  ├─ 请求/响应 schema
  └─ 鉴权与下载入口

backend/services/
  ├─ 业务编排
  ├─ 缓存/持久化
  └─ 历史/社区/报告聚合

backend/core/
  ├─ pitch        音高检测
  ├─ rhythm       节拍/节奏
  ├─ separation   音轨分离
  ├─ score        五线谱构建
  ├─ piano        钢琴编配
  ├─ guitar       吉他弹唱谱
  ├─ guzheng      古筝简谱
  ├─ dizi         笛子简谱
  ├─ traditional  民乐简谱 IR
  └─ generation   和弦/变奏生成

backend/db + backend/user + backend/export/
  ├─ 数据库模型与仓储
  ├─ 用户/历史/偏好
  └─ PDF / SVG / MusicXML / jianpu-ly / LilyPond 导出
```

### 2.2 主要功能模块

#### A. 智能识谱模块

- 页面入口：[frontend/transcription.html](/Users/kugua/SeeMusic/frontend/transcription.html)
- 核心用途：上传音频、识别音高、构建乐谱、切换乐器模式、导出结果。
- 当前支持乐器模式：
  - 钢琴
  - 吉他
  - 古筝
  - 笛子

#### B. 歌唱评估模块

- 页面入口：[frontend/singing_evaluation.html](/Users/kugua/SeeMusic/frontend/singing_evaluation.html)
- 核心用途：音准/节奏比较、评分、误差点展示、报告导出。

#### C. 乐谱社区模块

- 页面入口：[frontend/community.html](/Users/kugua/SeeMusic/frontend/community.html)
- 核心用途：浏览社区乐谱、上传社区内容、评论、点赞、收藏、下载。

#### D. 用户中心模块

- 页面入口：[frontend/profile.html](/Users/kugua/SeeMusic/frontend/profile.html)
- 核心用途：查看历史记录、管理偏好、展示用户信息与会话状态。

#### E. 登录注册模块

- 页面入口：[frontend/login.html](/Users/kugua/SeeMusic/frontend/login.html)
- 核心用途：注册、登录、登出、令牌管理。

---

## 3. 模块间调用关系

### 3.1 钢琴识谱主链路

```text
transcription.js
  -> POST /api/v1/score/from-audio
  -> backend/api/api_routes.py
  -> backend/core/score/audio_pipeline.prepare_piano_score_from_audio()
  -> backend/core/score/melody_audio_pipeline.extract_melody_from_audio()
      -> rhythm.detect_beats()
      -> separation.separate_tracks()
      -> pitch.detect_pitch_sequence()
      -> score.key_detection.analyze_key_signature()
  -> backend/core/score/sheet_extraction.build_score_from_pitch_sequence()
      -> backend/core/piano/arrangement.generate_piano_arrangement() [钢琴编配模式]
      -> backend/core/score/musicxml_utils.build_musicxml_from_measures()
  -> 前端 Verovio 预览 / PDF 导出
```

### 3.2 吉他弹唱谱主链路

```text
transcription.js
  -> POST /api/v1/generation/guitar-lead-sheet(-from-audio)
  -> backend/core/guitar/audio_pipeline.generate_guitar_lead_sheet_from_audio()
  -> backend/core/score/melody_audio_pipeline.extract_melody_from_audio()
  -> backend/core/guitar/lead_sheet.generate_guitar_lead_sheet()
  -> 前端 lead sheet 页面 / PDF 导出
```

### 3.3 古筝 / 笛子简谱主链路

```text
transcription.js
  -> POST /api/v1/generation/guzheng-score(-from-audio)
     或 /api/v1/generation/dizi-score(-from-audio)
  -> backend/core/score/melody_audio_pipeline.extract_melody_from_audio()
  -> backend/core/guzheng/notation.generate_guzheng_score_from_pitch_sequence()
     或 backend/core/dizi/notation.generate_dizi_score_from_pitch_sequence()
  -> backend/core/traditional/jianpu_ir.build_jianpu_ir()
  -> backend/export/traditional_export.export_traditional_score()
  -> jianpu-ly + LilyPond 排版
  -> 前端统一简谱预览 / 导出
```

### 3.4 导出链路

```text
前端导出按钮
  -> REST 导出接口
  -> export 模块生成文件
  -> /api/v1/exports/direct-download 附件下载
  -> 浏览器保存 PDF / SVG / jianpu / ly / MIDI / PNG
```

### 3.5 数据持久化链路

```text
API -> services -> db.repositories / db.models
                -> 内存缓存 fallback
```

说明：

- 当数据库可用时，系统落库到 MySQL / SQLite 兼容模型。
- 当数据库不可用时，部分服务退回内存缓存模式，保证基本功能不中断。

---

## 4. 模块间接口设计

### 4.1 前后端接口分类

#### 识谱与分析接口

- `POST /api/v1/pitch/detect`
- `POST /api/v1/pitch/detect-multitrack`
- `POST /api/v1/score/from-pitch-sequence`
- `POST /api/v1/score/from-audio`
- `POST /api/v1/rhythm/beat-detect`
- `POST /api/v1/audio/separate-tracks`
- `POST /api/v1/rhythm/score`
- `POST /api/v1/analyze/rhythm`

#### 钢琴 / 吉他 / 古筝 / 笛子生成接口

- `POST /api/v1/generation/piano-score/export`
- `POST /api/v1/generation/guitar-lead-sheet`
- `POST /api/v1/generation/guitar-lead-sheet-from-audio`
- `POST /api/v1/generation/guitar-lead-sheet/export`
- `POST /api/v1/generation/guzheng-score`
- `POST /api/v1/generation/guzheng-score-from-audio`
- `POST /api/v1/generation/guzheng-score/export`
- `POST /api/v1/generation/dizi-score`
- `POST /api/v1/generation/dizi-score-from-audio`
- `POST /api/v1/generation/dizi-score/export`
- `POST /api/v1/generation/chords`
- `POST /api/v1/generation/variation-suggestions`

#### 乐谱管理与导出记录接口

- `GET /api/v1/scores/{score_id}`
- `PATCH /api/v1/scores/{score_id}`
- `POST /api/v1/scores/{score_id}/undo`
- `POST /api/v1/scores/{score_id}/redo`
- `POST /api/v1/scores/{score_id}/export`
- `GET /api/v1/scores/{score_id}/exports`
- `GET /api/v1/scores/{score_id}/exports/{export_record_id}`
- `POST /api/v1/scores/{score_id}/exports/{export_record_id}/regenerate`
- `GET /api/v1/scores/{score_id}/exports/{export_record_id}/download`
- `GET /api/v1/scores/{score_id}/exports/{export_record_id}/preview`
- `GET /api/v1/exports/direct-download`

#### 社区与用户接口

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/users/me`
- `GET /api/v1/users/me/history`
- `POST /api/v1/users/me/history`
- `DELETE /api/v1/users/me/history/{history_id}`
- `GET /api/v1/users/me/preferences`
- `GET /api/v1/community/scores`
- `GET /api/v1/community/scores/{score_id}`
- `POST /api/v1/community/scores`
- `POST /api/v1/community/scores/upload`
- `GET /api/v1/community/scores/{score_id}/comments`
- `POST /api/v1/community/scores/{score_id}/comments`
- `POST /api/v1/community/scores/{score_id}/download`
- `POST /api/v1/community/scores/{score_id}/like`
- `DELETE /api/v1/community/scores/{score_id}/like`
- `POST /api/v1/community/scores/{score_id}/favorite`
- `DELETE /api/v1/community/scores/{score_id}/favorite`

### 4.2 关键内部接口

| 调用方 | 被调用方 | 作用 |
| --- | --- | --- |
| `api_routes.py` | `prepare_piano_score_from_audio` | 钢琴音频识谱主编排 |
| `prepare_piano_score_from_audio` | `extract_melody_from_audio` | 复用共享旋律提取管线 |
| `extract_melody_from_audio` | `detect_beats / separate_tracks / detect_pitch_sequence` | 节拍、分轨、音高联合分析 |
| `build_score_from_pitch_sequence` | `generate_piano_arrangement` | 钢琴双手简化编配 |
| `generate_guitar_lead_sheet_from_audio` | `generate_guitar_lead_sheet` | 吉他和弦弹唱谱生成 |
| `generate_guzheng_score_from_pitch_sequence` | `build_jianpu_ir` | 古筝简谱中间格式 |
| `generate_dizi_score_from_pitch_sequence` | `build_jianpu_ir` | 笛子简谱中间格式 |
| `export_traditional_score` | `jianpu-ly / LilyPond` | 民乐谱统一排版 |
| `write_score_export` | `Verovio + CairoSVG + PIL` | 五线谱 PNG/PDF/SVG/MIDI 导出 |

---

## 5. 界面设计与典型使用流程

### 5.1 界面设计目标

本系统的人机界面设计遵循“输入清晰、结果直观、导出顺畅、调试可下沉”的原则，重点解决以下问题：

- 让用户在单页内完成上传、识别、预览、导出闭环
- 在多乐器模式下保持统一操作框架，同时允许结果展示方式差异化
- 让“识谱结果”优先于“技术调试信息”
- 兼顾屏幕浏览与打印导出
- 支持从普通用户到开发调试者的不同使用深度

### 5.2 通用界面设计原则

#### 1. 全局布局原则

- 顶部固定品牌区与系统状态区，持续显示当前服务可用性与当前乐谱连接状态
- 中心工作台采用“输入区 - 分析区 - 结果区”三段式布局
- 高价值内容优先展示：
  - 识谱页优先显示乐谱正文或结果预览
  - 调试信息折叠或下沉
- 导出按钮与结果预览放在同一区域，减少用户视线跳转

#### 2. 交互一致性原则

- 所有页面统一使用状态提示条反馈成功、失败与处理中信息
- 所有导出统一通过按钮触发，并返回明确文件类型与文件名反馈
- 乐器模式切换保持同一位置，避免用户频繁重新学习
- 输入数据变化后，优先刷新当前可见结果，而不是额外跳转页面

#### 3. 视觉层次原则

- 一级信息：标题、乐器模式、核心操作按钮、主结果视图
- 二级信息：基础元数据，如调号、拍号、速度、笛型、Capo
- 三级信息：调试信息、分轨信息、候选结果、内部算法提示

#### 4. 响应式与可扩展原则

- 宽屏以三栏工作台为主
- 窄屏下转为纵向堆叠，优先保证输入和正文可读性
- 不同乐器共用页面骨架，但各自挂载专属 renderer

### 5.3 页面层次结构设计

#### 5.3.1 首页

- 页面：[frontend/index.html](/Users/kugua/SeeMusic/frontend/index.html)
- 设计目标：作为全系统导航入口，强调产品定位与四个核心模块入口。
- 页面组成：
  - 品牌标题区
  - 功能入口卡片区
  - 底部版本与版权信息
- 核心交互：
  - 点击模块卡片跳转到对应子系统
  - 支持登录态 / 未登录态两种首页状态

#### 5.3.2 智能识谱页

- 页面：[frontend/transcription.html](/Users/kugua/SeeMusic/frontend/transcription.html)
- 设计目标：在同一页面完成从音频输入到多乐器结果输出的完整闭环。

页面结构：

1. 顶部状态栏  
   作用：显示品牌、页面标题、后端状态、当前乐谱连接状态。

2. 左侧输入面板  
   作用：输入项目标题、速度、拍号、调号、音高序列以及上传音频。  
   组成：
   - 基础信息区
   - 音高序列编辑区
   - 音频识别区
   - 高级分析工具折叠区

3. 中部分析面板  
   作用：显示识别状态、节拍检测、音轨分离、和弦/调性分析结果。

4. 右侧结果面板  
   作用：按乐器模式切换展示：
   - 钢琴：MusicXML/Verovio 五线谱
   - 吉他：lead sheet 弹唱谱正文
   - 古筝：统一排版简谱正文
   - 笛子：统一排版简谱正文

5. 导出与编辑区  
   作用：提供 MusicXML 下载、PDF 下载、传统谱导出、导出记录查看等功能。

#### 5.3.3 歌唱评估页

- 页面：[frontend/singing_evaluation.html](/Users/kugua/SeeMusic/frontend/singing_evaluation.html)
- 设计目标：支持参考音频和用户演唱录音的对比分析。
- 页面组成：
  - 上传区
  - 参数区
  - 对比图表区
  - 评分结果区
  - 报告导出区

#### 5.3.4 社区页

- 页面：[frontend/community.html](/Users/kugua/SeeMusic/frontend/community.html)
- 设计目标：让识谱结果能够被展示、分享、下载和互动。
- 页面组成：
  - 分类与筛选栏
  - 社区卡片流
  - 作品详情弹层/上传面板
  - 评论与互动区

#### 5.3.5 个人中心页

- 页面：[frontend/profile.html](/Users/kugua/SeeMusic/frontend/profile.html)
- 设计目标：集中管理用户个人状态、历史记录和偏好。
- 页面组成：
  - 个人信息卡
  - 安全与会话状态卡
  - 历史看板
  - 偏好设置面板

#### 5.3.6 登录注册页

- 页面：[frontend/login.html](/Users/kugua/SeeMusic/frontend/login.html)
- 设计目标：在轻量页面中完成登录/注册状态切换。
- 页面组成：
  - 品牌返回入口
  - 登录/注册表单
  - 状态提示区
  - 模式切换按钮

### 5.4 智能识谱页的模式化界面设计

智能识谱页是本系统最核心的人机界面，因此采用“统一框架 + 乐器专属结果 renderer”的设计方式。

#### 5.4.1 钢琴模式

- 结果区主视图：五线谱预览
- 辅助区：
  - 精准识谱 / 钢琴编配模式切换
  - MusicXML 编辑区
  - PDF 导出
  - 导出记录面板
- 典型用户：需要得到标准钢琴谱或进行二次编辑的用户

#### 5.4.2 吉他模式

- 结果区主视图：ChordPro / lead sheet 风格弹唱正文
- 辅助区：
  - 调号、Capo、拍号、速度、扫弦建议
  - 常用和弦图
  - 调试面板
  - PDF 导出
- 典型用户：需要直接弹唱、打印或快速伴奏的用户

#### 5.4.3 古筝模式

- 结果区主视图：统一排版的整首连续简谱
- 辅助区：
  - 纯净简谱 / 带标注切换
  - 技法层、弦位层控制
  - jianpu / ly / svg / pdf 导出
  - 调试信息折叠区
- 典型用户：需要民乐简谱阅读、打印与后续润色的用户

#### 5.4.4 笛子模式

- 结果区主视图：统一排版的整首连续简谱
- 辅助区：
  - 笛型选择
  - 纯净简谱 / 带标注切换
  - 指法/孔位标注层
  - jianpu / ly / svg / pdf 导出
- 典型用户：需要按照具体笛型查看可吹奏简谱的用户

### 5.5 典型使用流程

#### 典型流程 A：钢琴识谱

1. 用户进入智能识谱页。
2. 在左侧输入区填写标题、速度、拍号、调号，或直接上传音频。
3. 点击“识别并直接生成乐谱”。
4. 中部分析区显示测速、分轨、定调与主旋律提取过程。
5. 右侧结果区渲染五线谱。
6. 用户可在钢琴模式下切换精准识谱 / 钢琴编配。
7. 用户可下载 MusicXML 或导出 PDF。

#### 典型流程 B：吉他弹唱谱

1. 用户切换到“吉他”模式。
2. 上传音频或保留当前音高序列。
3. 系统提取旋律并推断调号、和弦与扫弦建议。
4. 页面输出正文优先的弹唱谱。
5. 用户查看和弦图、导出 PDF。

#### 典型流程 C：古筝 / 笛子简谱

1. 用户切换到“古筝”或“笛子”模式。
2. 选择是否只看单音简谱或保留标注层。
3. 系统生成简谱 IR，并调用统一排版器。
4. 页面显示整首连续简谱。
5. 用户根据需要导出 jianpu、LilyPond、SVG 或 PDF。

#### 典型流程 D：歌唱评估

1. 用户进入评估页，上传参考音频与用户录音。
2. 系统完成音高与节拍分析。
3. 页面显示评分、误差点和音高曲线。
4. 用户导出分析报告。

#### 典型流程 E：社区分享

1. 用户在社区页浏览现有乐谱。
2. 选择作品查看详情。
3. 进行评论、点赞、收藏、下载。
4. 上传自己的识谱结果到社区。

### 5.6 界面设计特点总结

本系统界面设计具有以下特点：

- 统一工作台风格，便于多模块切换
- 同一输入源可对应多乐器结果输出
- 把“正文阅读体验”和“技术调试体验”分层处理
- 兼顾在线预览、编辑、打印和文件导出
- 让五线谱与简谱在同一产品内具备一致的交互逻辑

---

## 6. 数据库设计

当前数据库模型位于 [backend/db/models.py](/Users/kugua/SeeMusic/backend/db/models.py)。

### 6.1 核心实体

#### 用户域

| 表名 | 作用 | 核心字段 |
| --- | --- | --- |
| `user` | 用户主表 | `id`, `username`, `password`, `nickname`, `email` |
| `user_token` | 登录令牌 | `user_id`, `token`, `expired_time` |
| `user_preference` | 用户偏好 | `user_id`, `preferences` |
| `user_history` | 用户历史记录 | `user_id`, `type`, `resource_id`, `title`, `metadata` |

#### 识谱与项目域

| 表名 | 作用 | 核心字段 |
| --- | --- | --- |
| `project` | 项目主表 | `user_id`, `title`, `audio_url`, `analysis_id`, `status` |
| `audio_analysis` | 音频分析结果 | `analysis_id`, `file_name`, `sample_rate`, `duration`, `bpm`, `params`, `result` |
| `pitch_sequence` | 音高序列表 | `analysis_id`, `time`, `frequency`, `note`, `confidence`, `is_reference` |
| `sheet` | 乐谱主表 | `project_id`, `score_id`, `note_data`, `musicxml`, `bpm`, `key_sign`, `time_sign` |
| `export_record` | 导出记录表 | `project_id`, `format`, `file_url` |
| `report` | 评估报告 | `report_id`, `project_id`, `analysis_id`, `pitch_score`, `rhythm_score`, `total_score`, `metadata` |

#### 社区域

| 表名 | 作用 | 核心字段 |
| --- | --- | --- |
| `community_post` | 社区乐谱帖子 | `community_score_id`, `score_id`, `title`, `author_name`, `instrument`, `tags`, `price` |
| `community_comment` | 社区评论 | `post_id`, `user_id`, `username`, `content` |
| `community_like` | 点赞关系 | `post_id`, `actor_key`, `user_id` |
| `community_favorite` | 收藏关系 | `post_id`, `actor_key`, `user_id` |

### 6.2 主要关系

```text
user
  ├─ 1:N project
  ├─ 1:N audio_analysis
  ├─ 1:N user_history
  ├─ 1:N user_token
  └─ 1:1 user_preference

project
  ├─ 1:N sheet
  ├─ 1:N export_record
  └─ 1:N report

audio_analysis
  └─ 1:N pitch_sequence

sheet
  └─ 0..1 -> community_post

community_post
  ├─ 1:N community_comment
  ├─ 1:N community_like
  └─ 1:N community_favorite
```

### 6.3 数据设计特点

- 识谱结果既有结构化 JSON `note_data`，也有完整 `musicxml`。
- `audio_analysis.result` 允许存放扩展字段，便于多乐器、多算法结果共存。
- `pitch_sequence` 独立建表，支持参考序列与用户序列对比。
- 导出记录与实际导出文件分离，便于重导出、预览与下载。
- 当数据库不可用时，服务层支持内存 fallback，增强可用性。

---

## 7. 关键算法与关键技术

## 7.1 音高检测

- 实现位置：[backend/core/pitch/pitch_detection.py](/Users/kugua/SeeMusic/backend/core/pitch/pitch_detection.py)
- 作用：将音频转换为音高序列。
- 支持：
  - YIN
  - 自相关算法
- 输出字段：
  - 时间
  - 频率
  - 音名
  - 置信度

## 7.2 节拍与速度检测

- 实现位置：[backend/core/rhythm/beat_detection.py](/Users/kugua/SeeMusic/backend/core/rhythm/beat_detection.py)
- 核心能力：
  - 节拍点检测
  - BPM 估计
  - 检测置信度评估
- 系统不是固定用 120 BPM，而是先检测，再根据置信度决定是否采用检测值。

## 7.3 主旋律提取共享管线

- 实现位置：[backend/core/score/melody_audio_pipeline.py](/Users/kugua/SeeMusic/backend/core/score/melody_audio_pipeline.py)
- 核心步骤：
  1. 节拍检测
  2. 音轨分离
  3. 轨道级音高检测
  4. 轨道打分与主旋律轨选择
  5. 混音识别 fallback
  6. 自动判调
  7. 按调重拼音名

该模块是本系统的重要复用点，钢琴、吉他、古筝、笛子都共享这一前半段管线。

## 7.4 自动判调与调内重拼

- 实现位置：[backend/core/score/key_detection.py](/Users/kugua/SeeMusic/backend/core/score/key_detection.py)
- 核心方法：
  - 统计 pitch-class 分布
  - 与大调/小调音级模板做相似度匹配
  - 结合首音、尾音、长音权重做修正
  - 输出 `key_signature / fifths / confidence / candidates`
- 价值：
  - 让五线谱显示正确调号
  - 让古筝、笛子、吉他在调内选择更合理的记谱与和弦

## 7.5 时间量化与可读性清理

- 实现位置：[backend/core/score/sheet_extraction.py](/Users/kugua/SeeMusic/backend/core/score/sheet_extraction.py)
- 核心策略：
  - 秒转拍值
  - 量化到常见时值
  - 删除过短音
  - 吸收极短装饰音
  - 合并相邻同音
  - 修复离群跳音
  - 避免重叠音

这一步直接决定生成谱子的可读性。

## 7.6 钢琴双手简化编配

- 实现位置：[backend/core/piano/arrangement.py](/Users/kugua/SeeMusic/backend/core/piano/arrangement.py)
- 主要策略：
  - 先抽取右手主旋律
  - 将旋律约束在 `C4-C6`
  - 根据和弦推断生成左手低音/和声音壳
  - 控制左右手距离，避免拥挤
  - 提供精准识谱 / 钢琴编配双模式

## 7.7 吉他和弦弹唱谱生成

- 实现位置：[backend/core/guitar/lead_sheet.py](/Users/kugua/SeeMusic/backend/core/guitar/lead_sheet.py)
- 方法特点：
  - 按小节/拍位切分旋律
  - 基于旋律音级分布与段落上下文推断和弦
  - 支持调内和弦、副属和弦、借和弦
  - 使用动态规划做段落级和弦平滑
  - 输出 Capo、和弦图、扫弦建议、lead sheet 正文

## 7.8 古筝 / 笛子简谱统一中间格式

- 实现位置：[backend/core/traditional/jianpu_ir.py](/Users/kugua/SeeMusic/backend/core/traditional/jianpu_ir.py)
- 作用：
  - 统一古筝与笛子的简谱渲染数据结构
  - 将页面预览与打印排版统一到同一份 IR
  - 支持基础层、指法层、技法层、调试层

## 7.9 统一排版导出

- 古筝/笛子：[backend/export/traditional_export.py](/Users/kugua/SeeMusic/backend/export/traditional_export.py)
- 钢琴：[backend/export/export_utils.py](/Users/kugua/SeeMusic/backend/export/export_utils.py), [backend/export/piano_export.py](/Users/kugua/SeeMusic/backend/export/piano_export.py)
- 吉他：[backend/export/guitar_export.py](/Users/kugua/SeeMusic/backend/export/guitar_export.py)

技术路线：

- 钢琴五线谱：MusicXML -> Verovio -> SVG/PNG/PDF/MIDI
- 古筝/笛子简谱：Jianpu IR -> jianpu-ly -> LilyPond -> SVG/PDF/LY/Jianpu
- 吉他弹唱谱：结构化 lead sheet -> ReportLab PDF

---

## 8. 技术创新点

### 8.1 多乐器共享前处理、分乐器专用后处理

系统把“节拍检测、分轨、主旋律提取、判调”抽成共享能力，再按钢琴、吉他、古筝、笛子分别做后处理。这样既减少重复代码，又保留乐器差异化输出。

### 8.2 统一传统简谱 IR

古筝和笛子没有继续各自堆一套前端手工排版，而是统一抽象成 `jianpu_ir`，为统一排版、导出和后续扩展提供稳定中间层。

### 8.3 五线谱与简谱双渲染体系并存

系统同时支持：

- 西洋乐谱体系：MusicXML + Verovio
- 民乐简谱体系：jianpu-ly + LilyPond

这使系统具备跨文化乐谱表达能力。

### 8.4 数据库与内存双运行模式

服务层支持数据库模式与内存 fallback 模式，适合开发阶段、本地调试和数据库短时不可用场景。

### 8.5 直出下载接口统一化

系统对直接导出结果提供统一附件下载接口，避免前端依赖静态存储路径，提高跨端口场景下的下载稳定性。

---

## 9. 结论

SeeMusic 当前已经形成一套相对完整的“音频理解 -> 旋律抽取 -> 乐谱构建 -> 多乐器表达 -> 导出分享”的系统架构。其特点不是只做单一识谱，而是围绕音乐内容生产形成了完整闭环：

- 输入：音频、音高序列、社区乐谱
- 处理：识谱、评估、编配、排版
- 输出：五线谱、弹唱谱、简谱、报告、社区内容

从系统设计角度看，它的核心优势在于：

- 分层清晰
- 共享管线复用度高
- 多乐器输出能力完整
- 导出与社区链路闭环
- 兼顾算法实验与产品化界面

后续如果继续扩展，最适合的方向包括：

- 更强的歌词对齐与段落识别
- 更精细的钢琴/吉他自动编配
- 更多民族乐器支持
- 更完整的打印模板与出版级排版
- 更强的用户协作与社区内容治理
