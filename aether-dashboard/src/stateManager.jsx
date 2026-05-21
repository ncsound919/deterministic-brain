/* ═══════════════════════════════════════════════════════════════
   STATE MANAGER - Global state with localStorage persistence
   Solves: state loss on navigation, no caching, no undo
   ═══════════════════════════════════════════════════════════════ */

import { useState, useEffect, useCallback, createContext, useContext } from 'react';

// ─── Storage Keys ──────────────────────────────────────────────
const STORAGE_KEYS = {
  PAGE_STATE: 'aether_page_state',
  API_CACHE: 'aether_api_cache',
  SESSION: 'aether_session',
  PREFERENCES: 'aether_preferences',
  ACTION_LOG: 'aether_action_log',
};

// ─── Cache Configuration ───────────────────────────────────────
const CACHE_TTL = {
  default: 30000,      // 30s
  health: 10000,       // 10s
  news: 60000,         // 60s
  betting: 45000,      // 45s
  scheduler: 15000,    // 15s
  skills: 120000,      // 2m
  soul: 300000,        // 5m
};

// ─── Utility Functions ─────────────────────────────────────────
function safeJSONParse(str, fallback = null) {
  try { return str ? JSON.parse(str) : fallback; }
  catch { return fallback; }
}

function getStorage(key, fallback = null) {
  try {
    const val = localStorage.getItem(key);
    return val ? safeJSONParse(val, fallback) : fallback;
  } catch { return fallback; }
}

function setStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.warn(`Storage write failed for ${key}:`, e);
  }
}

// ─── API Cache ─────────────────────────────────────────────────
class APICache {
  constructor() {
    this._cache = getStorage(STORAGE_KEYS.API_CACHE, {});
    this._pending = new Map();
  }

  get(key) {
    const entry = this._cache[key];
    if (!entry) return null;
    
    const now = Date.now();
    const ttl = entry.ttl || CACHE_TTL.default;
    
    if (now - entry.timestamp > ttl) {
      delete this._cache[key];
      this._save();
      return null;
    }
    
    return entry.data;
  }

  set(key, data, ttl = null) {
    this._cache[key] = {
      data,
      timestamp: Date.now(),
      ttl: ttl || CACHE_TTL.default,
    };
    this._save();
  }

  invalidate(key) {
    if (key) {
      delete this._cache[key];
    } else {
      this._cache = {};
    }
    this._save();
  }

  _save() {
    setStorage(STORAGE_KEYS.API_CACHE, this._cache);
  }

  // Cached fetch with deduplication
  async fetch(url, options = {}, ttl = null) {
    const cacheKey = `${url}:${JSON.stringify(options)}`;
    
    // Check cache first
    const cached = this.get(cacheKey);
    if (cached) return cached;
    
    // Deduplicate pending requests
    if (this._pending.has(cacheKey)) {
      return this._pending.get(cacheKey);
    }
    
    const promise = fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers }
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        this.set(cacheKey, data, ttl);
        this._pending.delete(cacheKey);
        return data;
      })
      .catch(err => {
        this._pending.delete(cacheKey);
        throw err;
      });
    
    this._pending.set(cacheKey, promise);
    return promise;
  }
}

export const apiCache = new APICache();

// ─── Page State Manager ────────────────────────────────────────
class PageStateManager {
  constructor() {
    this._state = getStorage(STORAGE_KEYS.PAGE_STATE, {});
  }

  getPageState(pageId, fallback = {}) {
    return this._state[pageId] || fallback;
  }

  setPageState(pageId, state) {
    this._state[pageId] = {
      ...this._state[pageId],
      ...state,
      _updatedAt: Date.now(),
    };
    this._save();
  }

  clearPageState(pageId) {
    delete this._state[pageId];
    this._save();
  }

  clearAll() {
    this._state = {};
    this._save();
  }

  _save() {
    setStorage(STORAGE_KEYS.PAGE_STATE, this._state);
  }
}

export const pageStateManager = new PageStateManager();

// ─── Action Log ────────────────────────────────────────────────
class ActionLog {
  constructor(maxEntries = 100) {
    this._log = getStorage(STORAGE_KEYS.ACTION_LOG, []);
    this._maxEntries = maxEntries;
  }

  add(action, details = {}) {
    const entry = {
      id: Date.now().toString(36),
      timestamp: new Date().toISOString(),
      action,
      details,
    };
    this._log.unshift(entry);
    if (this._log.length > this._maxEntries) {
      this._log = this._log.slice(0, this._maxEntries);
    }
    this._save();
    return entry;
  }

  get(limit = 20) {
    return this._log.slice(0, limit);
  }

  clear() {
    this._log = [];
    this._save();
  }

  _save() {
    setStorage(STORAGE_KEYS.ACTION_LOG, this._log);
  }
}

export const actionLog = new ActionLog();

// ─── Session Manager ───────────────────────────────────────────
class SessionManager {
  constructor() {
    this._session = getStorage(STORAGE_KEYS.SESSION, {
      id: crypto.randomUUID?.() || Math.random().toString(36).slice(2),
      startedAt: new Date().toISOString(),
      lastActive: new Date().toISOString(),
      visitCount: 1,
    });
  }

  get() {
    this._session.lastActive = new Date().toISOString();
    this._save();
    return this._session;
  }

  update(data) {
    this._session = { ...this._session, ...data };
    this._save();
  }

  incrementVisit() {
    this._session.visitCount = (this._session.visitCount || 1) + 1;
    this._save();
  }

  _save() {
    setStorage(STORAGE_KEYS.SESSION, this._session);
  }
}

export const sessionManager = new SessionManager();

// ─── React Hooks ───────────────────────────────────────────────

// Hook for persistent page state
export function usePageState(pageId, initialState = {}) {
  const [state, setState] = useState(() => {
    const saved = pageStateManager.getPageState(pageId);
    return { ...initialState, ...saved };
  });

  useEffect(() => {
    pageStateManager.setPageState(pageId, state);
  }, [pageId, state]);

  const update = useCallback((updates) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  const reset = useCallback(() => {
    setState(initialState);
    pageStateManager.clearPageState(pageId);
  }, [pageId, initialState]);

  return [state, update, reset];
}

// Hook for cached API data
export function useCachedAPI(url, options = {}, ttl = null) {
  const [data, setData] = useState(() => apiCache.get(`${url}:${JSON.stringify(options)}`));
  const [loading, setLoading] = useState(!data);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async (forceRefresh = false) => {
    const cacheKey = `${url}:${JSON.stringify(options)}`;
    
    if (!forceRefresh) {
      const cached = apiCache.get(cacheKey);
      if (cached) {
        setData(cached);
        setLoading(false);
        return cached;
      }
    }

    setLoading(true);
    setError(null);

    try {
      const result = await apiCache.fetch(url, options, ttl);
      setData(result);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [url, options, ttl]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refresh = useCallback(() => fetchData(true), [fetchData]);

  return { data, loading, error, refresh };
}

// ─── Context for Global State ──────────────────────────────────
const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [session] = useState(() => sessionManager.get());
  const [preferences, setPreferences] = useState(() => 
    getStorage(STORAGE_KEYS.PREFERENCES, {
      theme: 'dark',
      autoRefresh: true,
      refreshInterval: 10000,
      soundEnabled: false,
      compactMode: false,
    })
  );

  useEffect(() => {
    setStorage(STORAGE_KEYS.PREFERENCES, preferences);
  }, [preferences]);

  const updatePreference = useCallback((key, value) => {
    setPreferences(prev => ({ ...prev, [key]: value }));
  }, []);

  const value = {
    session,
    preferences,
    updatePreference,
    actionLog,
    apiCache,
    pageStateManager,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return context;
}

// ─── Keyboard Shortcuts ────────────────────────────────────────
export function useKeyboardShortcuts(shortcuts = {}) {
  useEffect(() => {
    const handler = (e) => {
      const key = `${e.ctrlKey || e.metaKey ? 'cmd+' : ''}${e.shiftKey ? 'shift+' : ''}${e.key.toLowerCase()}`;
      const shortcut = shortcuts[key];
      if (shortcut) {
        e.preventDefault();
        shortcut(e);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [shortcuts]);
}

// ─── Auto-Refresh Hook ─────────────────────────────────────────
export function useAutoRefresh(refreshFn, interval = 10000, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    
    refreshFn();
    const id = setInterval(refreshFn, interval);
    return () => clearInterval(id);
  }, [refreshFn, interval, enabled]);
}

// ─── Debounce Hook ─────────────────────────────────────────────
export function useDebounce(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);

  return debounced;
}

// ─── Notification / Toast System ───────────────────────────────
class NotificationManager {
  constructor() {
    this._listeners = [];
    this._toasts = [];
  }

  addListener(fn) {
    this._listeners.push(fn);
    return () => {
      this._listeners = this._listeners.filter(l => l !== fn);
    };
  }

  notify(message, type = 'info', duration = 5000) {
    const toast = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      message,
      type,
      duration,
      createdAt: Date.now(),
    };
    this._toasts.push(toast);
    this._emit();
    
    setTimeout(() => {
      this._toasts = this._toasts.filter(t => t.id !== toast.id);
      this._emit();
    }, duration);
  }

  dismiss(id) {
    this._toasts = this._toasts.filter(t => t.id !== id);
    this._emit();
  }

  clear() {
    this._toasts = [];
    this._emit();
  }

  getToasts() {
    return this._toasts;
  }

  _emit() {
    this._listeners.forEach(fn => fn([...this._toasts]));
  }
}

export const notifications = new NotificationManager();

export function useNotifications() {
  const [toasts, setToasts] = useState(() => notifications.getToasts());

  useEffect(() => {
    return notifications.addListener(setToasts);
  }, []);

  const notify = useCallback((message, type = 'info', duration = 5000) => {
    notifications.notify(message, type, duration);
  }, []);

  const dismiss = useCallback((id) => {
    notifications.dismiss(id);
  }, []);

  return { toasts, notify, dismiss };
}

// ─── Export Everything ─────────────────────────────────────────
export {
  getStorage,
  setStorage,
  CACHE_TTL,
};