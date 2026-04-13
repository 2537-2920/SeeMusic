# Music AI System API 接口文档

> 说明：本文档基于当前 `README.md` 的工程结构与题目中给出的 A-E 功能清单整理，采用统一的 REST 风格接口设计。  
> 若你们项目后续已经确定了真实路由名，可以直接把本文档中的路径替换成实际实现。

## 1. 通用约定

### 1.1 基础地址

```text
/api/v1
```

### 1.2 数据格式

* 请求体：`application/json`
* 文件上传：`multipart/form-data`
* 响应体：`application/json`

### 1.3 通用请求头

```http
Content-Type: application/json
Authorization: Bearer <token>
```

### 1.4 通用响应结构

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 1.5 通用状态码

| HTTP 状态码 | 含义 |
| --- | --- |
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未登录或 Token 无效 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 422 | 参数校验失败 |
| 500 | 服务器内部错误 |

---

## 2. A 模块：音高识别与对比

### 2.1 音频上传音高检测

**接口用途**：上传音频，返回音高时间序列。

* `POST /api/v1/pitch/detect`

#### 请求方式

`multipart/form-data`

#### 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | 音频文件，支持 wav/mp3/flac |
| sample_rate | int | 否 | 采样率，不传则按文件原始采样率 |
| frame_ms | int | 否 | 分析帧长，默认 20ms |
| hop_ms | int | 否 | 帧移，默认 10ms |
| algorithm | string | 否 | 算法名，如 `yin`、`crepe` |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "analysis_id": "an_202604110001",
    "duration": 123.45,
    "pitch_sequence": [
      {
        "time": 0.00,
        "frequency": 440.0,
        "note": "A4",
        "confidence": 0.98
      },
      {
        "time": 0.01,
        "frequency": 442.1,
        "note": "A4",
        "confidence": 0.96
      }
    ]
  }
}
```

---

### 2.2 实时音准检测

**接口用途**：麦克风实时输入，返回实时音高与偏差。

* `WS /api/v1/ws/realtime-pitch`

#### 连接说明

建立 WebSocket 后，客户端持续发送音频帧，服务端实时返回识别结果。

#### 客户端发送示例

```json
{
  "type": "audio_frame",
  "sample_rate": 16000,
  "pcm": "base64-encoded-audio-bytes"
}
```

#### 服务端返回示例

```json
{
  "type": "pitch_update",
  "time": 12.36,
  "frequency": 438.2,
  "note": "A4",
  "cents_offset": -7.5,
  "confidence": 0.95
}
```

#### 停止消息

```json
{
  "type": "stop"
}
```

---

### 2.3 音高对比数据接口

**接口用途**：返回原唱与用户音高对比数据，供前端可视化。

* `POST /api/v1/pitch/compare`

#### 请求参数

```json
{
  "reference_id": "ref_001",
  "user_recording_id": "rec_001",
  "range": {
    "start_time": 0,
    "end_time": 120
  }
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "reference": [
      { "time": 0.0, "frequency": 440.0, "note": "A4" }
    ],
    "user": [
      { "time": 0.0, "frequency": 438.0, "note": "A4" }
    ],
    "deviation": [
      { "time": 0.0, "cents_offset": -8.0 }
    ],
    "summary": {
      "accuracy": 92.3,
      "average_deviation": -3.6
    }
  }
}
```

---

## 3. B ??????????

### 3.1 ???????

**????**??????????????? `project + sheet` ????????????

* `POST /api/v1/score/from-pitch-sequence`

#### ????

```json
{
  "user_id": 1,
  "title": "??????",
  "analysis_id": "an_202604110001",
  "tempo": 120,
  "time_signature": "4/4",
  "key_signature": "C",
  "pitch_sequence": [
    {
      "time": 0.0,
      "frequency": 440.0,
      "duration": 0.5
    }
  ]
}
```

#### ????

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "project_id": 12,
    "score_id": "score_1001",
    "title": "??????",
    "tempo": 120,
    "time_signature": "4/4",
    "key_signature": "C",
    "version": 1,
    "measures": [
      {
        "measure_no": 1,
        "notes": [
          {
            "pitch": "A4",
            "duration": "quarter",
            "start_beat": 1
          }
        ]
      }
    ]
  }
}
```

---

### 3.2 ??????

**????**????????????????? / ???

* `PATCH /api/v1/scores/{score_id}`
* `POST /api/v1/scores/{score_id}/undo`
* `POST /api/v1/scores/{score_id}/redo`

#### ??????

```json
{
  "operations": [
    {
      "type": "add_note",
      "measure_no": 1,
      "beat": 2,
      "note": {
        "pitch": "E4",
        "duration": "eighth"
      }
    },
    {
      "type": "update_time_signature",
      "value": "3/4"
    }
  ]
}
```

---

### 3.3 ??????

**????**??? `MIDI / PNG / PDF` ???????? `export_record` ???

* `POST /api/v1/scores/{score_id}/export`

#### ????

```json
{
  "format": "pdf",
  "page_size": "A4",
  "with_annotations": true
}
```

#### ????

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "project_id": 12,
    "export_record_id": 8,
    "score_id": "score_1001",
    "format": "pdf",
    "file_name": "score_1001_export_8.pdf",
    "download_url": "/storage/exports/score_1001_export_8.pdf",
    "detail_url": "/api/v1/scores/score_1001/exports/8",
    "preview_url": "/api/v1/scores/score_1001/exports/8/preview",
    "download_api_url": "/api/v1/scores/score_1001/exports/8/download",
    "regenerate_url": "/api/v1/scores/score_1001/exports/8/regenerate",
    "delete_url": "/api/v1/scores/score_1001/exports/8",
    "content_type": "application/pdf",
    "exists": true,
    "size_bytes": 40960,
    "manifest": {
      "kind": "pdf",
      "page_size": "A4",
      "with_annotations": true
    }
  }
}
```

---

### 3.4 ?????????

**????**??????????????????????????

* `GET /api/v1/scores/{score_id}/exports`
* `GET /api/v1/scores/{score_id}/exports/{export_record_id}`

#### ??????

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "score_id": "score_1001",
    "project_id": 12,
    "count": 2,
    "items": [
      {
        "export_record_id": 9,
        "format": "png",
        "file_name": "score_1001_export_9.png",
        "download_url": "/storage/exports/score_1001_export_9.png",
        "preview_url": "/api/v1/scores/score_1001/exports/9/preview",
        "download_api_url": "/api/v1/scores/score_1001/exports/9/download",
        "regenerate_url": "/api/v1/scores/score_1001/exports/9/regenerate",
        "delete_url": "/api/v1/scores/score_1001/exports/9",
        "content_type": "image/png",
        "exists": true,
        "size_bytes": 182340
      }
    ]
  }
}
```

---

### 3.5 ?????????

**????**????????????

* `GET /api/v1/scores/{score_id}/exports/{export_record_id}/download`
* `GET /api/v1/scores/{score_id}/exports/{export_record_id}/preview`

#### ??

* `download`??????????`Content-Disposition: attachment`
* `preview`?? `pdf/png/jpg/webp/gif/text` ????????????????

---

### 3.6 ???????????

**????**????? `export_record` ???????????????????

* `POST /api/v1/scores/{score_id}/exports/{export_record_id}/regenerate`
* `DELETE /api/v1/scores/{score_id}/exports/{export_record_id}`

#### ????????

```json
{
  "page_size": "LETTER",
  "with_annotations": false
}
```

#### ????????

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "project_id": 12,
    "export_record_id": 8,
    "format": "pdf",
    "file_name": "score_1001_export_8.pdf",
    "regenerated": true,
    "download_url": "/storage/exports/score_1001_export_8.pdf",
    "manifest": {
      "kind": "pdf",
      "page_size": "LETTER",
      "with_annotations": false
    }
  }
}
```

#### ??????

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "score_id": "score_1001",
    "project_id": 12,
    "export_record_id": 9,
    "format": "png",
    "file_name": "score_1001_export_9.png",
    "deleted": true,
    "file_deleted": true
  }
}
```

---

## 4. C 模块：节奏、多轨与社区

### 4.1 节拍检测接口

**接口用途**：输入音频，返回节拍时间点。

* `POST /api/v1/rhythm/beat-detect`

#### 请求参数

`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | 音频文件 |
| bpm_hint | int | 否 | 参考 BPM |
| sensitivity | float | 否 | 节拍敏感度 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "bpm": 128.4,
    "beat_times": [0.48, 0.95, 1.42, 1.89]
  }
}
```

---

### 4.2 多轨分离接口

**接口用途**：输入音频，分离人声 / 伴奏，返回多轨。

* `POST /api/v1/audio/separate-tracks`

#### 请求参数

`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file | file | 是 | 音频文件 |
| model | string | 否 | 分离模型，如 `demucs` |
| stems | int | 否 | 输出轨道数 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "sep_001",
    "tracks": [
      {
        "name": "vocal",
        "download_url": "https://example.com/vocal.wav"
      },
      {
        "name": "accompaniment",
        "download_url": "https://example.com/accompaniment.wav"
      }
    ]
  }
}
```

---

### 4.3 节奏评分接口

**接口用途**：输入用户节奏，返回评分与错误点。

* `POST /api/v1/rhythm/score`

#### 请求参数

```json
{
  "reference_beats": [0.5, 1.0, 1.5, 2.0],
  "user_beats": [0.52, 1.08, 1.47, 2.12]
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "score": 91,
    "errors": [
      {
        "time": 1.08,
        "deviation_ms": 80,
        "level": "slight"
      }
    ]
  }
}
```

---

### 4.4 乐谱列表

**接口用途**：获取社区乐谱列表。

* `GET /api/v1/community/scores`

#### 查询参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |
| keyword | string | 否 | 关键词搜索 |
| tag | string | 否 | 标签筛选 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 128,
    "items": [
      {
        "score_id": "score_1001",
        "title": "夜曲",
        "author": "user_01",
        "likes": 56,
        "favorites": 24
      }
    ]
  }
}
```

---

### 4.5 乐谱发布

**接口用途**：发布乐谱到社区。

* `POST /api/v1/community/scores`

#### 请求参数

```json
{
  "score_id": "score_1001",
  "title": "夜曲",
  "description": "根据音频自动扒谱生成",
  "tags": ["流行", "钢琴"],
  "is_public": true
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "community_score_id": "cmt_2001",
    "published_at": "2026-04-11T10:30:00+08:00"
  }
}
```

---

### 4.6 乐谱点赞 / 收藏

**接口用途**：社区互动。

* `POST /api/v1/community/scores/{id}/like`
* `DELETE /api/v1/community/scores/{id}/like`
* `POST /api/v1/community/scores/{id}/favorite`
* `DELETE /api/v1/community/scores/{id}/favorite`

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "liked": true,
    "favorited": false
  }
}
```

---

## 5. D 模块：日志、可视化与 AI 增强

### 5.1 音频日志接口

**接口用途**：记录采样率、时长、参数。

* `POST /api/v1/logs/audio`

#### 请求参数

```json
{
  "file_name": "demo.wav",
  "sample_rate": 16000,
  "duration": 123.45,
  "params": {
    "frame_ms": 20,
    "hop_ms": 10,
    "algorithm": "yin"
  }
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "log_id": "log_001"
  }
}
```

---

### 5.2 音高曲线图接口

**接口用途**：返回对比图数据，供前端渲染。

* `GET /api/v1/charts/pitch-curve`

#### 查询参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| analysis_id | string | 是 | 分析任务 ID |
| mode | string | 否 | 图表模式，如 `compare`、`single` |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "x_axis": [0, 1, 2, 3],
    "reference_curve": [440, 442, 438, 440],
    "user_curve": [438, 439, 440, 441],
    "deviation_curve": [-2, -3, 2, 1]
  }
}
```

---

### 5.3 和弦生成接口

**接口用途**：返回和弦序列。

* `POST /api/v1/generation/chords`

#### 请求参数

```json
{
  "key": "C",
  "tempo": 120,
  "style": "pop",
  "melody": [
    { "time": 0.0, "note": "C4" }
  ]
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "chords": [
      { "time": 0.0, "symbol": "Cmaj7" },
      { "time": 2.0, "symbol": "Am7" }
    ]
  }
}
```

---

### 5.4 AI 变奏建议接口

**接口用途**：返回变奏方案。

* `POST /api/v1/generation/variation-suggestions`

#### 请求参数

```json
{
  "score_id": "score_1001",
  "style": "traditional",
  "difficulty": "medium"
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "suggestions": [
      {
        "type": "rhythm_change",
        "description": "将第 2 小节节奏改为切分音"
      }
    ]
  }
}
```

---

## 6. E 模块：用户与数据管理

### 6.1 用户注册

**接口用途**：注册账号。

* `POST /api/v1/auth/register`

#### 请求参数

```json
{
  "username": "alice",
  "password": "12345678",
  "email": "alice@example.com"
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "u_1001"
  }
}
```

---

### 6.2 用户登录

**接口用途**：登录并返回 Token。

* `POST /api/v1/auth/login`

#### 请求参数

```json
{
  "username": "alice",
  "password": "12345678"
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 7200,
    "user": {
      "user_id": "u_1001",
      "username": "alice"
    }
  }
}
```

---

### 6.3 个人中心

**接口用途**：获取用户信息。

* `GET /api/v1/users/me`

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "u_1001",
    "username": "alice",
    "email": "alice@example.com",
    "avatar": "https://example.com/avatar.png",
    "created_at": "2026-04-01T12:00:00+08:00"
  }
}
```

---

### 6.4 历史记录管理

**接口用途**：保存、查询、删除历史乐谱与音频。

* `GET /api/v1/users/me/history`
* `POST /api/v1/users/me/history`
* `DELETE /api/v1/users/me/history/{history_id}`

#### 保存请求示例

```json
{
  "type": "score",
  "resource_id": "score_1001",
  "title": "夜曲",
  "metadata": {
    "source": "auto_generated"
  }
}
```

#### 查询响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "history_id": "h_001",
        "type": "audio",
        "resource_id": "an_202604110001",
        "title": "练习录音",
        "created_at": "2026-04-11T09:00:00+08:00"
      }
    ]
  }
}
```

---

### 6.5 导出报告接口

**接口用途**：导出练习报告、MIDI、PDF、图片。

* `POST /api/v1/reports/export`

#### 请求参数

```json
{
  "analysis_id": "an_202604110001",
  "formats": ["pdf", "midi", "png"],
  "include_charts": true
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "report_id": "r_001",
    "files": [
      {
        "format": "pdf",
        "download_url": "https://example.com/report.pdf"
      }
    ]
  }
}
```

---

## 7. 统一错误返回

```json
{
  "code": 40001,
  "message": "参数错误",
  "data": {
    "field": "file",
    "reason": "音频文件不能为空"
  }
}
```

### 常见业务错误码

| 错误码 | 说明 |
| --- | --- |
| 40001 | 参数错误 |
| 40002 | 文件格式不支持 |
| 40003 | 文件过大 |
| 40101 | Token 失效 |
| 40102 | 未登录 |
| 40301 | 无操作权限 |
| 40401 | 资源不存在 |
| 50001 | 算法处理失败 |
| 50002 | 文件导出失败 |

---

## 8. ??????

| ?? | ?? |
| --- | --- |
| A ???? | `/pitch/detect`?`/ws/realtime-pitch`?`/pitch/compare` |
| B ????? | `/score/from-pitch-sequence`?`/scores/{id}`?`/scores/{id}/undo`?`/scores/{id}/redo`?`/scores/{id}/export`?`/scores/{id}/exports`?`/scores/{id}/exports/{export_record_id}`?`/scores/{id}/exports/{export_record_id}/preview`?`/scores/{id}/exports/{export_record_id}/download`?`/scores/{id}/exports/{export_record_id}/regenerate`?`DELETE /scores/{id}/exports/{export_record_id}` |
| C ????? | `/rhythm/beat-detect`?`/audio/separate-tracks`?`/rhythm/score`?`/community/scores` |
| D ????? | `/logs/audio`?`/charts/pitch-curve`?`/generation/chords`?`/generation/variation-suggestions` |
| E ????? | `/auth/register`?`/auth/login`?`/users/me`?`/users/me/history`?`/reports/export` |

---

## 9. 备注

1. 实时音准检测更适合使用 WebSocket；如果后端最终选用 SSE 或长连接轮询，可以保持数据结构不变，仅替换传输方式。
2. 音频文件上传类接口建议统一返回 `analysis_id` 或 `task_id`，便于前端后续查询任务状态。
3. 导出类接口建议支持异步任务，文件生成完成后再返回下载地址。
4. 如果后续需要，我可以继续把这份文档整理成 OpenAPI 3.0 / Swagger 版本。


## 10. ??????

?????????????????????????????? `frontend/export_panel_integration.md`?
