(function () {
    const STORAGE_KEYS = {
        apiBase: "seemusic.transcription.apiBase",
        authToken: "seemusic.auth.token",
        currentUser: "seemusic.auth.user",
        loggedIn: "seeMusic_isLoggedIn",
    };
    const SHARED_HEADER_STYLE_ID = "seemusic-shared-header-user-style";

    const DEFAULT_BACKEND_ORIGIN = window.location.protocol.startsWith("http")
        ? window.location.origin
        : "http://127.0.0.1:8000";
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

    function avatarUrl(inputData) {
        if (typeof inputData === "object" && inputData !== null && inputData.avatar) {
            const timestamp = Date.now();
            const path = inputData.avatar.startsWith("http") ? inputData.avatar : `${getApiOrigin()}${inputData.avatar}`;
            return path.includes("?") ? `${path}&t=${timestamp}` : `${path}?t=${timestamp}`;
        }

        let seed = "SeeMusic";
        if (typeof inputData === "string" && inputData.trim()) {
            seed = inputData.trim();
        } else if (typeof inputData === "object" && inputData !== null) {
            const displaySeed = [inputData.nickname, inputData.username, inputData.email]
                .find((value) => typeof value === "string" && value.trim());
            if (displaySeed) {
                seed = displaySeed.trim();
            }
        }

        return `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(seed)}`;
    }

    function ensureSharedHeaderUserStyles() {
        if (typeof document === "undefined" || !document.head || document.getElementById(SHARED_HEADER_STYLE_ID)) {
            return;
        }

        const style = document.createElement("style");
        style.id = SHARED_HEADER_STYLE_ID;
        style.textContent = `
            .sm-page-user {
                display: inline-flex;
                align-items: center;
                gap: 14px;
                min-width: 0;
                padding: 10px 16px;
                border-radius: 999px;
                background: rgba(249, 250, 252, 0.96);
                border: 1px solid #edf1f5;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
                color: #1d3557;
            }

            .sm-page-user--link {
                text-decoration: none;
                transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
            }

            .sm-page-user--link:hover,
            .sm-page-user--link:focus-visible {
                transform: translateY(-1px);
                border-color: rgba(69, 123, 157, 0.32);
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.09);
            }

            .sm-page-user__avatar-wrap {
                width: 56px;
                height: 56px;
                border-radius: 999px;
                overflow: hidden;
                flex-shrink: 0;
                display: block;
                background: linear-gradient(135deg, #e5eef6 0%, #c9dff1 45%, #f9d8dd 100%);
            }

            .sm-page-user__avatar {
                width: 100%;
                height: 100%;
                display: block;
                object-fit: cover;
            }

            .sm-page-user__body {
                min-width: 0;
                display: flex;
                flex-direction: column;
                gap: 4px;
            }

            .sm-page-user__name {
                color: #2f3440;
                font-size: 1rem;
                font-weight: 700;
                line-height: 1.15;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .sm-page-user__meta {
                color: #7c8793;
                font-size: 0.76rem;
                line-height: 1.2;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            @media (max-width: 768px) {
                .sm-page-user {
                    gap: 12px;
                    padding: 9px 13px;
                }

                .sm-page-user__avatar-wrap {
                    width: 46px;
                    height: 46px;
                }

                .sm-page-user__name {
                    font-size: 0.95rem;
                }

                .sm-page-user__meta {
                    font-size: 0.72rem;
                }
            }
        `;
        document.head.appendChild(style);
    }

    function getDisplayName(user, fallbackName = "游客模式") {
        if (!user || typeof user !== "object") {
            return fallbackName;
        }
        const displayName = [user.nickname, user.username, user.email]
            .find((value) => typeof value === "string" && value.trim());
        return displayName ? displayName.trim() : fallbackName;
    }

    function syncPageUsers(options) {
        const config = options || {};
        const root = config.root || document;
        if (!root || typeof root.querySelectorAll !== "function") {
            return {
                user: null,
                displayName: config.fallbackName || "游客模式",
                avatarSrc: avatarUrl(config.fallbackSeed || "SeeMusic"),
                loggedIn: false,
            };
        }

        ensureSharedHeaderUserStyles();
        const hasUserOverride = Object.prototype.hasOwnProperty.call(config, "user");
        const user = hasUserOverride ? config.user : getCurrentUser();
        const displayName = config.displayName || getDisplayName(user, config.fallbackName || "游客模式");
        const avatarSrc = avatarUrl(user || config.fallbackSeed || "SeeMusic");

        root.querySelectorAll(config.containerSelector || "[data-seemusic-user]").forEach((container) => {
            const avatarElement = container.querySelector("[data-seemusic-user-avatar]");
            const nameElement = container.querySelector("[data-seemusic-user-name]");

            if (avatarElement) {
                avatarElement.src = avatarSrc;
                avatarElement.alt = `${displayName} avatar`;
            }
            if (nameElement) {
                nameElement.textContent = displayName;
            }
        });

        return {
            user,
            displayName,
            avatarSrc,
            loggedIn: Boolean(user),
        };
    }

    ensureSharedHeaderUserStyles();

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
        getDisplayName,
        syncPageUsers,
    };
})();
