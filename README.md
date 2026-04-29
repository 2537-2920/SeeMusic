

# 🎵 Music AI System — 智能音频分析与自动扒谱系统

一个基于 AI 的音乐分析系统，支持**音频输入 → 音高识别 → 节奏分析 → 自动生成乐谱 → 智能评估报告**的完整流程，并提供多轨分离、和弦生成与古风/民乐扩展能力。

---

## 🚀 项目简介

本项目旨在构建一个“端到端音乐理解与生成系统”，通过多模块协同，实现：

* 🎤 多模式音频输入（上传 / 麦克风 / 视频提取）
* 🎼 自动扒谱（音频 → 五线谱）
* 🎯 音准与节奏智能评估
* 📊 可视化分析报告（音高曲线 / 错误标注）
* 🎧 多轨分离（人声 / 伴奏）
* 🎶 AI音乐增强（和弦生成 / 变奏建议 / 民乐支持）

---

## 🧠 系统架构

```text
音频输入
   ↓
音高识别（Pitch Detection）
   ↓
节奏分析 / 多轨分离（Rhythm & Separation）
   ↓
乐谱生成（Score Generation）
   ↓
可视化 & AI增强（Visualization & Generation）
   ↓
API输出 / 用户系统 / 导出
```

系统采用**分层架构设计**：

* Core：算法模块（音高 / 节奏 / 乐谱）
* Service：业务整合
* API：对外接口
* User：用户系统与数据管理

> 说明：当前仓库里的 `backend/` 只提供 API 服务，不直接渲染网页。浏览器界面位于 `frontend/` 目录，B 模块的主要入口是 `frontend/transcription.html`。  
> `python backend/main.py` 启动后，`0.0.0.0:8000` 只是监听地址，不是可以直接打开的页面；浏览器里请访问 `http://127.0.0.1:8000` 或 `http://localhost:8000`。

---

## 📁 项目结构

```bash
music-ai-system/
│
├── backend/
│   ├── api/                      # 接口层（人E）
│   │   ├── api_routes.py
│   ├── database/                 #数据库
│   │   ├── models.py
│   │   ├── db.py
│   ├── core/                     # 核心算法层
│   │   ├── pitch/                # 音高相关（人A）
│   │   │   ├── pitch_detection.py
│   │   │   ├── realtime_tuning.py
│   │   │   ├── audio_utils.py
│   │   │
│   │   ├── rhythm/              # 节奏相关（人C）
│   │   │   ├── beat_detection.py
│   │   │   ├── rhythm_analysis.py
│   │   │
│   │   ├── separation/          # 多轨分离（人C）
│   │   │   ├── multi_track_separation.py
│   │   │
│   │   ├── score/               # 扒谱/乐谱（人B）
│   │   │   ├── sheet_extraction.py
│   │   │   ├── note_mapping.py
│   │   │   ├── score_utils.py
│   │   │
│   │   ├── traditional/         # 古风/民乐（人D）
│   │   │   ├── traditional_instruments.py
│   │   │
│   │   ├── generation/          # 生成类功能（人D）
│   │   │   ├── chord_generation.py
│   │   │   ├── variation_suggestions.py
│   │
│   ├── utils/                   # 工具模块（人D）
│   │   ├── audio_logger.py
│   │   ├── data_visualizer.py
│   │
│   ├── services/                # 业务逻辑层（整合各模块）
│   │   ├── analysis_service.py
│   │   ├── score_service.py
│   │   ├── report_service.py
│   │
│   ├── user/                    # 用户系统（人E）
│   │   ├── user_system.py
│   │   ├── history_manager.py
│   │
│   ├── export/                  # 导出模块
│   │   ├── export_utils.py
│   │
│   ├── config/
│   │   ├── settings.py
│   │
│   └── main.py                  # 后端入口
│
├── frontend/                    # 前端静态页面（需单独打开或用静态服务器）
│
├── tests/                       # 测试
│   ├── test_pitch.py
│   ├── test_rhythm.py
│   ├── test_score.py
│
├── requirements.txt
└── README.md
```

---

## ⚙️ 功能模块说明

### 🎧 音频分析

* 音高识别（Pitch Detection）
* 实时音准检测（Realtime Tuning）
* 节奏分析（Beat Detection）
* 多轨分离（Multi- track Separation）

### 🎼 乐谱系统

* 自动扒谱（Audio → Score）
* 音符映射与编辑
* 乐谱导出（PDF / 图片 / MIDI）

### 📊 智能评估

* 音准评分
* 节奏评分
* 错误高亮
* 可视化分析图（音高曲线）

### 🎶 AI扩展能力

* 和弦自动生成
* AI变奏建议
* 古风 / 民乐扒谱支持

### 👤 用户系统

* 注册 / 登录
* 历史记录管理
* 报告存储与导出
* 乐谱社区（上传 / 浏览）

---

## 🧩 核心模块对应

| 模块         | 负责人 | 说明      |
| ---------- | --- | ------- |
| 音高识别       | A   | 提取音高序列  |
| 乐谱生成       | B   | 构建五线谱   |
| 节奏分析 / 分离  | C   | 节拍与音轨   |
| 可视化 / AI扩展 | D   | 图表 + 生成 |
| API / 用户系统 | E   | 系统整合    |

---

## 🛠️ 技术栈（建议）

* Backend：Python / FastAPI（或 Flask）
* Audio Processing：librosa / torchaudio
* ML / AI：PyTorch
* Visualization：matplotlib / plotly
* Frontend：静态 HTML / CSS / JavaScript
* Storage：SQLite / PostgreSQL

---

## ▶️ 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-repo/music-ai-system.git
cd music-ai-system
```

---

### 2. 激活运行环境并安装依赖

```bash
conda activate SeeMusic
pip install -r requirements.txt
```

---

### 3. 启动后端 API

```bash
bash scripts/start_backend.sh
```

脚本会优先使用仓库里的 `./.venv/bin/python`，找不到时再回退到系统 `python3`。
如果你想手动启动，也可以直接运行：

```bash
./.venv/bin/python backend/main.py
```

或者：

```bash
python3 backend/main.py
```

后端默认监听 `8000` 端口。启动后建议立刻做一次健康检查：

```bash
bash scripts/check_backend_health.sh
```

手动检查也可以，下面两个地址都会返回 `{"status":"ok"}`：

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/api/v1/health
```

---

### 4. 打开前端界面

推荐直接启动一个静态服务器，然后打开前端页面：

```bash
python3 -m http.server 5173 --directory frontend
```

注意：

* 前端静态服务器请用 `5173` 或其他空闲端口，不要占用 `8000`
* `8000` 已留给后端 API 服务使用
* 如果页面右上角的健康检查显示离线，先检查 API base 是否仍然是 `http://127.0.0.1:8000/api/v1`
* 如果你之前打开过旧版本页面，建议先强制刷新一次，或者清掉浏览器里 `seemusic.transcription.apiBase` 这条本地缓存

然后在浏览器中打开：

```text
http://127.0.0.1:5173/index.html
```

如果你只负责B模块，直接打开：

```text
http://127.0.0.1:5173/transcription.html
```

前端页面默认读取的 API base 是：

```text
http://127.0.0.1:8000/api/v1
```

你也可以在页面里手动修改 API base，再点击 `Save`。

---

### 5. 调用接口

后端提供的是 API，而不是网页首页。常用接口示例：

```bash
# 音频分析整体
POST /analyze

# 多轨分离（新增功能）
POST /api/v1/audio/separate-tracks

# 歌唱评估：标准音频先分离人声，再与用户音频对比
POST /api/v1/singing/evaluate
```

上传音频文件示例：

```bash
# 基础分析
curl -X POST http://localhost:8000/analyze \
  -F "file=@song.mp3"

# 多轨分离 - 4轨（人声+鼓+贝司+其他）
curl -X POST http://localhost:8000/api/v1/audio/separate-tracks \
  -F "file=@song.mp3" \
  -F "stems=4"

# 多轨分离 - 6轨（完整乐器分离）
curl -X POST http://localhost:8000/api/v1/audio/separate-tracks \
  -F "file=@song.mp3" \
  -F "stems=6"

# 歌唱评估 - 用户清唱版本
curl -X POST http://localhost:8000/api/v1/singing/evaluate \
  -F "reference_audio=@standard_with_accompaniment.wav" \
  -F "user_audio=@user_a_cappella.wav" \
  -F "user_audio_mode=a_cappella"

# 歌唱评估 - 用户带伴奏版本（用户音频也会先分离人声）
curl -X POST http://localhost:8000/api/v1/singing/evaluate \
  -F "reference_audio=@standard_with_accompaniment.wav" \
  -F "user_audio=@user_with_accompaniment.wav" \
  -F "user_audio_mode=with_accompaniment"
```

返回数据示例：

* 音高数据
* 节奏数据
* 乐谱结构
* 可视化分析结果
* 分离的音频轨道 
* 歌唱评估的节奏得分、音高对比结果、综合分数


---

## 🧪 测试

```bash
pytest tests/
```

### 缓存清理

开发和测试过程中会生成 `__pycache__/`、`.pytest_cache/`、`*.pyc` 等缓存文件，这些文件不应提交到仓库。

```bash
bash scripts/clean_cache.sh
```

清理策略：

* 通过 `.gitignore` 统一忽略 Python 缓存、测试缓存、覆盖率产物、本地环境目录和运行时 `storage/`
* 通过 `scripts/clean_cache.sh` 做一次性清理，适合本地开发和提交前执行
* CI 只安装依赖并跑测试，不缓存仓库内的 Python 编译产物

---

## 📦 开发阶段

### 阶段一（核心功能）

* 音高识别
* 节奏检测
* 自动扒谱
* API打通

👉 目标：系统可运行

---

### 阶段二（功能增强）

* 多轨分离
* 和弦生成
* 民乐支持
* 报告与导出优化

👉 目标：产品级体验

---

## 📌 亮点

* 🎯 端到端音乐理解 pipeline
* 🧠 多模块 AI 协同（音高 / 节奏 / 乐谱）
* 🔄 可扩展架构（支持更多音乐风格）
* 🎨 数据可视化 + AI生成结合
* 🧩 工程化设计（Service解耦）

---

## ⚠️ 风险与限制

* 多音轨复杂音频识别精度有限
* 民乐音色建模仍需优化
* 实时处理对性能要求较高

---

## 📈 未来规划

* 支持更多音乐风格（Jazz / EDM）
* 引入大模型进行音乐理解
* Web端实时交互编辑器
* 社区化音乐创作平台

---

## 👥 团队

* A：音高识别与音准分析
* B：乐谱生成与编辑
* C：节奏分析与多轨分离
* D：可视化与AI扩展
* E：系统接口与用户系统
