(function () {
    const STORAGE_KEYS = {
        apiBase: "seemusic.transcription.apiBase",
        authToken: "seemusic.auth.token",
        currentUser: "seemusic.auth.user",
        loggedIn: "seeMusic_isLoggedIn",
    };

    const DEFAULT_BACKEND_ORIGIN = "http://127.0.0.1:8000";
    const DEFAULT_API_BASE = `${DEFAULT_BACKEND_ORIGIN}/api/v1`;

    function normalizeApiBase(rawValue) {
        let value = (rawValue || "").trim() || DEFAULT_API_BASE;
        if (!/^https?:\/\//i.test(value)) {
            value = `http://${value}`;
        }
        value = value.replace(/\/+$/, "");
        if (!/\/api\/v\d+$/i.test(value)) {
            value = `${value}/api/v1`;
        }
        return value;
    }

    function getApiBase() {
        return normalizeApiBase(localStorage.getItem(STORAGE_KEYS.apiBase) || DEFAULT_API_BASE);
    }

    function getApiOrigin() {
        try {
            return new URL(getApiBase()).origin;
        } catch {
            return DEFAULT_BACKEND_ORIGIN;
        }
    }

    function buildApiUrl(path) {
        if (/^https?:\/\//i.test(path)) {
            return path;
        }
        if (path.startsWith("/api/")) {
            return `${getApiOrigin()}${path}`;
        }
        if (path.startsWith("/")) {
            return `${getApiBase()}${path}`;
        }
        return `${getApiBase()}/${path}`;
    }

    function buildServerUrl(path) {
        if (/^https?:\/\//i.test(path)) {
            return path;
        }
        return `${getApiOrigin()}${path.startsWith("/") ? path : `/${path}`}`;
    }

    function getAuthToken() {
        return localStorage.getItem(STORAGE_KEYS.authToken) || "";
    }

    function getCurrentUser() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEYS.currentUser) || "null");
        } catch {
            return null;
        }
    }

    function setAuthSession(payload) {
        if (!payload || !payload.token || !payload.user) {
            return;
        }
        localStorage.setItem(STORAGE_KEYS.authToken, payload.token);
        localStorage.setItem(STORAGE_KEYS.currentUser, JSON.stringify(payload.user));
        localStorage.setItem(STORAGE_KEYS.loggedIn, "true");
    }

    function clearAuthSession() {
        localStorage.removeItem(STORAGE_KEYS.authToken);
        localStorage.removeItem(STORAGE_KEYS.currentUser);
        localStorage.removeItem(STORAGE_KEYS.loggedIn);
    }

    function authHeaders(extraHeaders) {
        const headers = { ...(extraHeaders || {}) };
        const token = getAuthToken();
        if (token) {
            headers.Authorization = `Bearer ${token}`;
        }
        return headers;
    }

    async function requestJson(path, options) {
        const config = options || {};
        const headers = authHeaders(config.headers);
        let body = config.body;

        const isBlob = config.responseType === 'blob';

        if (body && !(body instanceof FormData)) {
            headers["Content-Type"] = "application/json";
            body = JSON.stringify(body);
        }

        const response = await fetch(buildApiUrl(path), {
            method: config.method || "GET",
            headers,
            body,
        });

        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json") ? await response.json() : null;

        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            const detail = payload && (payload.detail || payload.message);
            throw new Error(detail || `Request failed (${response.status})`);
        }

        if (isBlob) {
            return await response.blob(); 
        }

        if (payload && Object.prototype.hasOwnProperty.call(payload, "code")) {
            if (payload.code !== 0) {
                throw new Error(payload.message || "Request failed");
            }
            return payload.data;
        }

        return payload;
    }

    function avatarUrl(seed) {
         if (user && user.avatar) {
            const baseUrl = "http://127.0.0.1:8000"; 
            return user.avatar.startsWith("http") ? user.avatar : `${baseUrl}${user.avatar}`;
        }
        return `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(seed || "SeeMusic")}`;
    }

    window.SeeMusicApp = {
        STORAGE_KEYS,
        getApiBase,
        getApiOrigin,
        buildApiUrl,
        buildServerUrl,
        getAuthToken,
        getCurrentUser,
        setAuthSession,
        clearAuthSession,
        authHeaders,
        requestJson,
        avatarUrl,
    };
})();
