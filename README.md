

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
│   │
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
* **多轨分离（Multi-track Separation）** ✨ **[完整实现]**
  - 支持2、4、5、6轨分离
  - 人声 + 伴奏分离
  - 人声 + 鼓 + 贝司 + 其他
  - 人声 + 鼓 + 贝司 + 吉他 + 钢琴 + 其他
  - 单轨WAV文件输出
  - API: `POST /api/v1/audio/separate-tracks`
  - 详见: [多轨分离完整文档](./AUDIO_SEPARATION_IMPLEMENTATION.md)

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
python backend/main.py
```

---

### 4. 打开前端界面

推荐直接启动一个静态服务器，然后打开前端页面：

```bash
python -m http.server 5173 --directory frontend
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
```

返回数据示例：

* 音高数据
* 节奏数据
* 乐谱结构
* 可视化分析结果
* **分离的音频轨道** (多轨分离功能)

---

## 🎯 多轨分离快速入门

已完整实现多轨音频分离功能，支持人声、鼓、贝司、吉他、钢琴等多种乐器分离。

### 使用示例

```python
from backend.core.separation.multi_track_separation import separate_tracks

# 读取音频
with open("song.mp3", "rb") as f:
    audio_bytes = f.read()

# 执行4轨分离
result = separate_tracks(
    file_name="song.mp3",
    model="demucs",
    stems=4,
    audio_bytes=audio_bytes
)

# 获取分离结果
for track in result['tracks']:
    print(f"轨道: {track['name']}")
    print(f"文件: {track['file_path']}")
    print(f"时长: {track['duration']}秒")

print(result["backend_used"])   # "demucs" or "simple"
print(result["fallback_used"])  # True when Demucs failed and simple separation was used
print(result["warnings"])       # Failure reason when fallback happened
```

### 支持的分离模式

| 轨道数 | 分离范围 | 适用场景 |
|-------|--------|--------|
| 2 | 人声 + 伴奏 | 快速分离 |
| 4 | + 鼓 + 贝司 | 通用编辑 |
| 5 | + 钢琴 | 详细编辑 |
| 6 | + 吉他 | 完整分离 |

### Demucs 权重缓存与离线预置

项目里的 Demucs 默认按下面的顺序找权重：

1. 本地离线 repo：`storage/demucs-repo/`
2. Torch 缓存：`storage/.cache/torch/hub/checkpoints/`
3. 在线下载

可选环境变量：

```bash
export DEMUCS_REPO_DIR=/absolute/path/to/demucs-repo
export DEMUCS_CACHE_DIR=/absolute/path/to/demucs-cache
export DEMUCS_MODEL_NAME=htdemucs
```

默认模型 `htdemucs` 对应的官方权重文件名是：

```text
955717e8-8726e21a.th
```

离线运行有两种推荐方式。

方式一：预置 Torch 缓存文件

```bash
mkdir -p storage/.cache/torch/hub/checkpoints
cp 955717e8-8726e21a.th storage/.cache/torch/hub/checkpoints/
```

这种方式不需要改代码，Demucs 会直接命中本地缓存。

方式二：预置本地离线 repo

```bash
mkdir -p storage/demucs-repo
cp 955717e8-8726e21a.th storage/demucs-repo/
```

代码会自动从已安装的 `demucs` 包里补齐 `htdemucs.yaml`，然后以本地 repo 模式加载，不再依赖联网下载。

如果你想手工完整准备 repo，目录应当像这样：

```text
storage/demucs-repo/
├── htdemucs.yaml
└── 955717e8-8726e21a.th
```

### Demucs 失败排查

如果返回结果里出现：

```json
{
  "backend_used": "simple",
  "fallback_used": true
}
```

说明请求虽然写的是 `model=demucs`，但实际并没有成功跑到 Demucs，而是回退到了简化分离逻辑。此时优先检查：

1. `storage/.cache/torch/hub/checkpoints/955717e8-8726e21a.th` 是否存在
2. `storage/demucs-repo/955717e8-8726e21a.th` 是否存在
3. 当前运行环境是否能解析 `dl.fbaipublicfiles.com`
4. 返回的 `warnings` 字段里是否有具体错误

### 更多信息

- 📖 [详细实现文档](./AUDIO_SEPARATION_IMPLEMENTATION.md)
- 🚀 [快速使用指南](./AUDIO_SEPARATION_QUICKSTART.md)
- ✅ [完成总结](./COMPLETION_SUMMARY.md)

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
