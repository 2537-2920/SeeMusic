# 导出记录面板接入说明

适用页面：`frontend/transcription.html` 对应的乐谱编辑/导出区域。

## 1. 面板目标

导出记录面板负责展示某个 `score_id` 的历史导出文件，并提供这些操作：

1. 查看导出历史列表
2. 查看单条导出记录详情
3. 在线预览 PDF / 图片
4. 下载导出文件
5. 重新导出已有记录
6. 删除导出记录

后端已经支持以上能力，前端只需要围绕 `score_id` 和 `export_record_id` 做状态管理。

---

## 2. 推荐面板状态

前端建议维护这一组状态：

```js
const exportPanelState = {
  scoreId: "",
  loading: false,
  refreshing: false,
  list: [],
  selectedExportRecordId: null,
  selectedDetail: null,
  error: "",
};
```

字段含义：

- `scoreId`: 当前乐谱 ID
- `loading`: 首次打开面板时的加载状态
- `refreshing`: 执行重新导出 / 删除后刷新列表时的状态
- `list`: 导出记录列表
- `selectedExportRecordId`: 当前高亮的导出记录
- `selectedDetail`: 当前右侧详情区或预览区数据
- `error`: 面板级错误提示

---

## 3. 后端返回结构

### 3.1 列表接口

`GET /api/v1/scores/{score_id}/exports`

响应结构：

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
        "project_id": 12,
        "score_id": "score_1001",
        "format": "png",
        "file_name": "score_1001_export_9.png",
        "file_path": "D:/SeeMusic/storage/exports/score_1001_export_9.png",
        "download_url": "/storage/exports/score_1001_export_9.png",
        "detail_url": "/api/v1/scores/score_1001/exports/9",
        "preview_url": "/api/v1/scores/score_1001/exports/9/preview",
        "download_api_url": "/api/v1/scores/score_1001/exports/9/download",
        "regenerate_url": "/api/v1/scores/score_1001/exports/9/regenerate",
        "delete_url": "/api/v1/scores/score_1001/exports/9",
        "content_type": "image/png",
        "exists": true,
        "size_bytes": 182340,
        "created_at": "2026-04-12T14:10:20",
        "updated_at": "2026-04-12T14:10:20"
      }
    ]
  }
}
```

### 3.2 单条详情接口

`GET /api/v1/scores/{score_id}/exports/{export_record_id}`

返回字段和列表项一致，适合点选某条记录后刷新右侧详情。

### 3.3 重新导出接口

`POST /api/v1/scores/{score_id}/exports/{export_record_id}/regenerate`

请求体：

```json
{
  "page_size": "LETTER",
  "with_annotations": false
}
```

返回结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "project_id": 12,
    "export_record_id": 9,
    "score_id": "score_1001",
    "format": "png",
    "file_name": "score_1001_export_9.png",
    "download_url": "/storage/exports/score_1001_export_9.png",
    "preview_url": "/api/v1/scores/score_1001/exports/9/preview",
    "download_api_url": "/api/v1/scores/score_1001/exports/9/download",
    "regenerate_url": "/api/v1/scores/score_1001/exports/9/regenerate",
    "delete_url": "/api/v1/scores/score_1001/exports/9",
    "content_type": "image/png",
    "exists": true,
    "size_bytes": 185000,
    "regenerated": true,
    "manifest": {
      "kind": "png",
      "page_size": "LETTER",
      "with_annotations": false
    }
  }
}
```

### 3.4 删除接口

`DELETE /api/v1/scores/{score_id}/exports/{export_record_id}`

返回结构：

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

## 4. 前端推荐字段映射

列表项推荐这样显示：

- 标题：`file_name`
- 副标题：`format.toUpperCase()` + `created_at`
- 标签：`content_type`、`size_bytes`
- 状态：
  - `exists === true` 显示“可预览/可下载”
  - `exists === false` 显示“文件缺失”

按钮显隐建议：

- `预览`：仅当 `content_type` 以 `application/pdf` 或 `image/` 开头时展示
- `下载`：`exists === true` 时展示
- `重新导出`：始终可展示
- `删除`：始终可展示，但建议二次确认

---

## 5. 推荐调用顺序

### 场景 A：首次打开导出面板

1. 页面拿到当前 `score_id`
2. 调用 `GET /api/v1/scores/{score_id}/exports`
3. 列表按接口返回顺序直接显示
4. 默认选中第 1 条 `items[0]`
5. 调用 `GET /api/v1/scores/{score_id}/exports/{export_record_id}`
6. 用详情填充右侧信息区和预览区

### 场景 B：用户点击某条导出记录

1. 更新 `selectedExportRecordId`
2. 调用详情接口
3. 根据 `content_type` 决定渲染方式

### 场景 C：用户点击预览

不要直接拼接本地 `file_path`，一律使用接口返回的 `preview_url`。

渲染建议：

- `application/pdf`: 用 `<iframe>` 或 `<object>`
- `image/png` / `image/jpeg` / `image/webp` / `image/gif`: 用 `<img>`
- `audio/midi` 或其他不可内联类型：显示“当前格式不支持在线预览，请下载查看”

### 场景 D：用户点击下载

优先使用 `download_api_url`，而不是直接拼接 `/storage/...`。

原因：

- 以后后端如果增加鉴权或签名下载，前端不需要改调用方式
- `download_api_url` 明确返回附件响应

### 场景 E：用户点击重新导出

1. 弹出参数选择框
2. 让用户选择：
   - `page_size`: `A4` / `LETTER`
   - `with_annotations`: `true` / `false`
3. 调用 `POST /regenerate`
4. 成功后刷新：
   - 当前详情
   - 列表
5. 保持当前 `selectedExportRecordId` 不变

### 场景 F：用户点击删除

1. 弹出二次确认
2. 调用 `DELETE /api/v1/scores/{score_id}/exports/{export_record_id}`
3. 删除成功后刷新列表
4. 如果删掉的是当前选中项：
   - 若列表还有数据，自动选中新的第 1 条
   - 若列表为空，清空详情区和预览区

---

## 6. 推荐前端封装

### 6.1 建议的数据类型

```js
/** @typedef {Object} ExportRecordItem
 *  @property {number} export_record_id
 *  @property {number} project_id
 *  @property {string} score_id
 *  @property {'midi'|'png'|'pdf'} format
 *  @property {string|null} file_name
 *  @property {string|null} download_url
 *  @property {string} detail_url
 *  @property {string} preview_url
 *  @property {string} download_api_url
 *  @property {string} regenerate_url
 *  @property {string} delete_url
 *  @property {string} content_type
 *  @property {boolean} exists
 *  @property {number} size_bytes
 *  @property {string|null} created_at
 *  @property {string|null} updated_at
 */
```

### 6.2 建议的 API 封装函数

```js
async function apiGetExportList(scoreId) {}
async function apiGetExportDetail(scoreId, exportRecordId) {}
async function apiRegenerateExport(scoreId, exportRecordId, payload) {}
async function apiDeleteExport(scoreId, exportRecordId) {}
```

### 6.3 推荐的面板加载主流程

```js
async function openExportPanel(scoreId) {
  exportPanelState.scoreId = scoreId;
  exportPanelState.loading = true;
  exportPanelState.error = '';

  try {
    const listData = await apiGetExportList(scoreId);
    exportPanelState.list = listData.items;

    if (listData.items.length > 0) {
      const first = listData.items[0];
      exportPanelState.selectedExportRecordId = first.export_record_id;
      exportPanelState.selectedDetail = await apiGetExportDetail(scoreId, first.export_record_id);
    } else {
      exportPanelState.selectedExportRecordId = null;
      exportPanelState.selectedDetail = null;
    }
  } catch (error) {
    exportPanelState.error = error.message || '导出记录加载失败';
  } finally {
    exportPanelState.loading = false;
  }
}
```

---

## 7. 推荐的 UI 状态

### 7.1 空状态

当 `count === 0` 时显示：

- 标题：`暂无导出记录`
- 说明：`先导出一次 PDF、PNG 或 MIDI，这里就会出现历史记录。`

### 7.2 错误状态

建议统一显示后端 `detail` 或 `message`：

- 404：`导出记录不存在或已被删除`
- 400/500：`导出失败，请稍后重试`

### 7.3 处理中状态

- 重新导出时，锁定当前行按钮并显示 `重新生成中...`
- 删除时，锁定当前行按钮并显示 `删除中...`

---

## 8. 接入建议

如果你们下一步要把它接到 `frontend/transcription.js`，建议按这个顺序落地：

1. 先把导出记录列表渲染出来
2. 再接详情切换和预览区
3. 然后接下载按钮
4. 最后接重新导出和删除

这样做的好处是：

- 最先就能看到历史数据
- 下载/预览链路最容易验证
- 删除/重新导出属于“修改型操作”，放最后接更稳
