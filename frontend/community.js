const {
    requestJson,
    getCurrentUser,
    getAuthToken,
    avatarUrl,
} = window.SeeMusicApp;

const state = {
    items: [],
    selectedScoreId: "",
    selectedDetail: null,
    selectedComments: [],
    activeTag: "",
    keyword: "",
    tags: [],
};

const searchInput = document.getElementById("search-input");
const tagBar = document.getElementById("tag-bar");
const statusEl = document.getElementById("community-status");
const scoreGrid = document.getElementById("score-grid");
const headerAvatar = document.getElementById("header-avatar");
const uploadFileInput = document.getElementById("upload-file-input");
const uploadFileName = document.getElementById("upload-file-name");
const uploadCoverInput = document.getElementById("upload-cover-input");
const uploadCoverName = document.getElementById("upload-cover-name");
const uploadCoverPreview = document.getElementById("upload-cover-preview");
const uploadCoverPreviewFrame = document.getElementById("upload-cover-preview-frame");
const uploadCoverPlaceholderIcon = document.getElementById("upload-cover-placeholder-icon");
const uploadCoverHint = document.getElementById("upload-cover-hint");
const uploadStatus = document.getElementById("upload-status");
const uploadTitleInput = document.getElementById("upload-title-input");
const uploadDescriptionInput = document.getElementById("upload-description-input");
const uploadStyleInput = document.getElementById("upload-style-input");
const uploadPriceInput = document.getElementById("upload-price-input");
const uploadInstrumentInput = document.getElementById("upload-instrument-input");
const uploadTagsInput = document.getElementById("upload-tags-input");
const uploadSubmitBtn = document.getElementById("upload-submit-btn");
const uploadCoverTrigger = document.getElementById("upload-cover-trigger");
const uploadCoverCropModal = document.getElementById("upload-cover-crop-modal");
const uploadCoverCropViewport = document.getElementById("upload-cover-crop-viewport");
const uploadCoverCropImage = document.getElementById("upload-cover-crop-image");
const uploadCoverCropPreview = document.getElementById("upload-cover-crop-preview");
const uploadCoverCropZoom = document.getElementById("upload-cover-crop-zoom");
const uploadCoverCropResetBtn = document.getElementById("upload-cover-crop-reset");
const uploadCoverCropCancelBtn = document.getElementById("upload-cover-crop-cancel");
const uploadCoverCropApplyBtn = document.getElementById("upload-cover-crop-apply");
const uploadCoverCropCloseBtn = document.getElementById("upload-cover-crop-close");
const detailEmpty = document.getElementById("detail-empty");
const detailContent = document.getElementById("detail-content");
const commentInput = document.getElementById("comment-input");
const commentSendBtn = document.getElementById("comment-send-btn");
const detailLikeBtn = document.getElementById("detail-like-btn");
const detailDownloadBtn = document.getElementById("detail-download-btn");
const detailFavoriteBtn = document.getElementById("detail-favorite-btn");
const detailShareBtn = document.getElementById("detail-share-btn");

let searchTimer = null;
let selectedCoverFile = null;
let coverCropState = createCoverCropState();

function createCoverCropState() {
    return {
        file: null,
        dataUrl: "",
        image: null,
        zoom: 1,
        offsetX: 0,
        offsetY: 0,
        viewportWidth: 0,
        viewportHeight: 0,
        displayScale: 1,
        displayWidth: 0,
        displayHeight: 0,
        dragging: false,
        pointerId: null,
        dragStartX: 0,
        dragStartY: 0,
        startOffsetX: 0,
        startOffsetY: 0,
    };
}

function setStatus(message, isError = false) {
    statusEl.textContent = message;
    statusEl.className = `text-sm mb-6 ${isError ? "text-red-500" : "text-gray-400"}`;
}

function setUploadStatus(message, isError = false) {
    if (!message) {
        uploadStatus.className = "hidden text-xs rounded-xl px-4 py-3 mb-4";
        uploadStatus.textContent = "";
        return;
    }
    uploadStatus.className = `text-xs rounded-xl px-4 py-3 mb-4 ${isError ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-700"}`;
    uploadStatus.textContent = message;
}
function formatFileSize(file) {
    if (!file) return "";
    const size = file.size;
    if (size < 1024) return `${file.name} (${size} B)`;
    if (size < 1024 * 1024) return `${file.name} (${(size / 1024).toFixed(1)} KB)`;
    return `${file.name} (${(size / (1024 * 1024)).toFixed(1)} MB)`;
}

function setCoverSelection(file) {
    selectedCoverFile = file;
    if (!file) {
        uploadCoverInput.value = "";
        uploadCoverName.textContent = "尚未选择封面";
        uploadCoverPreview.src = "";
        uploadCoverPreviewFrame.classList.add("hidden");
        uploadCoverPlaceholderIcon.classList.remove("hidden");
        if (uploadCoverHint) {
            uploadCoverHint.innerHTML = '拖拽图片到这里 或 <span class="text-[#457b9d] font-bold">点击上传封面</span>';
        }
        return;
    }

    if (file.type && !file.type.startsWith("image/")) {
        setUploadStatus("封面文件必须是图片格式。", true);
        selectedCoverFile = null;
        return;
    }

    uploadCoverName.textContent = formatFileSize(file);
    if (uploadCoverHint) {
        uploadCoverHint.innerHTML = '封面已准备好，可再次点击上传重新裁剪';
    }
    const reader = new FileReader();
    reader.onload = () => {
        uploadCoverPreview.src = String(reader.result || "");
        uploadCoverPreviewFrame.classList.remove("hidden");
        uploadCoverPlaceholderIcon.classList.add("hidden");
    };
    reader.readAsDataURL(file);
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function resetCoverCropper() {
    coverCropState = createCoverCropState();
    uploadCoverCropImage.src = "";
    uploadCoverCropImage.style.width = "";
    uploadCoverCropImage.style.height = "";
    uploadCoverCropImage.style.transform = "translate(-50%, -50%)";
    uploadCoverCropZoom.value = "1";
    const ctx = uploadCoverCropPreview.getContext("2d");
    ctx.clearRect(0, 0, uploadCoverCropPreview.width, uploadCoverCropPreview.height);
    uploadCoverCropViewport.classList.remove("is-dragging");
}

function closeCoverCropper() {
    toggleModal("upload-cover-crop-modal", false);
    resetCoverCropper();
    uploadCoverInput.value = "";
}

function openCoverCropper(file) {
    if (!file) {
        return;
    }
    if (file.type && !file.type.startsWith("image/")) {
        setUploadStatus("封面文件必须是图片格式。", true);
        return;
    }
    if (file.size > 5 * 1024 * 1024) {
        setUploadStatus("封面图片不能超过 5MB。", true);
        return;
    }

    const reader = new FileReader();
    reader.onload = () => {
        const dataUrl = String(reader.result || "");
        const image = new Image();
        image.onload = () => {
            coverCropState = createCoverCropState();
            coverCropState.file = file;
            coverCropState.dataUrl = dataUrl;
            coverCropState.image = image;
            uploadCoverCropImage.src = dataUrl;
            uploadCoverCropZoom.value = "1";
            toggleModal("upload-cover-crop-modal", true);
            window.requestAnimationFrame(() => syncCoverCropBounds(true));
        };
        image.onerror = () => setUploadStatus("封面图片读取失败，请换一张再试。", true);
        image.src = dataUrl;
    };
    reader.onerror = () => setUploadStatus("封面图片读取失败，请换一张再试。", true);
    reader.readAsDataURL(file);
}

function syncCoverCropBounds(resetPosition = false) {
    if (!coverCropState.image) {
        return;
    }
    const viewportWidth = uploadCoverCropViewport.clientWidth;
    const viewportHeight = uploadCoverCropViewport.clientHeight;
    if (!viewportWidth || !viewportHeight) {
        return;
    }

    const baseScale = Math.max(
        viewportWidth / coverCropState.image.naturalWidth,
        viewportHeight / coverCropState.image.naturalHeight,
    );
    coverCropState.viewportWidth = viewportWidth;
    coverCropState.viewportHeight = viewportHeight;
    coverCropState.displayScale = baseScale * coverCropState.zoom;
    coverCropState.displayWidth = coverCropState.image.naturalWidth * coverCropState.displayScale;
    coverCropState.displayHeight = coverCropState.image.naturalHeight * coverCropState.displayScale;

    if (resetPosition) {
        coverCropState.offsetX = 0;
        coverCropState.offsetY = 0;
    }

    const maxOffsetX = Math.max(0, (coverCropState.displayWidth - viewportWidth) / 2);
    const maxOffsetY = Math.max(0, (coverCropState.displayHeight - viewportHeight) / 2);
    coverCropState.offsetX = clamp(coverCropState.offsetX, -maxOffsetX, maxOffsetX);
    coverCropState.offsetY = clamp(coverCropState.offsetY, -maxOffsetY, maxOffsetY);

    uploadCoverCropImage.style.width = `${coverCropState.displayWidth}px`;
    uploadCoverCropImage.style.height = `${coverCropState.displayHeight}px`;
    uploadCoverCropImage.style.transform = `translate(-50%, -50%) translate(${coverCropState.offsetX}px, ${coverCropState.offsetY}px)`;
    updateCoverCropPreview();
}

function getCoverCropSourceRect() {
    const left = (coverCropState.viewportWidth - coverCropState.displayWidth) / 2 + coverCropState.offsetX;
    const top = (coverCropState.viewportHeight - coverCropState.displayHeight) / 2 + coverCropState.offsetY;
    return {
        x: clamp((0 - left) / coverCropState.displayScale, 0, coverCropState.image.naturalWidth),
        y: clamp((0 - top) / coverCropState.displayScale, 0, coverCropState.image.naturalHeight),
        width: clamp(
            coverCropState.viewportWidth / coverCropState.displayScale,
            1,
            coverCropState.image.naturalWidth,
        ),
        height: clamp(
            coverCropState.viewportHeight / coverCropState.displayScale,
            1,
            coverCropState.image.naturalHeight,
        ),
    };
}

function updateCoverCropPreview() {
    if (!coverCropState.image) {
        return;
    }
    const ctx = uploadCoverCropPreview.getContext("2d");
    const source = getCoverCropSourceRect();
    ctx.clearRect(0, 0, uploadCoverCropPreview.width, uploadCoverCropPreview.height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, uploadCoverCropPreview.width, uploadCoverCropPreview.height);
    ctx.drawImage(
        coverCropState.image,
        source.x,
        source.y,
        source.width,
        source.height,
        0,
        0,
        uploadCoverCropPreview.width,
        uploadCoverCropPreview.height,
    );
}

function renameCoverFile(originalName, extension) {
    const normalized = originalName || "community-cover";
    if (/\.[^.]+$/.test(normalized)) {
        return normalized.replace(/\.[^.]+$/, extension);
    }
    return `${normalized}${extension}`;
}

async function applyCoverCrop() {
    if (!coverCropState.image || !coverCropState.file) {
        return;
    }

    uploadCoverCropApplyBtn.disabled = true;
    uploadCoverCropApplyBtn.textContent = "处理中...";

    try {
        const source = getCoverCropSourceRect();
        const canvas = document.createElement("canvas");
        canvas.width = 1200;
        canvas.height = 900;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(
            coverCropState.image,
            source.x,
            source.y,
            source.width,
            source.height,
            0,
            0,
            canvas.width,
            canvas.height,
        );

        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
        if (!blob) {
            throw new Error("封面裁剪失败");
        }

        const croppedFile = new File([blob], renameCoverFile(coverCropState.file.name, ".jpg"), {
            type: "image/jpeg",
        });
        const transfer = new DataTransfer();
        transfer.items.add(croppedFile);
        uploadCoverInput.files = transfer.files;
        setCoverSelection(croppedFile);
        closeCoverCropper();
        setUploadStatus("封面已裁剪完成，发布时会上传这张封面。");
    } catch (error) {
        setUploadStatus(error.message || "封面裁剪失败，请稍后重试。", true);
    } finally {
        uploadCoverCropApplyBtn.disabled = false;
        uploadCoverCropApplyBtn.textContent = "使用封面";
    }
}

function startCoverCropDrag(event) {
    if (!coverCropState.image) {
        return;
    }
    if (uploadCoverCropViewport.setPointerCapture) {
        uploadCoverCropViewport.setPointerCapture(event.pointerId);
    }
    coverCropState.dragging = true;
    coverCropState.pointerId = event.pointerId;
    coverCropState.dragStartX = event.clientX;
    coverCropState.dragStartY = event.clientY;
    coverCropState.startOffsetX = coverCropState.offsetX;
    coverCropState.startOffsetY = coverCropState.offsetY;
    uploadCoverCropViewport.classList.add("is-dragging");
    event.preventDefault();
}

function moveCoverCropDrag(event) {
    if (!coverCropState.dragging || coverCropState.pointerId !== event.pointerId) {
        return;
    }
    coverCropState.offsetX = coverCropState.startOffsetX + (event.clientX - coverCropState.dragStartX);
    coverCropState.offsetY = coverCropState.startOffsetY + (event.clientY - coverCropState.dragStartY);
    syncCoverCropBounds(false);
}

function stopCoverCropDrag(event) {
    if (coverCropState.pointerId !== null && event.pointerId !== coverCropState.pointerId) {
        return;
    }
    if (event.pointerId !== undefined && uploadCoverCropViewport.releasePointerCapture) {
        try {
            uploadCoverCropViewport.releasePointerCapture(event.pointerId);
        } catch { }
    }
    coverCropState.dragging = false;
    coverCropState.pointerId = null;
    uploadCoverCropViewport.classList.remove("is-dragging");
}

async function saveHistory(payload) {
    if (!getAuthToken()) {
        return;
    }
    try {
        await requestJson("/users/me/history", {
            method: "POST",
            body: payload,
        });
    } catch (error) {
        console.warn("save history failed", error);
    }
}

function formatRelativeText(score) {
    if (!score) {
        return "";
    }
    if (score.updated_at && score.updated_at !== score.published_at) {
        return `更新于 ${new Date(score.updated_at).toLocaleString("zh-CN")}`;
    }
    if (score.published_at) {
        return `发布于 ${new Date(score.published_at).toLocaleString("zh-CN")}`;
    }
    return "";
}

function renderTags() {
    const buttons = [
        `<button class="px-6 py-2 rounded-full text-sm font-medium shadow-md ${state.activeTag ? "bg-white text-gray-600" : "bg-[#1d3557] text-white"}" data-tag="">全部</button>`,
        ...state.tags.map((tag) => {
            const active = state.activeTag === tag.name;
            return `<button class="px-6 py-2 rounded-full text-sm font-medium shadow-md ${active ? "bg-[#1d3557] text-white" : "bg-white text-gray-600"}" data-tag="${escapeHtml(tag.name)}">${escapeHtml(tag.name)} <span class="opacity-60">(${tag.count})</span></button>`;
        }),
    ];
    tagBar.innerHTML = buttons.join("");
}

function renderGrid() {
    if (!state.items.length) {
        scoreGrid.innerHTML = `
            <div class="col-span-full bg-white rounded-[28px] border border-gray-100 shadow-sm p-10 text-center">
                <iconify-icon class="text-5xl text-gray-200 mb-4" icon="solar:music-library-2-bold-duotone"></iconify-icon>
                <p class="text-gray-500 font-medium">没有匹配的社区乐谱</p>
                <p class="text-xs text-gray-400 mt-2">可以尝试切换标签、清空搜索词，或直接上传新的版本。</p>
            </div>
        `;
        return;
    }

    scoreGrid.innerHTML = state.items.map((item) => {
        const isSelected = item.score_id === state.selectedScoreId;
        return `
            <article class="text-left bg-white rounded-[28px] border p-5 shadow-sm hover:shadow-lg transition-all cursor-pointer ${isSelected ? "border-[#457b9d] ring-2 ring-[#a8dadc]/60" : "border-gray-100"}" data-score-id="${escapeHtml(item.score_id)}" tabindex="0">
                <div class="aspect-[4/3] rounded-2xl overflow-hidden bg-gray-50 mb-4 relative">
                    <img alt="${escapeHtml(item.title)}" class="w-full h-full object-cover" src="${escapeHtml(item.cover_url || avatarUrl(item.title || item.score_id))}" onerror="this.onerror=null; this.src='https://api.dicebear.com/7.x/initials/svg?seed=' + encodeURIComponent(this.alt)"/>
                    <button
                        class="absolute top-3 right-3 w-10 h-10 rounded-full backdrop-blur bg-white/85 border border-white/70 flex items-center justify-center transition-all ${item.favorited ? "text-[#1d3557]" : "text-gray-400 hover:text-[#1d3557]"}"
                        data-favorite-score-id="${escapeHtml(item.score_id)}"
                        data-favorited="${item.favorited ? "true" : "false"}"
                        type="button"
                    >
                        <iconify-icon class="text-lg" icon="${item.favorited ? "solar:bookmark-bold" : "solar:bookmark-outline"}"></iconify-icon>
                    </button>
                </div>
                <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                        <h3 class="font-bold text-gray-800 truncate">${escapeHtml(item.title)}</h3>
                        <p class="text-xs text-gray-400 mt-1 truncate">${escapeHtml(item.subtitle || item.author || "社区用户")}</p>
                    </div>
                    <span class="text-xs font-bold ${item.price > 0 ? "text-[#457b9d]" : "text-green-600"}">${escapeHtml(item.price_label || "免费")}</span>
                </div>
                <p class="text-xs text-gray-500 mt-3 line-clamp-2 min-h-[2.5rem]">${escapeHtml(item.description || "暂无简介")}</p>
                <div class="flex flex-wrap gap-2 mt-4">
                    ${(item.tags || []).slice(0, 3).map((tag) => `<span class="px-2.5 py-1 rounded-full bg-gray-50 text-[11px] text-gray-500">${escapeHtml(tag)}</span>`).join("")}
                </div>
                <div class="flex items-center justify-between text-[11px] text-gray-400 mt-4">
                    <span>下载 ${escapeHtml(item.download_count_display || String(item.downloads || 0))}</span>
                    <span>点赞 ${escapeHtml(String(item.likes || 0))}</span>
                    <span>评论 ${escapeHtml(String(item.comments_count || 0))}</span>
                </div>
            </article>
        `;
    }).join("");
}

function renderDetail() {
    const detail = state.selectedDetail;
    if (!detail || !detail.score) {
        detailEmpty.classList.remove("hidden");
        detailContent.classList.add("hidden");
        return;
    }

    const score = detail.score;
    detailEmpty.classList.add("hidden");
    detailContent.classList.remove("hidden");

    document.getElementById("d-title").textContent = score.title || "未命名乐谱";
    document.getElementById("d-author").textContent = score.subtitle || score.author || "社区用户";
    document.getElementById("d-cover").src = score.cover_url || avatarUrl(score.title || score.score_id);
    document.getElementById("d-cover").alt = score.title || "preview";
    document.getElementById("d-price").textContent = score.price_label || "免费";
    document.getElementById("d-downloads").textContent = String(score.downloads || 0);
    document.getElementById("d-likes").textContent = String(score.likes || 0);
    document.getElementById("d-favorites").textContent = String(score.favorites || 0);
    document.getElementById("d-description").textContent = score.description || "暂无简介";
    document.getElementById("comment-title").textContent = `社区评论 (${state.selectedComments.length})`;

    detailLikeBtn.className = `transition-colors ${score.liked ? "text-red-500" : "text-gray-300 hover:text-red-500"}`;
    detailLikeBtn.innerHTML = `<iconify-icon class="text-2xl" icon="${score.liked ? "solar:heart-bold" : "solar:heart-outline"}"></iconify-icon>`;
    detailFavoriteBtn.className = `w-14 h-14 rounded-2xl flex items-center justify-center transition-all ${score.favorited ? "bg-[#1d3557] text-white" : "bg-gray-50 text-gray-400 hover:bg-gray-100"}`;
    detailFavoriteBtn.innerHTML = `<iconify-icon class="text-xl" icon="${score.favorited ? "solar:bookmark-bold" : "solar:bookmark-outline"}"></iconify-icon>`;

    const commentsList = document.getElementById("detail-comments-list");
if (!state.selectedComments.length) {
    commentsList.innerHTML = '<p class="text-xs text-gray-400">还没有评论，来成为第一个留言的人。</p>';
} else {
    commentsList.innerHTML = state.selectedComments.map((comment) => {
        // 1. 先计算出应该显示的名字（优先昵称，其次用户名，最后保底）
        const displayName = comment.nickname || comment.username || "社区用户";
        
        // 2. 构造 HTML
        return `
            <div class="flex gap-3">
                <!-- 头像部分：使用我们之前优化过的对象传参 -->
                <img alt="${escapeHtml(displayName)}" 
                     class="w-9 h-9 rounded-full bg-gray-100" 
                     src="${escapeHtml(avatarUrl({ avatar: comment.avatar_url, username: displayName }))}" 
                     onerror="this.onerror=null; this.src='https://api.dicebear.com/7.x/avataaars/svg?seed=' + encodeURIComponent(this.alt)"/>
                
                <div class="min-w-0 flex-1">
                    <div class="flex items-center justify-between gap-3">
                        <!-- 【核心修改】：这里一定要换成 displayName 变量 -->
                        <span class="text-sm font-medium text-gray-700 truncate">${escapeHtml(displayName)}</span>
                        
                        <span class="text-[10px] text-gray-400 whitespace-nowrap">${escapeHtml(comment.relative_time || "")}</span>
                    </div>
                    <p class="text-xs text-gray-500 leading-relaxed mt-1 break-words">${escapeHtml(comment.content || "")}</p>
                </div>
            </div>
        `;
    }).join("");
}
}

function syncItem(scoreId, patch) {
    state.items = state.items.map((item) => item.score_id === scoreId ? { ...item, ...patch } : item);
    if (state.selectedDetail && state.selectedDetail.score && state.selectedDetail.score.score_id === scoreId) {
        state.selectedDetail.score = { ...state.selectedDetail.score, ...patch };
    }
}

async function loadTags() {
    const data = await requestJson("/community/tags");
    state.tags = data.items || [];
    renderTags();
}

async function loadScores(preferredScoreId = "") {
    const query = new URLSearchParams();
    query.set("page", "1");
    query.set("page_size", "20");
    if (state.keyword) {
        query.set("keyword", state.keyword);
    }
    if (state.activeTag) {
        query.set("tag", state.activeTag);
    }

    setStatus("正在同步社区乐谱...");
    const data = await requestJson(`/community/scores?${query.toString()}`);
    state.items = data.items || [];
    renderGrid();
    setStatus(`已连接后端，当前共 ${data.total || 0} 份社区乐谱。`);

    const targetScoreId = preferredScoreId
        || state.selectedScoreId
        || new URLSearchParams(window.location.search).get("score_id")
        || (state.items[0] && state.items[0].score_id)
        || "";

    if (targetScoreId) {
        const exists = state.items.some((item) => item.score_id === targetScoreId);
        if (exists) {
            await selectScore(targetScoreId);
            return;
        }
    }

    state.selectedScoreId = "";
    state.selectedDetail = null;
    state.selectedComments = [];
    renderDetail();
}

async function loadScoreDetail(scoreId) {
    const data = await requestJson(`/community/scores/${encodeURIComponent(scoreId)}`);
    state.selectedDetail = data;
    state.selectedComments = data.comments || [];
    syncItem(scoreId, data.score || {});
    renderGrid();
    renderDetail();
}

async function loadScoreComments(scoreId) {
    const data = await requestJson(`/community/scores/${encodeURIComponent(scoreId)}/comments?page=1&page_size=20`);
    state.selectedComments = data.items || [];
    if (state.selectedDetail && state.selectedDetail.score && state.selectedDetail.score.score_id === scoreId) {
        state.selectedDetail.comments = state.selectedComments;
        state.selectedDetail.score.comments_count = data.total || state.selectedComments.length;
    }
    syncItem(scoreId, { comments_count: data.total || state.selectedComments.length });
    renderGrid();
    renderDetail();
}

async function selectScore(scoreId) {
    if (!scoreId) {
        return;
    }
    state.selectedScoreId = scoreId;
    renderGrid();
    try {
        await loadScoreDetail(scoreId);
        await loadScoreComments(scoreId);
    } catch (error) {
        setStatus(error.message || "加载乐谱详情失败。", true);
    }
}

async function handleLikeToggle() {
    const score = state.selectedDetail && state.selectedDetail.score;
    if (!score) {
        return;
    }
    const nextLiked = !score.liked;
    detailLikeBtn.disabled = true;
    try {
        const payload = await requestJson(`/community/scores/${encodeURIComponent(score.score_id)}/like`, {
            method: nextLiked ? "POST" : "DELETE",
        });
        syncItem(score.score_id, { liked: payload.liked, likes: payload.likes });
        renderGrid();
        renderDetail();
    } catch (error) {
        setStatus(error.message || "点赞操作失败。", true);
    } finally {
        detailLikeBtn.disabled = false;
    }
}

async function handleFavoriteToggle() {
    const score = state.selectedDetail && state.selectedDetail.score;
    if (!score) {
        return;
    }
    const nextFavorited = !score.favorited;
    detailFavoriteBtn.disabled = true;
    try {
        const payload = await requestJson(`/community/scores/${encodeURIComponent(score.score_id)}/favorite`, {
            method: nextFavorited ? "POST" : "DELETE",
        });
        syncItem(score.score_id, { favorited: payload.favorited, favorites: payload.favorites });
        renderGrid();
        renderDetail();
        setStatus(payload.favorited ? "已加入收藏。" : "已取消收藏。");
    } catch (error) {
        setStatus(error.message || "收藏操作失败。", true);
    } finally {
        detailFavoriteBtn.disabled = false;
    }
}

async function handleFavoriteToggleByScoreId(scoreId, nextFavorited) {
    try {
        const payload = await requestJson(`/community/scores/${encodeURIComponent(scoreId)}/favorite`, {
            method: nextFavorited ? "POST" : "DELETE",
        });
        syncItem(scoreId, { favorited: payload.favorited, favorites: payload.favorites });
        renderGrid();
        renderDetail();
    } catch (error) {
        setStatus(error.message || "收藏操作失败。", true);
    }
}

async function handleDownload() {
    const score = state.selectedDetail && state.selectedDetail.score;
    if (!score) {
        return;
    }
    detailDownloadBtn.disabled = true;
    try {
        const myBlob = await requestJson(`/community/scores/${encodeURIComponent(score.score_id)}/download`, {
            method: "POST",
            responseType: 'blob' 
        });
        const url = window.URL.createObjectURL(myBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = score.source_file_name || "乐谱.pdf";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        setStatus("下载成功！");
        
         const updatedInfo = await requestJson(`/community/scores/${encodeURIComponent(score.score_id)}`, {
            method: "GET" 
        });
        const scoreData = updatedInfo.score; 

        syncItem(score.score_id, {
             downloads: scoreData.downloads,
            download_count_display: scoreData.download_count_display
        });

        renderGrid();
        renderDetail();
        setStatus(`已记录下载：${scoreData.source_file_name || score.title}。当前下载 ${scoreData.downloads} 次。`);
        await saveHistory({
            type: "score",
            resource_id: score.score_id,
            title: `下载乐谱：${score.title}`,
            metadata: {
                source: "community",
                file_name: scoreData.source_file_name || "",
                downloads: scoreData.downloads || 0,
                published_at: scoreData.published_at || "",
            },
        });
    } catch (error) {
        setStatus(error.message || "下载记录失败。", true);
    } finally {
        detailDownloadBtn.disabled = false;
    }
}

async function handleCommentSubmit() {
    const score = state.selectedDetail && state.selectedDetail.score;
    const content = commentInput.value.trim();
    if (!score || !content) {
        return;
    }
    commentSendBtn.disabled = true;
    try {
        const currentUser = getCurrentUser();
        await requestJson(`/community/scores/${encodeURIComponent(score.score_id)}/comments`, {
            method: "POST",
            body: {
                content,
                username: currentUser && currentUser.username ? currentUser.username : undefined,
            },
        });
        commentInput.value = "";
        await loadScoreComments(score.score_id);
    } catch (error) {
        setStatus(error.message || "评论发送失败。", true);
    } finally {
        commentSendBtn.disabled = false;
    }
}

async function handleUploadSubmit() {
    const file = uploadFileInput.files && uploadFileInput.files[0];
    const coverFile = selectedCoverFile;
    const title = uploadTitleInput.value.trim();
    const style = uploadStyleInput.value.trim();
    const instrument = uploadInstrumentInput.value.trim();
    const tags = uploadTagsInput.value.trim();
    const price = Number(uploadPriceInput.value || 0);
    const description = uploadDescriptionInput.value.trim();

    if (!file) {
        setUploadStatus("请先选择要上传的文件。", true);
        return;
    }
    if (!title) {
        setUploadStatus("请填写作品标题。", true);
        return;
    }
    if (!style || style === "选择风格") {
        setUploadStatus("请选择作品风格。", true);
        return;
    }
    if (!instrument) {
        setUploadStatus("请选择乐器类型。", true);
        return;
    }
    const base64File = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]); 
        reader.readAsDataURL(file);
    });

    const formData = new FormData();
    formData.append("file", file);
    formData.append("file_content_base64", base64File); 
    formData.append("title", title);
    formData.append("style", style);
    formData.append("instrument", instrument);
    formData.append("price", String(Number.isFinite(price) ? price : 0));
    formData.append("description", description);
    formData.append("tags", tags);
    formData.append("file_content_base64", base64File); 
    if (coverFile) {
        formData.append("cover_file", coverFile);
    }

    uploadSubmitBtn.disabled = true;
    uploadSubmitBtn.textContent = "发布中...";
    setUploadStatus("正在上传并同步数据库...");

    try {
        const payload = await requestJson("/community/scores/upload", {
            method: "POST",
            body: formData,
        });
        setUploadStatus("作品已发布，社区列表已刷新。");
        await saveHistory({
            type: "score",
            resource_id: payload.score_id,
            title: `发布乐谱：${title}`,
            metadata: {
                source: "community_upload",
                file_name: file.name,
                style,
                instrument,
            },
        });
        resetUploadForm();
        toggleModal("upload-modal", false);
        await loadTags();
        await loadScores(payload.score_id);
    } catch (error) {
        setUploadStatus(error.message || "上传失败，请稍后重试。", true);
    } finally {
        uploadSubmitBtn.disabled = false;
        uploadSubmitBtn.textContent = "发布作品";
    }
}

function resetUploadForm() {
    uploadFileInput.value = "";
    uploadFileName.textContent = "尚未选择文件";
    setCoverSelection(null);
    uploadTitleInput.value = "";
    uploadDescriptionInput.value = "";
    uploadStyleInput.value = "选择风格";
    uploadPriceInput.value = "";
    uploadInstrumentInput.value = "";
    uploadTagsInput.value = "";
}

function toggleModal(id, show) {
    const modal = document.getElementById(id);
    if (!modal) {
        return;
    }
    if (show) {
        modal.classList.remove("hidden");
        modal.classList.add("modal-active");
    } else {
        modal.classList.add("hidden");
        modal.classList.remove("modal-active");
        setUploadStatus("");
    }
}

function updateHeader() {
    const currentUser = getCurrentUser();
    headerAvatar.src = currentUser ? avatarUrl(currentUser) : avatarUrl("SeeMusic");
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function bindEvents() {
    scoreGrid.addEventListener("click", (event) => {
        const favoriteButton = event.target.closest("[data-favorite-score-id]");
        if (favoriteButton) {
            event.stopPropagation();
            const scoreId = favoriteButton.dataset.favoriteScoreId;
            const nextFavorited = favoriteButton.dataset.favorited !== "true";
            handleFavoriteToggleByScoreId(scoreId, nextFavorited);
            return;
        }
        const card = event.target.closest("[data-score-id]");
        if (card) {
            selectScore(card.dataset.scoreId);
        }
    });

    scoreGrid.addEventListener("keydown", (event) => {
        const card = event.target.closest("[data-score-id]");
        if (!card) {
            return;
        }
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            selectScore(card.dataset.scoreId);
        }
    });

    tagBar.addEventListener("click", (event) => {
        const button = event.target.closest("[data-tag]");
        if (!button) {
            return;
        }
        state.activeTag = button.dataset.tag || "";
        loadScores().catch((error) => setStatus(error.message || "加载乐谱失败。", true));
        renderTags();
    });

    searchInput.addEventListener("input", (event) => {
        state.keyword = event.target.value.trim();
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => {
            loadScores().catch((error) => setStatus(error.message || "搜索失败。", true));
        }, 250);
    });

    detailLikeBtn.addEventListener("click", handleLikeToggle);
    detailDownloadBtn.addEventListener("click", handleDownload);
    detailFavoriteBtn.addEventListener("click", handleFavoriteToggle);
    detailShareBtn.addEventListener("click", async () => {
        const score = state.selectedDetail && state.selectedDetail.score;
        if (!score) {
            return;
        }
        const shareUrl = `${window.location.origin}${window.location.pathname}?score_id=${encodeURIComponent(score.score_id)}`;
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(shareUrl);
            }
            setStatus(`分享链接已复制：${formatRelativeText(score) || score.title}`);
        } catch {
            setStatus("浏览器未授权剪贴板，无法自动复制。", true);
        }
    });

    commentSendBtn.addEventListener("click", handleCommentSubmit);
    commentInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            handleCommentSubmit();
        }
    });

    uploadFileInput.addEventListener("change", () => {
        const file = uploadFileInput.files && uploadFileInput.files[0];
        uploadFileName.textContent = file ? formatFileSize(file) : "尚未选择文件";
    });

    uploadCoverInput.addEventListener("change", () => {
        const file = uploadCoverInput.files && uploadCoverInput.files[0];
        if (file) {
            openCoverCropper(file);
        }
    });

    const uploadDropzone = document.getElementById("upload-dropzone").closest("div");
    uploadDropzone.addEventListener("click", () => uploadFileInput.click());
    uploadDropzone.addEventListener("dragover", (event) => {
        event.preventDefault();
        uploadDropzone.classList.add("border-[#a8dadc]");
    });
    uploadDropzone.addEventListener("dragleave", () => {
        uploadDropzone.classList.remove("border-[#a8dadc]");
    });
    uploadDropzone.addEventListener("drop", (event) => {
        event.preventDefault();
        uploadDropzone.classList.remove("border-[#a8dadc]");
        const file = event.dataTransfer.files && event.dataTransfer.files[0];
        if (!file) {
            return;
        }
        const transfer = new DataTransfer();
        transfer.items.add(file);
        uploadFileInput.files = transfer.files;
        uploadFileName.textContent = formatFileSize(file);
    });

    const uploadCoverDropzone = document.getElementById("upload-cover-dropzone");
    uploadCoverTrigger.addEventListener("click", () => uploadCoverInput.click());
    uploadCoverDropzone.addEventListener("click", () => uploadCoverInput.click());
    uploadCoverDropzone.addEventListener("dragover", (event) => {
        event.preventDefault();
        uploadCoverDropzone.classList.add("border-[#a8dadc]");
    });
    uploadCoverDropzone.addEventListener("dragleave", () => {
        uploadCoverDropzone.classList.remove("border-[#a8dadc]");
    });
    uploadCoverDropzone.addEventListener("drop", (event) => {
        event.preventDefault();
        uploadCoverDropzone.classList.remove("border-[#a8dadc]");
        const file = event.dataTransfer.files && event.dataTransfer.files[0];
        if (!file) {
            return;
        }
        const transfer = new DataTransfer();
        transfer.items.add(file);
        uploadCoverInput.files = transfer.files;
        openCoverCropper(file);
    });

    uploadCoverCropViewport.addEventListener("pointerdown", startCoverCropDrag);
    uploadCoverCropViewport.addEventListener("pointermove", moveCoverCropDrag);
    uploadCoverCropViewport.addEventListener("pointerup", stopCoverCropDrag);
    uploadCoverCropViewport.addEventListener("pointercancel", stopCoverCropDrag);
    uploadCoverCropViewport.addEventListener("lostpointercapture", stopCoverCropDrag);
    uploadCoverCropZoom.addEventListener("input", () => {
        coverCropState.zoom = Number(uploadCoverCropZoom.value || 1);
        syncCoverCropBounds(false);
    });
    uploadCoverCropResetBtn.addEventListener("click", () => {
        coverCropState.zoom = 1;
        uploadCoverCropZoom.value = "1";
        syncCoverCropBounds(true);
    });
    uploadCoverCropCancelBtn.addEventListener("click", closeCoverCropper);
    uploadCoverCropCloseBtn.addEventListener("click", closeCoverCropper);
    uploadCoverCropApplyBtn.addEventListener("click", applyCoverCrop);
    uploadCoverCropModal.addEventListener("click", (event) => {
        if (event.target === uploadCoverCropModal) {
            closeCoverCropper();
        }
    });
    window.addEventListener("resize", () => syncCoverCropBounds(false));
    uploadSubmitBtn.addEventListener("click", handleUploadSubmit);
}

async function bootstrap() {
    updateHeader();
    bindEvents();
    try {
        await loadTags();
        await loadScores();
    } catch (error) {
        setStatus(error.message || "社区页初始化失败，请检查后端服务。", true);
    }
}

window.toggleModal = toggleModal;
window.addEventListener("load", bootstrap);
