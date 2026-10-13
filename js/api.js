/**
 * AvitoRadar — API Client & Offline-first Cache Layer
 */

const BASE_URL = (typeof window !== 'undefined' && (window.location.hostname.includes('github.io') || (window.location.hostname === 'localhost' && window.location.port !== '7860')))
  ? 'https://avito-radar.onrender.com'
  : (typeof window !== 'undefined' && window.location.origin ? window.location.origin : 'https://avito-radar.onrender.com');

export const ApiService = {
  // --- Searches ---

  async getSearches() {
    try {
      const res = await fetch(`${BASE_URL}/api/searches`);
      if (res.ok) {
        const data = await res.json();
        if (data.searches && Array.isArray(data.searches)) {
          localStorage.setItem('avitoradar_searches_cache', JSON.stringify(data.searches));
          return data.searches;
        }
      }
    } catch (err) {
      console.warn('[API] getSearches fetch failed, using offline cache:', err.message);
    }

    // Offline / fallback cache
    const cached = localStorage.getItem('avitoradar_searches_cache');
    if (cached) {
      try { return JSON.parse(cached); } catch (_) {}
    }

    return [];
  },

  async createSearch(payload) {
    try {
      const res = await fetch(`${BASE_URL}/api/searches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        return data.search;
      }
    } catch (err) {
      console.warn('[API] createSearch API failed, saving locally:', err.message);
    }

    // Local offline fallback
    const id = `${payload.query.toLowerCase().replace(/[^a-z0-9]+/g, '_')}_${payload.city}`;
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
    localStorage.setItem('avitoradar_searches_cache', JSON.stringify(existing));
    return newSearch;
  },

  async deleteSearch(id) {
    try {
      await fetch(`${BASE_URL}/api/searches/${id}`, { method: 'DELETE' });
    } catch (err) {
      console.warn('[API] deleteSearch API offline, deleting locally:', err.message);
    }

    const existing = await this.getSearches();
    const updated = existing.filter(s => s.id !== id);
    localStorage.setItem('avitoradar_searches_cache', JSON.stringify(updated));
    return true;
  },

  async triggerScan(id) {
    try {
      const res = await fetch(`${BASE_URL}/api/searches/${id}/scan`, { method: 'POST' });
      return res.ok;
    } catch (_) {
      return false;
    }
  },

  // --- Lots ---

  async getLots(filters = {}) {
    try {
      const params = new URLSearchParams();
      if (filters.searchId) params.append('searchId', filters.searchId);
      if (filters.onlyProfit) params.append('onlyProfit', 'true');
      if (filters.privateSellers) params.append('privateSellers', 'true');
      if (filters.withDelivery) params.append('withDelivery', 'true');
      if (filters.noDefects) params.append('noDefects', 'true');
      if (filters.includeDismissed) params.append('includeDismissed', 'true');
      if (filters.q) params.append('q', filters.q);
      if (filters.sort) params.append('sort', filters.sort);

      const res = await fetch(`${BASE_URL}/api/lots?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        if (data.lots && Array.isArray(data.lots)) {
          // Merge with dismissed set
          const dismissedSet = this.getDismissedIds();
          data.lots.forEach(l => {
            if (dismissedSet.has(String(l.id))) l.isDismissed = true;
          });
          localStorage.setItem('avitoradar_lots_cache', JSON.stringify(data.lots));
          return data.lots;
        }
      }
    } catch (err) {
      console.warn('[API] getLots fetch failed, using offline cache:', err.message);
    }

    // Offline / fallback cache
    const cached = localStorage.getItem('avitoradar_lots_cache');
    if (cached) {
      try {
        let lots = JSON.parse(cached);
        const dismissedSet = this.getDismissedIds();
        lots.forEach(l => {
          if (dismissedSet.has(String(l.id))) l.isDismissed = true;
        });
        if (!filters.includeDismissed) lots = lots.filter(l => !l.isDismissed);
        if (filters.searchId && filters.searchId !== 'all') lots = lots.filter(l => l.searchId === filters.searchId);
        return lots;
      } catch (_) {}
    }

    return [];
  },

  // --- Vanish (Dismiss lot) ---

  async dismissLot(id) {
    const strId = String(id);
    const dismissed = this.getDismissedIds();
    dismissed.add(strId);
    localStorage.setItem('avitoradar_dismissed_ids', JSON.stringify(Array.from(dismissed)));

    try {
      await fetch(`${BASE_URL}/api/lots/${strId}/dismiss`, { method: 'POST' });
    } catch (_) {}

    return true;
  },

  async restoreLot(id) {
    const strId = String(id);
    const dismissed = this.getDismissedIds();
    dismissed.delete(strId);
    localStorage.setItem('avitoradar_dismissed_ids', JSON.stringify(Array.from(dismissed)));

    try {
      await fetch(`${BASE_URL}/api/lots/${strId}/restore`, { method: 'POST' });
    } catch (_) {}

    return true;
  },

  getDismissedIds() {
    try {
      const raw = localStorage.getItem('avitoradar_dismissed_ids');
      if (raw) return new Set(JSON.parse(raw));
    } catch (_) {}
    return new Set();
  }
};
