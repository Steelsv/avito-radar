/**
 * AvitoRadar - Unified Terminal Client
 * Standalone bundle with zero external module dependencies.
 * Works seamlessly in Telegram WebApp (iOS / Android / Desktop) and standalone browsers.
 */

// ==========================================================================
// 0. Immediate Global App Object (Ensures inline onclick never fails)
// ==========================================================================
window.app = window.app || {};

// ==========================================================================
// 1. Safe Storage Layer (Guards against iOS WebKit / iframe SecurityError)
// ==========================================================================
const SafeStorage = {
  _mem: new Map(),

  getItem(key) {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const val = window.localStorage.getItem(key);
        if (val !== null) return val;
      }
    } catch (_) {}
    return this._mem.get(key) || null;
  },

  setItem(key, val) {
    const strVal = String(val);
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, strVal);
      }
    } catch (_) {}
    this._mem.set(key, strVal);

    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.CloudStorage) {
        window.Telegram.WebApp.CloudStorage.setItem(key, strVal, () => {});
      }
    } catch (_) {}
  },

  removeItem(key) {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.removeItem(key);
      }
    } catch (_) {}
    this._mem.delete(key);

    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.CloudStorage) {
        window.Telegram.WebApp.CloudStorage.removeItem(key, () => {});
      }
    } catch (_) {}
  },

  async initCloudSync() {
    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.CloudStorage) {
        const searchKey = getUserStorageKey('searches');
        const favKey = getUserStorageKey('favorites');
        return new Promise((resolve) => {
          // The Telegram mock SDK in plain browsers may never call back -
          // never let cloud sync block the app bootstrap.
          const timer = setTimeout(resolve, 3000);
          try {
            window.Telegram.WebApp.CloudStorage.getItems([searchKey, favKey], (err, values) => {
              clearTimeout(timer);
              if (!err && values) {
                if (values[searchKey] && !window.localStorage?.getItem(searchKey)) {
                  SafeStorage.setItem(searchKey, values[searchKey]);
                }
                if (values[favKey] && !window.localStorage?.getItem(favKey)) {
                  SafeStorage.setItem(favKey, values[favKey]);
                }
              }
              resolve();
            });
          } catch (_) {
            // Old SDK builds throw WebAppMethodUnsupported synchronously
            // outside the Telegram client - treat as "no cloud storage".
            clearTimeout(timer);
            resolve();
          }
        });
      }
    } catch (_) {}
  }
};

// ==========================================================================
// 1.1 Multi-User Identity & Storage Key Scope
// ==========================================================================
function getCurrentUserId() {
  let uid = null;
  if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
    uid = String(window.Telegram.WebApp.initDataUnsafe.user.id).trim();
  }
  if (!uid) {
    try {
      if (typeof window !== 'undefined' && window.location) {
        const params = new URLSearchParams(window.location.search);
        const qUid = params.get('user_id');
        if (qUid && qUid.trim()) uid = qUid.trim();
      }
    } catch (_) {}
  }
  if (!uid) {
    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initData) {
        const params = new URLSearchParams(window.Telegram.WebApp.initData);
        const userStr = params.get('user');
        if (userStr) {
          const userObj = JSON.parse(userStr);
          if (userObj?.id) uid = String(userObj.id).trim();
        }
      }
    } catch (_) {}
  }
  if (!uid) {
    try {
      if (typeof window !== 'undefined' && window.location?.hash) {
        const hashParams = new URLSearchParams(window.location.hash.substring(1));
        const tgData = hashParams.get('tgWebAppData');
        if (tgData) {
          const parsed = new URLSearchParams(tgData);
          const userStr = parsed.get('user');
          if (userStr) {
            const userObj = JSON.parse(userStr);
            if (userObj?.id) uid = String(userObj.id).trim();
          }
        }
      }
    } catch (_) {}
  }

  if (uid) {
    SafeStorage.setItem('avitoradar_client_uid', uid);
    return uid;
  }

  let guestId = SafeStorage.getItem('avitoradar_client_uid');
  if (!guestId) {
    guestId = 'guest_' + Math.random().toString(36).substring(2, 10);
    SafeStorage.setItem('avitoradar_client_uid', guestId);
  }
  return guestId;
}

function getUserStorageKey(suffix) {
  const uid = getCurrentUserId();
  return `avitoradar_${suffix}_${uid}`;
}

function getApiHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const uid = getCurrentUserId();
  if (uid) headers['X-Telegram-User-Id'] = uid;
  if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initData) {
    headers['X-Telegram-Init-Data'] = window.Telegram.WebApp.initData;
  }
  return headers;
}

// ==========================================================================
// 2. City Abbreviation Mapping & Formatting Helpers
// ==========================================================================
const CITY_ABBR = {
  'челябинск': 'ЧЛБ',
  'chelyabinsk': 'ЧЛБ',
  'москва': 'МСК',
  'moskva': 'МСК',
  'санкт-петербург': 'СПБ',
  'sankt-peterburg': 'СПБ',
  'питер': 'СПБ',
  'екатеринбург': 'ЕКБ',
  'ekaterinburg': 'ЕКБ',
  'казань': 'КЗН',
  'kazan': 'КЗН',
  'новосибирск': 'НСК',
  'novosibirsk': 'НСК',
  'уфа': 'УФА',
  'ufa': 'УФА',
  'россия': 'РФ',
  'вся россия': 'РФ',
  'rossiya': 'РФ',
  'сочи': 'СОЧ',
  'sochi': 'СОЧ',
  'краснодар': 'КРД',
  'krasnodar': 'КРД',
  'тюмень': 'ТМН',
  'tyumen': 'ТМН',
  'самара': 'СМР',
  'samara': 'СМР',
  'нижний новгород': 'НН',
  'nizhniy_novgorod': 'НН',
  'пермь': 'ПРМ',
  'perm': 'ПРМ',
  'ростов-на-дону': 'РНД',
  'rostov': 'РНД',
  'волгоград': 'ВЛГ',
  'volgograd': 'ВЛГ',
  'воронеж': 'ВРЖ',
  'voronezh': 'ВРЖ',
  'омск': 'ОМС',
  'omsk': 'ОМС',
  'красноярск': 'КРС',
  'krasnoyarsk': 'КРС'
};

function getCityAbbr(cityName) {
  if (!cityName) return 'РФ';
  const key = String(cityName).trim().toLowerCase();
  if (CITY_ABBR[key]) return CITY_ABBR[key];
  for (const [k, abbr] of Object.entries(CITY_ABBR)) {
    if (key.includes(k) || k.includes(key)) return abbr;
  }
  return cityName.replace(/[^a-zA-Zа-яА-Я]/g, '').slice(0, 3).toUpperCase() || 'РФ';
}

function cleanQueryTitle(query) {
  if (!query) return '';
  let q = String(query).trim();
  const m = q.match(/«([^»]+)»/);
  if (m) {
    q = m[1];
  } else {
    q = q.replace(/:?\s*объявления\s+(для|в)\s+.*$/i, '')
         .replace(/объявления\s+в\s+.*$/i, '')
         .trim();
  }
  return q || String(query);
}

function formatSearchDisplay(search) {
  if (!search) return '';
  const abbr = getCityAbbr(search.city);
  const title = cleanQueryTitle(search.query || search.title || search.id);
  return `[${abbr}] ${title}`;
}

// ==========================================================================
// 3. Telegram WebApp Service
// ==========================================================================
const tg = window.Telegram?.WebApp;

const TelegramService = {
  isDesktop() {
    if (!tg) return !/Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    const p = (tg.platform || '').toLowerCase();
    if (['tdesktop', 'macos', 'web', 'weba', 'webk'].includes(p)) return true;
    if (['ios', 'android'].includes(p)) return false;
    return !/Android|iPhone|iPad|iPod/i.test(navigator.userAgent) && window.innerWidth >= 640;
  },

  isMobile() {
    return !this.isDesktop();
  },

  init() {
    document.body?.classList.add(this.isDesktop() ? 'platform-desktop' : 'platform-mobile');

    if (!tg) {
      console.log('[TelegramService] Running in web browser mode');
      this.updateFullscreenButton();
      return;
    }
    try {
      tg.ready();
      tg.headerColor = '#09090B';
      tg.backgroundColor = '#09090B';

      // Adapt base background to Telegram dark theme params when available
      try {
        const tpBg = tg.themeParams?.bg_color;
        if (tpBg && /^#?[0-9a-fA-F]{6}$/.test(tpBg)) {
          const hex = tpBg.replace('#', '');
          const lum = (parseInt(hex.slice(0, 2), 16) * 0.299 + parseInt(hex.slice(2, 4), 16) * 0.587 + parseInt(hex.slice(4, 6), 16) * 0.114) / 255;
          if (lum < 0.5) {
            document.documentElement.style.setProperty('--bg', '#' + hex);
            tg.headerColor = '#' + hex;
            tg.backgroundColor = '#' + hex;
          }
        }
      } catch (_) {}

      if (this.isDesktop()) {
        // Desktop (PC Telegram): stay in the default window, user can widen it manually.
        // No requestFullscreen() and no expand() here - fullscreen stays opt-in via the header button.
      } else {
        // Mobile (iPhone / Android): DO NOT force requestFullscreen (prevents notch / status bar overlap bugs).
        // Only use native tg.expand() for standard bottom-sheet expansion.
        try { tg.expand(); } catch (_) {}
      }

      // Prevent accidental swipe-to-close; keep vertical scroll intact (touch-only platforms)
      if (this.isMobile() && typeof tg.disableVerticalSwipes === 'function') {
        try { tg.disableVerticalSwipes(); } catch (_) {}
      } else if (this.isMobile() && tg.isVerticalSwipesEnabled !== undefined) {
        tg.isVerticalSwipesEnabled = false;
      }

      const updateSafeAreas = () => {
        if (this.isDesktop()) {
          // On PC desktop there is no hardware notch
          document.documentElement.style.setProperty('--safe-area-top', '0px');
          document.documentElement.style.setProperty('--safe-area-bottom', '0px');
          return;
        }

        let top = 0;
        if (tg.safeAreaInset?.top) top = Math.max(top, tg.safeAreaInset.top);
        if (tg.contentSafeAreaInset?.top) top = Math.max(top, tg.contentSafeAreaInset.top);

        if (top > 0) {
          document.documentElement.style.setProperty('--safe-area-top', `${top}px`);
        } else {
          document.documentElement.style.setProperty('--safe-area-top', 'max(env(safe-area-inset-top, 0px), 12px)');
        }

        let bottom = 0;
        if (tg.safeAreaInset?.bottom) bottom = Math.max(bottom, tg.safeAreaInset.bottom);
        if (tg.contentSafeAreaInset?.bottom) bottom = Math.max(bottom, tg.contentSafeAreaInset.bottom);
        if (bottom > 0) {
          document.documentElement.style.setProperty('--safe-area-bottom', `${bottom}px`);
        } else {
          document.documentElement.style.setProperty('--safe-area-bottom', 'max(env(safe-area-inset-bottom, 0px), 12px)');
        }
      };

      updateSafeAreas();
      if (typeof tg.onEvent === 'function') {
        tg.onEvent('safeAreaChanged', updateSafeAreas);
        tg.onEvent('contentSafeAreaChanged', updateSafeAreas);
        tg.onEvent('viewportChanged', updateSafeAreas);
        tg.onEvent('fullscreenChanged', () => {
          this.updateFullscreenButton();
        });
        tg.onEvent('fullscreenFailed', (err) => {
          console.warn('[TelegramService] fullscreenFailed:', err);
          try { tg.expand(); } catch (_) {}
        });
      }

      this.updateFullscreenButton();
    } catch (e) {
      console.warn('[TelegramService] Init warning:', e);
    }
  },

  updateFullscreenButton() {
    const btn = document.getElementById('btnFullscreen');
    if (!btn) return;

    const canFs = (tg && typeof tg.requestFullscreen === 'function') ||
                  (!tg && typeof document.documentElement.requestFullscreen === 'function');

    if (canFs && this.isDesktop()) {
      btn.style.display = 'inline-flex';
      const isFs = tg?.isFullscreen || Boolean(document.fullscreenElement);
      btn.title = isFs ? 'Выйти из полноэкранного режима' : 'На весь экран';
      const icon = document.getElementById('fullscreenIconExpand');
      if (icon) {
        if (isFs) {
          icon.innerHTML = `<path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>`;
        } else {
          icon.innerHTML = `<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>`;
        }
      }
    } else {
      btn.style.display = 'none';
    }
  },

  toggleFullscreen() {
    this.haptic('medium');
    if (tg && typeof tg.requestFullscreen === 'function') {
      try {
        if (tg.isFullscreen) {
          if (typeof tg.exitFullscreen === 'function') tg.exitFullscreen();
        } else {
          tg.requestFullscreen();
        }
      } catch (err) {
        console.warn('[TelegramService] toggleFullscreen error:', err);
      }
      setTimeout(() => this.updateFullscreenButton(), 200);
      return;
    }

    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
    setTimeout(() => this.updateFullscreenButton(), 200);
  },

  haptic(type = 'light') {
    if (!tg?.HapticFeedback) return;
    try {
      if (type === 'light') tg.HapticFeedback.impactOccurred('light');
      else if (type === 'medium') tg.HapticFeedback.impactOccurred('medium');
      else if (type === 'heavy') tg.HapticFeedback.impactOccurred('heavy');
      else if (type === 'selection') tg.HapticFeedback.selectionChanged();
      else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
      else if (type === 'warning') tg.HapticFeedback.notificationOccurred('warning');
      else if (type === 'error') tg.HapticFeedback.notificationOccurred('error');
    } catch (_) {}
  },

  openLink(url) {
    this.haptic('medium');
    if (tg?.openLink) {
      tg.openLink(url);
    } else {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  },

  openTelegramLink(url) {
    this.haptic('medium');
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(url);
    } else {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  },

  // Opens a Telegram Stars invoice. callback receives 'paid' | 'cancelled' | 'failed'.
  openInvoice(link, callback) {
    if (tg?.openInvoice) {
      try {
        tg.openInvoice(link, (status) => callback?.(status));
        return true;
      } catch (_) {}
    }
    return false;
  },

  getUser() {
    return tg?.initDataUnsafe?.user || null;
  }
};

// ==========================================================================
// 4. API Service & Offline Cache (Multi-Tenant Per User)
// ==========================================================================
const API_BASE_URL = (typeof window !== 'undefined' && (window.location.hostname.includes('github.io') || (window.location.hostname === 'localhost' && window.location.port !== '7860')))
  ? 'https://avito-radar.onrender.com'
  : (typeof window !== 'undefined' && window.location.origin ? window.location.origin : 'https://avito-radar.onrender.com');

const ApiService = {
  // Set when the last server request failed (drives the retry error state UI).
  networkFailed: false,

  async getSearches() {
    const key = getUserStorageKey('searches');
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/searches?user_id=${encodeURIComponent(uid)}`, {
        headers: getApiHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        if (data.searches && Array.isArray(data.searches)) {
          this.networkFailed = false;
          SafeStorage.setItem(key, JSON.stringify(data.searches));
          return data.searches;
        }
      }
      this.networkFailed = true;
    } catch (err) {
      this.networkFailed = true;
      console.warn('[API] getSearches network call failed, falling back to cache:', err.message);
    }

    const cached = SafeStorage.getItem(key);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed)) return parsed;
      } catch (_) {}
    }

    return [];
  },

  async createSearch(payload) {
    const key = getUserStorageKey('searches');
    const uid = getCurrentUserId();
    const bodyPayload = { ...payload, user_id: uid };
    try {
      const res = await fetch(`${API_BASE_URL}/api/searches?user_id=${encodeURIComponent(uid)}`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify(bodyPayload)
      });
      if (res.ok) {
        const data = await res.json();
        if (data.search) {
          const existing = await this.getSearches();
          const filtered = existing.filter(s => s.id !== data.search.id);
          filtered.unshift(data.search);
          SafeStorage.setItem(key, JSON.stringify(filtered));
          return data.search;
        }
        if (data.name) {
          const s = {
            id: data.name,
            query: payload.query,
            city: payload.city || 'Челябинск',
            minPrice: Number(payload.minPrice) || 0,
            isActive: true
          };
          const existing = await this.getSearches();
          const filtered = existing.filter(x => x.id !== s.id);
          filtered.unshift(s);
          SafeStorage.setItem(key, JSON.stringify(filtered));
          return s;
        }
      }
    } catch (err) {
      console.warn('[API] createSearch API offline, persisting locally:', err.message);
    }

    const id = `u${uid}_${payload.query.toLowerCase().replace(/[^a-z0-9а-яё]+/gi, '_')}_${payload.city || 'chelyabinsk'}`.replace(/^_+|_+$/g, '');
    const newSearch = {
      id: id,
      query: payload.query,
      city: payload.city || 'chelyabinsk',
      minPrice: Number(payload.minPrice) || 0,
      filters: payload.filters || {},
      isActive: true,
      createdAt: Date.now()
    };

    const existing = await this.getSearches();
    existing.unshift(newSearch);
    SafeStorage.setItem(key, JSON.stringify(existing));
    return newSearch;
  },

  async deleteSearch(id) {
    const key = getUserStorageKey('searches');
    const uid = getCurrentUserId();
    try {
      await fetch(`${API_BASE_URL}/api/searches/${encodeURIComponent(id)}?user_id=${encodeURIComponent(uid)}`, {
        method: 'DELETE',
        headers: getApiHeaders()
      });
    } catch (_) {}
    try {
      await fetch(`${API_BASE_URL}/api/searches/delete`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ name: id, id: id, user_id: uid })
      });
    } catch (_) {}

    const existing = await this.getSearches();
    const updated = existing.filter(s => s.id !== id);
    SafeStorage.setItem(key, JSON.stringify(updated));
    return true;
  },

  async triggerScan(id) {
    const uid = getCurrentUserId();
    try {
      const res = await fetch(`${API_BASE_URL}/api/searches/scan`, {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({ name: id, id: id, user_id: uid })
      });
      this.networkFailed = !res.ok;
      return res.ok;
    } catch (_) {
      this.networkFailed = true;
      return false;
    }
  },

  async getLots(filters = {}) {
    const key = getUserStorageKey('lots');
    const uid = getCurrentUserId();
    try {
      const params = new URLSearchParams();
      params.append('user_id', uid);
      if (filters.searchId && filters.searchId !== 'all') {
        params.append('searchId', filters.searchId);
      }
      const res = await fetch(`${API_BASE_URL}/api/lots?${params.toString()}`, {
        headers: getApiHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        if (data.lots && Array.isArray(data.lots)) {
          this.networkFailed = false;
          const dismissedSet = this.getDismissedIds();
          data.lots.forEach(l => {
            if (dismissedSet.has(String(l.id))) l.isDismissed = true;
          });
          SafeStorage.setItem(key, JSON.stringify(data.lots));
          return data.lots;
        }
      }
      this.networkFailed = true;
    } catch (err) {
      this.networkFailed = true;
      console.warn('[API] getLots fetch failed, using offline fallback:', err.message);
    }

    const cached = SafeStorage.getItem(key);
    if (cached) {
      try {
        let lots = JSON.parse(cached);
        const dismissedSet = this.getDismissedIds();
        lots.forEach(l => {
          if (dismissedSet.has(String(l.id))) l.isDismissed = true;
        });
        return lots;
      } catch (_) {}
    }

    return [];
  },

  async dismissLot(id) {
    const strId = String(id);
    const dismissed = this.getDismissedIds();
    dismissed.add(strId);
    SafeStorage.setItem(getUserStorageKey('dismissed'), JSON.stringify(Array.from(dismissed)));

    const uid = getCurrentUserId();
    try {
      await fetch(`${API_BASE_URL}/api/lots/${strId}/dismiss?user_id=${encodeURIComponent(uid)}`, {
        method: 'POST',
        headers: getApiHeaders()
      });
    } catch (_) {}
    return true;
  },

  async restoreLot(id) {
    const strId = String(id);
    const dismissed = this.getDismissedIds();
    dismissed.delete(strId);
    SafeStorage.setItem(getUserStorageKey('dismissed'), JSON.stringify(Array.from(dismissed)));

    const uid = getCurrentUserId();
    try {
      await fetch(`${API_BASE_URL}/api/lots/${strId}/restore?user_id=${encodeURIComponent(uid)}`, {
        method: 'POST',
        headers: getApiHeaders()
      });
    } catch (_) {}
    return true;
  },

  getDismissedIds() {
    try {
      const raw = SafeStorage.getItem(getUserStorageKey('dismissed'));
      if (raw) return new Set(JSON.parse(raw));
    } catch (_) {}
    return new Set();
  }
};

// ==========================================================================
// 5. Application State
// ==========================================================================
const State = {
  searches: [],
  currentSearchId: 'all',
  lots: [],
  activeFilter: 'all', // 'all', 'noaccessories', 'deals', 'private', 'delivery', 'nodefects', 'dismissed'
  searchQuery: '',
  sortMode: 'deal', // 'deal', 'cheap', 'expensive', 'date'
  viewMode: 'cards', // 'cards', 'table', 'fav', 'searches'
  excludeAccessories: true,
  favorites: [],
  modalLot: null,
  pendingDeleteId: null,
  networkError: false,
  lastStaleToastAt: null
};

// Load saved favorites and accessories preference safely
try {
  const savedFavs = SafeStorage.getItem(getUserStorageKey('favorites'));
  if (savedFavs) State.favorites = JSON.parse(savedFavs);
  const savedAcc = SafeStorage.getItem(getUserStorageKey('exclude_accessories'));
  if (savedAcc !== null) State.excludeAccessories = savedAcc === 'true';
} catch (_) {}

// ==========================================================================
// 5.1 Accessory & Parts Intelligent Classifier (Prevents median breakage)
// ==========================================================================
const BIKE_ACC_RE = /\b(?:покрышк\w*|покрышка|покрышки|велопокрышк\w*|шины\s+для\s+вело\w*|велокамер\w*|бескамерк\w*|герметик\s+для\s+шин|сидушк\w*|сидень\w*\s+для|седл\w*|седло|подседел\w*|подседельный|педал\w*|педали|контактн\w*\s+педал\w*|топталк\w*|дропбар\w*|вынос\s+руля|вынос\w*|грипс\w*|обмотк\w*\s+руля|манетк\w*|шифтер\w*|рулев\w*\s+колонк\w*|велоцепь\w*|цепь\s+для\s+вело\w*|кассет\w*\s+(?:shimano|sram|для)|трещотк\w*|ротор\w*\s+(?:тормозной|shimano|sram|160|180)|калипер\w*|тормозн\w*\s+колодк\w*|байкпакинг\w*|велосумк\w*|подседельн\w*\s+сумк\w*|сумк\w*\s+(?:на\s+раму|на\s+руль|под\s+раму)|багажник\s+(?:для\s+вело|на\s+вело|велосипедн)|велокрыл\w*|крылья\s+(?:для\s+вело|на\s+вело)|флягодержател\w*|велокомпьютер\w*|велофара\w*|велофонар\w*|велошлем\w*|велотуфл\w*|велоформ\w*|джерси\s+(?:вело|для)|велоперчатк\w*|велозамок\w*|велонасос\w*|насос\s+(?:высокого\s+давления|для\s+вело)|велостанок\w*|подножк\w*\s+для\s+вело|фреймсет\w*|веловилк\w*)\b/i;

const ELEC_ACC_RE = /\b(?:чехол\w*|чехлы|чехольчик\w*|бампер\s+(?:на|для)|стекл\w*\s+(?:на|для|защитн\w*)|защитн\w*\s+стекл\w*|пленк\w*\s+(?:на|для|защитн\w*)|гидрогелев\w*|ремешок\w*|браслет\s+(?:для|на)|стилус\w*|s-pen|spen|apple\s+pencil|наконечник\w*|амбушюр\w*|кейс\s+(?:для|от)|коробк\w*\s+от|коробка\s+(?:от|для)|док-станци\w*|подставк\w*\s+(?:для|под)|держатель\s+(?:для|в\s+авто)|magsafe|зарядк\w*|зарядн\w*\s+устройств\w*|блок\w*\s+питания|сетев\w*\s+адаптер|кабел\w*|провод\w*|шнур\w*|переходник\w*|кулер\w*|вентилятор\w*|радиатор\w*|термопаст\w*|термопрокладк\w*|райзер\w*|бэкплейт\w*|кронштейн\w*|болтик\w*|винтик\w*|винты|шлейф\w*|заглушк\w*|кейкап\w*|свитч\w*|коврик\s+для\s+мыши)\b/i;

const AUTO_ACC_RE = /\b(?:коврик\w*|автоковрик\w*|авточехл\w*|накидк\w*\s+на\s+сидень\w*|брызговик\w*|дворник\w*|щетк\w*\s+стеклоочистител\w*|дефлектор\w*|ветровик\w*|колпак\w*\s+на\s+колес\w*|подлокотник\w*|видеорегистратор\w*|радар-детектор\w*|ароматизатор\w*|пахучк\w*|шильдик\w*|спойлер\w*|оплетк\w*\s+на\s+руль|органайзер\s+в\s+багажник|фаркоп\w*|автобокс\w*|бампер\w*|капот\w*|дверь\w*|двери|крыло\w*|фара\w*|фары|фонарь\w*|фонари|лобовое(?:\s+стекло)?|стеклоподъемник\w*|генератор\w*|стартер\w*|мкпп|акпп|двигатель\w*|глушитель\w*|радиатор\w*|амортизатор\w*|стойк\w*|рычаг\w*|рулев\w*\s+рейк\w*|суппорт\w*|сцеплени\w*|тормозн\w*\s+диск\w*|авторазбор\w*)\b/i;

const GEN_ACC_RE = /\b(?:аксессуар\w*|запчаст\w*|комплектующ\w*|детал\w*|расходник\w*|креплени\w*|крепеж\w*|ремкомплект\w*|насадк\w*|сменн\w*)\b/i;

function isAccessoryLot(lot, searchQuery = '') {
  if (!lot) return false;
  if (lot.isAccessory) return true;
  if (Array.isArray(lot.tags) && lot.tags.some(t => t.includes('Аксессуар') || t.includes('Велозапчасть') || t.includes('Автоаксессуар'))) {
    return true;
  }
  const t = (lot.title || '').toLowerCase();
  const q = (searchQuery || '').toLowerCase();
  const queryMentions = (term) => q && term && term.length >= 3 && q.includes(term.toLowerCase());

  const mBike = BIKE_ACC_RE.exec(t);
  if (mBike && !queryMentions(mBike[0].substring(0, 4))) return true;

  if (/\bруль\b/i.test(t) && !/\bруль\b/i.test(q)) {
    if (/гравел|велосипед|шоссе|mtb|баран|дропбар/i.test(t + ' ' + q)) return true;
  }

  if (/\bкамер[аыеу]\b/i.test(t) && !/\bкамер/i.test(q)) {
    if (/вело|700|28|29|26|27\.5|schwalbe|continental|maxxis|gravel|гравел/i.test(t)) return true;
  }

  const mElec = ELEC_ACC_RE.exec(t);
  if (mElec && !queryMentions(mElec[0].substring(0, 4))) return true;

  const mAuto = AUTO_ACC_RE.exec(t);
  if (mAuto && !queryMentions(mAuto[0].substring(0, 4))) return true;

  const mGen = GEN_ACC_RE.exec(t);
  if (mGen && !queryMentions(mGen[0].substring(0, 4))) return true;

  if (/^(?:для|на|к|под)\s+/i.test(t) && !/^(?:для|на|к|под)\s+/i.test(q)) return true;

  return false;
}

// 5.2 Defect & iCloud Lock and Exchange / Trade Detection
const ICLOUD_RE = /\b(?:icloud|айклауд|аклауд|activation\s*lock|заблокирован(?:\s+на\s+icloud|\s+apple|\s+экран|\s+телефон|\s+айфон)?|забыли\s+(?:пароль|код|apple\s*id|айклауд)|apple\s*id|lock\b|лоченый|залочен\w*|mdm\b|корпоративн\w*\s+профиль|bypass|байпас|демо\b|demo\b)\b/iu;
const DONOR_DEAD_RE = /\b(?:на\s+запчаст\w*|на\s+разбор\w*|под\s+восстановлен\w*|не\s+включается|не\s+включ\w*|труп\b|донор\w*|плата\s+мертв\w*|кирпич\b|после\s+воды|утоплен\w*|залит\w*|условно\s*рабоч\w*|отвал\b|артефакт\w*|после\s+дтп|битый|битая|битое|битые|перевертыш|не\s+на\s+ходу|без\s+двигателя|без\s+мотора|запрет(?:\s+рег\w*|\s+регистрац\w*)?|без\s+документов|без\s+птс|в\s+разбор|авторазбор\w*|утиль\b)\b/iu;
const SCREEN_DEFECT_RE = /\b(?:разбит\w*\s+экран|треснут\w*\s+экран|черн\w*\s+экран|полос\w*\s+на\s+экран|экран\s+под\s+замену|битый\s+экран|пятн\w*\s+на\s+диспле\w*|пятно\s+на\s+экран\w*)\b/iu;
const GENERAL_DEFECT_RE = /(?<!не\s)бит(?:ый|ая|ое|ые)\b|заблок|блокировк|icloud|айклауд|аклауд|на\s+запчаст|на\s+разбор|под\s+восстановл|не\s+включ|не\s+работает|разбит|треснут|утоплен|после\s+воды|залит|не\s+ловит|плата\s+мертв|донор|условно\s*рабоч|проблем\w*\s+с\s+драйвер|кернел|kernel|отвал|артефакт|полос\w*\s+на\s+экран|черн\w*\s+экран|не\s+выводит|прогрет|после\s+майнинг|вылетает|код\s*43|ошибк\w*\s+43/iu;
const EXCHANGE_RE = /\b(?:обмен\s+(?:на|с\s+доплатой)|обменяю\s+(?:на|с\s+доплатой)|обменял\s+бы\s+на|рассмотрю\s+обмен\s+на|только\s+обмен|обмен\b|обменяю\b|куплю\b|ищу\b|приму\s+в\s+дар|скупка\b|выкуп\b|спрос\b)\b/iu;

function getLotDefectInfo(lot) {
  if (!lot) return { isDefect: false, type: null, label: null };
  if (lot.isDefect) {
    return {
      isDefect: true,
      type: lot.defectType || 'general',
      label: lot.defectType === 'icloud' ? 'iCloud Lock' : (lot.defectType === 'dead' ? 'На запчасти' : 'Дефект')
    };
  }
  const text = `${lot.title || ''} ${lot.description || ''}`;
  if (ICLOUD_RE.test(text)) return { isDefect: true, type: 'icloud', label: 'iCloud Lock' };
  if (DONOR_DEAD_RE.test(text)) return { isDefect: true, type: 'dead', label: 'На запчасти' };
  if (SCREEN_DEFECT_RE.test(text)) return { isDefect: true, type: 'screen', label: 'Дефект экрана' };
  if (GENERAL_DEFECT_RE.test(text)) return { isDefect: true, type: 'general', label: 'Дефект' };
  if (Array.isArray(lot.tags) && lot.tags.some(t => t.includes('Дефект') || t.includes('Заблокирован') || t.includes('На запчасти'))) {
    return { isDefect: true, type: 'general', label: 'Дефект' };
  }
  return { isDefect: false, type: null, label: null };
}

function isExchangeLot(lot) {
  if (!lot) return false;
  if (lot.isExchangeOrWtb) return true;
  const title = (lot.title || '').toLowerCase();
  const text = `${title} ${(lot.description || '').toLowerCase()}`;
  if (/\b(?:обмен|обменяю|обменял\s+бы|куплю|ищу|скупка|выкуп|спрос)\b/iu.test(title)) return true;
  if (/\b(?:обмен\s+(?:на|с\s+доплатой)|обменяю\s+(?:на|с\s+доплатой)|обменял\s+бы\s+на|рассмотрю\s+обмен)\b/iu.test(text) && (lot.price === null || lot.price <= 1000)) return true;
  if (Array.isArray(lot.tags) && lot.tags.some(t => t.includes('Обмен') || t.includes('Спрос'))) return true;
  return false;
}

const WB_L = '(?<![\\p{L}\\p{N}])';
const WB_R = '(?![\\p{L}\\p{N}])';

function parseQueryIntent(query) {
  if (!query || typeof query !== 'string') return null;
  const q = query.trim().toLowerCase();

  const intent = {
    raw: query,
    brand: null,
    modelNumber: null,
    subModel: null,
    storage: null,
    features: []
  };

  // 1. Storage detection
  const storageRe = new RegExp(`${WB_L}(64|128|256|512)\\s*(?:gb|гб)?${WB_R}|${WB_L}(1|2)\\s*(?:tb|тб)${WB_R}`, 'iu');
  const storageMatch = q.match(storageRe);
  if (storageMatch) {
    intent.storage = storageMatch[1] ? `${storageMatch[1]}gb` : `${storageMatch[2]}tb`;
  }

  // 2. Feature detection
  const esimRe = new RegExp(`${WB_L}(?:esim|есим|e-sim)${WB_R}`, 'iu');
  if (esimRe.test(q)) {
    intent.features.push('esim');
  }

  // 3. Apple iPhone detection
  const iphoneRe = new RegExp(`${WB_L}(?:iphone|айфон|айфончик)${WB_R}|${WB_L}1[1-6]\\s*(?:pro|max|plus|mini|про|макс|плюс|мини)?${WB_R}`, 'iu');
  if (iphoneRe.test(q)) {
    intent.brand = 'apple_iphone';
    const genRe = new RegExp(`${WB_L}(1[1-6]|[78]|xr|xs|x|se)${WB_R}`, 'iu');
    const genMatch = q.match(genRe);
    if (genMatch) {
      intent.modelNumber = genMatch[1].toLowerCase();
    }

    const proMaxRe = new RegExp(`${WB_L}(?:pro\\s*max|про\\s*макс)${WB_R}`, 'iu');
    const proRe = new RegExp(`${WB_L}(?:pro|про)${WB_R}`, 'iu');
    const plusRe = new RegExp(`${WB_L}(?:plus|плюс)${WB_R}`, 'iu');
    const miniRe = new RegExp(`${WB_L}(?:mini|мини)${WB_R}`, 'iu');

    if (proMaxRe.test(q)) {
      intent.subModel = 'pro max';
    } else if (proRe.test(q)) {
      intent.subModel = 'pro';
    } else if (plusRe.test(q)) {
      intent.subModel = 'plus';
    } else if (miniRe.test(q)) {
      intent.subModel = 'mini';
    } else {
      if (intent.storage || intent.features.length > 0) {
        intent.subModel = 'base';
      } else {
        intent.subModel = 'any';
      }
    }
    return intent;
  }

  // 4. CPU detection (Ryzen, Core i, Xeon)
  const ryzenRe = new RegExp(`${WB_L}(?:ryzen|райзен|r)\\s*([3579])\\s*[-]?\\s*(\\d{4}[a-z0-9]*)?${WB_R}`, 'iu');
  const ryzenMatch = q.match(ryzenRe);
  if (ryzenMatch) {
    intent.brand = 'amd_ryzen';
    intent.subModel = `r${ryzenMatch[1]}`;
    if (ryzenMatch[2]) intent.modelNumber = ryzenMatch[2].toLowerCase();
    return intent;
  }

  const intelRe = new RegExp(`${WB_L}(?:intel\\s+)?(?:core\\s+)?i([3579])\\s*[-]?\\s*(\\d{4,5}[a-z0-9]*)?${WB_R}`, 'iu');
  const intelMatch = q.match(intelRe);
  if (intelMatch) {
    intent.brand = 'intel_core';
    intent.subModel = `i${intelMatch[1]}`;
    if (intelMatch[2]) intent.modelNumber = intelMatch[2].toLowerCase();
    return intent;
  }

  const xeonRe = new RegExp(`${WB_L}xeon\\s*(?:e[357]\\s*)?(\\d{4}[a-z0-9\\s]*v\\d|\\d{4}[a-z0-9]*)${WB_R}`, 'iu');
  const xeonMatch = q.match(xeonRe);
  if (xeonMatch) {
    intent.brand = 'intel_xeon';
    intent.modelNumber = xeonMatch[1].toLowerCase().replace(/\s+/g, '');
    return intent;
  }

  // 5. GPU detection
  const gpuRe = new RegExp(`${WB_L}(rtx|gtx|rx)\\s*(\\d{3,4})\\s*(ti\\s*super|super|ti|xtx|xt)?${WB_R}`, 'iu');
  const gpuMatch = q.match(gpuRe);
  if (gpuMatch) {
    intent.brand = gpuMatch[1].toLowerCase();
    intent.modelNumber = gpuMatch[2];
    intent.subModel = (gpuMatch[3] || '').replace(/\s+/g, ' ').trim().toLowerCase() || 'any';
    return intent;
  }

  // 5. PlayStation / Console detection
  const psRe = new RegExp(`${WB_L}(?:playstation|ps|пс)\\s*([345])${WB_R}`, 'iu');
  const psMatch = q.match(psRe);
  if (psMatch) {
    intent.brand = 'playstation';
    intent.modelNumber = psMatch[1];
    const psProRe = new RegExp(`${WB_L}(?:pro|про)${WB_R}`, 'iu');
    const psSlimRe = new RegExp(`${WB_L}(?:slim|слим)${WB_R}`, 'iu');
    if (psProRe.test(q)) intent.subModel = 'pro';
    else if (psSlimRe.test(q)) intent.subModel = 'slim';
    else intent.subModel = 'any';
    return intent;
  }

  // 6. Generic brand + model number
  const numRe = new RegExp(`${WB_L}([\\p{L}]{2,})\\s+(\\d{1,4}[\\p{L}]?)${WB_R}`, 'iu');
  const numMatch = q.match(numRe);
  if (numMatch) {
    intent.brand = numMatch[1].toLowerCase();
    intent.modelNumber = numMatch[2].toLowerCase();
    return intent;
  }

  return intent;
}

function parseItemModel(title, description = '') {
  const t = (title || '').toLowerCase();
  const full = `${t} ${description}`.toLowerCase();

  const item = {
    brand: null,
    modelNumber: null,
    subModel: null,
    storage: null,
    features: []
  };

  const storageRe = new RegExp(`${WB_L}(64|128|256|512)\\s*(?:gb|гб)?${WB_R}|${WB_L}(1|2)\\s*(?:tb|тб)${WB_R}`, 'iu');
  const storageMatch = t.match(storageRe);
  if (storageMatch) {
    item.storage = storageMatch[1] ? `${storageMatch[1]}gb` : `${storageMatch[2]}tb`;
  }

  const esimRe = new RegExp(`${WB_L}(?:esim|есим|e-sim)${WB_R}`, 'iu');
  if (esimRe.test(full)) {
    item.features.push('esim');
  }

  const iphoneRe = new RegExp(`${WB_L}(?:iphone|айфон|айфончик)${WB_R}|${WB_L}1[1-6]\\s*(?:pro|max|plus|mini|про|макс|плюс|мини)?${WB_R}`, 'iu');
  if (iphoneRe.test(t)) {
    item.brand = 'apple_iphone';
    const genRe = new RegExp(`${WB_L}(1[1-6]|[78]|xr|xs|x|se)${WB_R}`, 'iu');
    const genMatch = t.match(genRe);
    if (genMatch) {
      item.modelNumber = genMatch[1].toLowerCase();
    }

    const proMaxRe = new RegExp(`${WB_L}(?:pro\\s*max|про\\s*макс)${WB_R}`, 'iu');
    const proRe = new RegExp(`${WB_L}(?:pro|про)${WB_R}`, 'iu');
    const plusRe = new RegExp(`${WB_L}(?:plus|плюс)${WB_R}`, 'iu');
    const miniRe = new RegExp(`${WB_L}(?:mini|мини)${WB_R}`, 'iu');

    if (proMaxRe.test(t)) {
      item.subModel = 'pro max';
    } else if (proRe.test(t)) {
      item.subModel = 'pro';
    } else if (plusRe.test(t)) {
      item.subModel = 'plus';
    } else if (miniRe.test(t)) {
      item.subModel = 'mini';
    } else {
      item.subModel = 'base';
    }
    return item;
  }

  // CPU
  const ryzenRe = new RegExp(`${WB_L}(?:ryzen|райзен|r)\\s*([3579])\\s*[-]?\\s*(\\d{4}[a-z0-9]*)?${WB_R}`, 'iu');
  const ryzenMatch = t.match(ryzenRe);
  if (ryzenMatch) {
    item.brand = 'amd_ryzen';
    item.subModel = `r${ryzenMatch[1]}`;
    if (ryzenMatch[2]) item.modelNumber = ryzenMatch[2].toLowerCase();
    return item;
  }

  const intelRe = new RegExp(`${WB_L}(?:intel\\s+)?(?:core\\s+)?i([3579])\\s*[-]?\\s*(\\d{4,5}[a-z0-9]*)?${WB_R}`, 'iu');
  const intelMatch = t.match(intelRe);
  if (intelMatch) {
    item.brand = 'intel_core';
    item.subModel = `i${intelMatch[1]}`;
    if (intelMatch[2]) item.modelNumber = intelMatch[2].toLowerCase();
    return item;
  }

  const xeonRe = new RegExp(`${WB_L}xeon\\s*(?:e[357]\\s*)?(\\d{4}[a-z0-9\\s]*v\d|\\d{4}[a-z0-9]*)${WB_R}`, 'iu');
  const xeonMatch = t.match(xeonRe);
  if (xeonMatch) {
    item.brand = 'intel_xeon';
    item.modelNumber = xeonMatch[1].toLowerCase().replace(/\s+/g, '');
    return item;
  }

  const gpuRe = new RegExp(`${WB_L}(rtx|gtx|rx)\\s*(\\d{3,4})\\s*(ti\\s*super|super|ti|xtx|xt)?${WB_R}`, 'iu');
  const gpuMatch = t.match(gpuRe);
  if (gpuMatch) {
    item.brand = gpuMatch[1].toLowerCase();
    item.modelNumber = gpuMatch[2];
    item.subModel = (gpuMatch[3] || '').replace(/\s+/g, ' ').trim().toLowerCase() || 'base';
    return item;
  }

  const psRe = new RegExp(`${WB_L}(?:playstation|ps|пс)\\s*([345])${WB_R}`, 'iu');
  const psMatch = t.match(psRe);
  if (psMatch) {
    item.brand = 'playstation';
    item.modelNumber = psMatch[1];
    const psProRe = new RegExp(`${WB_L}(?:pro|про)${WB_R}`, 'iu');
    const psSlimRe = new RegExp(`${WB_L}(?:slim|слим)${WB_R}`, 'iu');
    if (psProRe.test(t)) item.subModel = 'pro';
    else if (psSlimRe.test(t)) item.subModel = 'slim';
    else item.subModel = 'base';
    return item;
  }

  const numRe = new RegExp(`${WB_L}([\\p{L}]{2,})\\s+(\\d{1,4}[\\p{L}]?)${WB_R}`, 'iu');
  const numMatch = t.match(numRe);
  if (numMatch) {
    item.brand = numMatch[1].toLowerCase();
    item.modelNumber = numMatch[2].toLowerCase();
    return item;
  }

  return item;
}

function isItemMatchingSearch(itemTitle, itemDesc, query) {
  if (!query || !query.trim()) return true;
  const intent = parseQueryIntent(query);
  if (!intent || !intent.modelNumber) return true;

  const parsedItem = parseItemModel(itemTitle, itemDesc);

  // 1. Generation / Model number check: STRICT
  if (intent.modelNumber && parsedItem.modelNumber) {
    if (intent.modelNumber !== parsedItem.modelNumber) {
      return false;
    }
  } else if (intent.modelNumber && !parsedItem.modelNumber) {
    const t = (itemTitle || '').toLowerCase();
    const conflictingGen = t.match(new RegExp(`${WB_L}(1[1-6]|[78]|xr|xs|x)${WB_R}`, 'iu'));
    if (conflictingGen && conflictingGen[1].toLowerCase() !== intent.modelNumber) {
      return false;
    }
  }

  // 2. Sub-model check
  if (intent.subModel && intent.subModel !== 'any') {
    if (intent.subModel === 'base') {
      if (parsedItem.subModel && parsedItem.subModel !== 'base') {
        return false;
      }
    } else {
      if (parsedItem.subModel !== intent.subModel) {
        return false;
      }
    }
  }

  // 3. Storage check
  if (intent.storage && parsedItem.storage) {
    if (intent.storage !== parsedItem.storage) {
      return false;
    }
  }

  // 4. Feature check
  if (intent.features && intent.features.length > 0) {
    for (const feat of intent.features) {
      if (!parsedItem.features.includes(feat)) {
        return false;
      }
    }
  }

  return true;
}

// ==========================================================================
// 5.9 SL UI Library Controllers (MIT License, Copyright (c) 2026 SLtowl)
// Adapted from https://github.com/SLtowl/sl-ui-library - components:
// matte-glide-toggle, matte-range-slider, matte-like, matte-retry-feedback.
// Palette lives in css/styles.css; controllers keep their original motion
// and keyboard / reduced-motion behavior.
// ==========================================================================
const SLUI = (() => {
  const mounted = new WeakMap();

  // matte-toggle controller (selection category) - native checkbox + status
  function mountToggle(root, { onChange } = {}) {
    if (mounted.has(root)) return mounted.get(root);
    if (typeof onChange !== 'undefined' && typeof onChange !== 'function') throw new TypeError('onChange must be a function.');
    const input = root?.querySelector('input[type="checkbox"]');
    const status = root?.querySelector('[data-status]');
    if (!input || !status) throw new TypeError('A native checkbox and visible status are required.');
    const view = root.ownerDocument.defaultView;
    const lifecycle = new view.AbortController();
    const motion = view.matchMedia('(prefers-reduced-motion: reduce)');
    let feedbackAnimation = null, destroyed = false;
    const on = (target, type, callback) => target.addEventListener(type, callback, { signal: lifecycle.signal });

    function settle() { feedbackAnimation?.cancel(); feedbackAnimation = null; }
    function feedback() {
      if (motion.matches) return;
      settle();
      const target = root.querySelector('.sl-toggle__emblem');
      if (!target?.animate) return;
      feedbackAnimation = target.animate(
        [{ transform: 'scale(1)' }, { transform: 'scale(.96)', offset: .36 }, { transform: 'scale(1)' }],
        { duration: 420, easing: 'cubic-bezier(.4,0,.2,1)' }
      );
      const animation = feedbackAnimation;
      animation.onfinish = () => { if (feedbackAnimation === animation) settle(); };
    }
    function render({ animate = false, emit = false } = {}) {
      if (destroyed) return;
      root.dataset.checked = String(input.checked);
      status.textContent = input.checked ? input.dataset.on || 'On' : input.dataset.off || 'Off';
      status.setAttribute('aria-live', 'polite');
      if (animate) feedback();
      else settle();
      if (emit) {
        onChange?.(input.checked);
        root.dispatchEvent(new view.CustomEvent('togglechange', { bubbles: true, composed: true, detail: { checked: input.checked } }));
      }
    }
    function setChecked(value, { emit = false, animate = true } = {}) {
      if (destroyed) return;
      input.checked = Boolean(value);
      render({ animate, emit });
    }

    on(input, 'change', () => render({ animate: true, emit: true }));
    on(motion, 'change', () => { if (motion.matches) settle(); });
    if (input.form) on(input.form, 'reset', () => queueMicrotask(() => setChecked(input.defaultChecked, { animate: false })));
    render();

    const controller = {
      setChecked,
      reset() { setChecked(input.defaultChecked, { animate: false }); },
      destroy() { if (destroyed) return; destroyed = true; settle(); lifecycle.abort(); mounted.delete(root); },
      get checked() { return input.checked; },
    };
    mounted.set(root, controller);
    return controller;
  }

  // matte-slider controller (sliders category) - native range + live output
  function mountSlider(root, { onChange, formatValue } = {}) {
    if (mounted.has(root)) return mounted.get(root);
    if (onChange !== undefined && typeof onChange !== 'function') throw new TypeError('onChange must be a function.');
    if (formatValue !== undefined && typeof formatValue !== 'function') throw new TypeError('formatValue must be a function.');
    const inputs = [...root.querySelectorAll('input[type="range"]')];
    const output = root.querySelector('[data-output]');
    if (!inputs.length || !output) throw new TypeError('A native range and output are required.');
    const lifecycle = new AbortController();
    const view = root.ownerDocument.defaultView;
    const dual = inputs.length === 2;
    const labels = root.dataset.labels?.split(',');
    const format = value => formatValue ? String(formatValue(value)) : dual ? '$' + value : value + '%';
    const track = root.querySelector('.slider-track');
    let dragging = null, destroyed = false;
    const values = () => inputs.map(input => input.valueAsNumber);
    const percent = input => (input.valueAsNumber - Number(input.min)) / (Number(input.max) - Number(input.min)) * 100;
    function render(changed, emit = false) {
      if (destroyed) return;
      if (dual) {
        if (inputs[0].valueAsNumber > inputs[1].valueAsNumber) {
          if (changed === inputs[0]) inputs[0].value = inputs[1].value;
          else inputs[1].value = inputs[0].value;
        }
        root.style.setProperty('--low', percent(inputs[0]) + '%');
        root.style.setProperty('--high', percent(inputs[1]) + '%');
        inputs[0].setAttribute('aria-valuemax', inputs[1].value);
        inputs[1].setAttribute('aria-valuemin', inputs[0].value);
        for (const input of inputs) input.setAttribute('aria-valuetext', format(input.valueAsNumber));
        output.textContent = format(inputs[0].valueAsNumber) + ' - ' + format(inputs[1].valueAsNumber);
      } else {
        const p = percent(inputs[0]);
        root.style.setProperty('--high', p + '%');
        root.style.setProperty('--position', p + '%');
        if (root.hasAttribute('data-centered')) {
          const center = (0 - Number(inputs[0].min)) / (Number(inputs[0].max) - Number(inputs[0].min)) * 100;
          root.style.setProperty('--low', Math.min(p, center) + '%');
          root.style.setProperty('--high', Math.max(p, center) + '%');
        }
        output.textContent = labels ? labels[inputs[0].valueAsNumber] : format(inputs[0].valueAsNumber);
        inputs[0].setAttribute('aria-valuetext', output.textContent);
        for (const marker of root.querySelectorAll('[data-step]')) marker.classList.toggle('is-current', Number(marker.dataset.step) === inputs[0].valueAsNumber);
      }
      if (emit) {
        onChange?.(values());
        root.dispatchEvent(new view.CustomEvent('sliderchange', { bubbles: true, detail: { values: values() } }));
      }
    }
    root.addEventListener('input', event => { if (inputs.includes(event.target)) render(event.target, true); }, { signal: lifecycle.signal });
    // In the dual control, native thumbs drag normally. Empty-track dragging uses
    // the nearest thumb, with pointer capture, while both inputs remain focusable.
    if (dual) {
      const updatePointer = event => {
        const rect = track.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left - 12) / (rect.width - 24)));
        const min = Number(dragging.min), max = Number(dragging.max), step = Number(dragging.step) || 1;
        dragging.value = String(min + Math.round(ratio * (max - min) / step) * step);
        dragging.dispatchEvent(new view.Event('input', { bubbles: true }));
      };
      track.addEventListener('pointerdown', event => {
        if (event.button !== 0 || inputs.includes(event.target) || dragging) return;
        const candidates = inputs.filter(input => !input.disabled);
        if (!candidates.length) return;
        const rect = track.getBoundingClientRect();
        const p = (event.clientX - rect.left - 12) / (rect.width - 24) * 100;
        dragging = candidates.reduce((nearest, input) => Math.abs(percent(input) - p) < Math.abs(percent(nearest) - p) ? input : nearest);
        dragging.focus({ preventScroll: true });
        track.setPointerCapture(event.pointerId);
        updatePointer(event);
        event.preventDefault();
      }, { signal: lifecycle.signal });
      track.addEventListener('pointermove', event => { if (dragging && track.hasPointerCapture(event.pointerId)) updatePointer(event); }, { signal: lifecycle.signal });
      const finish = () => { const input = dragging; dragging = null; input?.dispatchEvent(new view.Event('change', { bubbles: true })); };
      track.addEventListener('pointerup', finish, { signal: lifecycle.signal });
      track.addEventListener('pointercancel', finish, { signal: lifecycle.signal });
      track.addEventListener('lostpointercapture', finish, { signal: lifecycle.signal });
    }
    function reset() {
      if (destroyed) return;
      inputs.forEach(input => { input.value = input.defaultValue; });
      render();
    }
    inputs[0].form?.addEventListener('reset', () => queueMicrotask(reset), { signal: lifecycle.signal });
    // History restoration can replace native values after module initialization.
    view.addEventListener('pageshow', () => render(), { signal: lifecycle.signal });
    render();
    const controller = { reset, get values() { return values(); }, destroy() { destroyed = true; dragging = null; lifecycle.abort(); mounted.delete(root); } };
    mounted.set(root, controller);
    return controller;
  }

  // matte-like heartbeat (buttons category) - pulse a heart element in place
  function pulseLikeHeart(heart, pressed) {
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    if (motion.matches || !heart?.animate) return;
    const frames = pressed
      ? [{ transform: 'scale(1)' }, { transform: 'scale(.9)', offset: .18 }, { transform: 'scale(1.14)', offset: .5 }, { transform: 'scale(.985)', offset: .8 }, { transform: 'scale(1)' }]
      : [{ transform: 'scale(1)' }, { transform: 'scale(.94)', offset: .4 }, { transform: 'scale(1)' }];
    heart.animate(frames, { duration: pressed ? 620 : 420, easing: 'cubic-bezier(.4,0,.2,1)' });
  }

  // matte-retry controller (feedback category) - actionable async error state.
  // Strings localized to Russian; state machine matches the original controller.
  function mountRetry(root, { onAction } = {}) {
    if (mounted.has(root)) return mounted.get(root);
    if (typeof onAction !== 'function') throw new TypeError('onAction must be a function.');
    const q = s => root.querySelector(s);
    const card = q('.fb-retry-card');
    const button = q('[data-action="retry"]');
    const titleEl = q('[data-title]');
    const detailEl = q('[data-detail]');
    const stateLabel = q('[data-state-label]');
    const live = q('[data-live]');
    const error = q('[data-error]');
    if (!card || !button || !titleEl || !live || !error) throw new TypeError('Retry needs its card, button, title and live regions.');
    const view = root.ownerDocument.defaultView;
    const lifecycle = new view.AbortController();
    let destroyed = false, state = 'error', request = null;

    function announce(text, isError = false) { live.textContent = isError ? '' : text; error.textContent = isError ? text : ''; }
    function setState(value) {
      state = value;
      card.dataset.state = value;
      const busy = value === 'pending';
      button.setAttribute('aria-disabled', String(busy || value === 'complete'));
      button.setAttribute('aria-busy', String(busy));
      titleEl.textContent = busy ? 'Повторяем запрос' : value === 'complete' ? 'Данные загружены' : 'Не удалось загрузить данные';
      detailEl.textContent = busy ? 'Проверяем соединение с сервером…' : value === 'complete' ? 'Продолжайте с того же места.' : 'Сервер не отвечает. Ваши радары и избранное сохранены на этом устройстве.';
      if (stateLabel) stateLabel.textContent = busy ? 'ПОДОЖДИТЕ' : value === 'complete' ? 'ОНЛАЙН' : 'ОШИБКА ЗАПРОСА';
      button.textContent = busy ? 'Пробуем…' : value === 'complete' ? 'Обновить' : 'Повторить';
    }
    async function run() {
      if (destroyed || state === 'pending') return false;
      const current = new view.AbortController();
      request = current;
      setState('pending');
      announce('Запрос запущен.');
      try {
        await onAction({ signal: current.signal });
        if (destroyed || current.signal.aborted) return false;
        request = null;
        setState('complete');
        announce('Данные загружены.');
        return true;
      } catch (err) {
        if (destroyed) return false;
        request = null;
        setState('error');
        announce('Не удалось выполнить запрос. Попробуйте ещё раз.', err?.name !== 'AbortError');
        return false;
      }
    }
    button.addEventListener('click', () => { if (button.getAttribute('aria-disabled') !== 'true') void run(); }, { signal: lifecycle.signal });
    setState('error');
    const controller = {
      run,
      get state() { return state; },
      destroy() { if (destroyed) return; destroyed = true; request?.abort(); lifecycle.abort(); mounted.delete(root); }
    };
    mounted.set(root, controller);
    return controller;
  }

  return { mountToggle, mountSlider, mountRetry, pulseLikeHeart };
})();
