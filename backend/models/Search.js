const fs = require('fs');
const path = require('path');
const { slugify } = require('../utils/helpers');

const DATA_DIR = path.resolve(__dirname, '../../data');
const SEARCHES_FILE = path.join(DATA_DIR, 'searches.json');

// Ensure data directory exists
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

class SearchModel {
  constructor() {
    this.searches = new Map();
    this.loadFromDisk();
  }

  loadFromDisk() {
    // 1. Load from searches.json if exists
    if (fs.existsSync(SEARCHES_FILE)) {
      try {
        const raw = fs.readFileSync(SEARCHES_FILE, 'utf-8');
        const list = JSON.parse(raw);
        if (Array.isArray(list)) {
          list.forEach(item => this.searches.set(item.id, item));
        }
      } catch (err) {
        console.error('[SearchModel] Error loading searches.json:', err.message);
      }
    }

    // 2. Discover existing folder-based searches (from Python scraper data/searches/*)
    const searchesFolder = path.join(DATA_DIR, 'searches');
    if (fs.existsSync(searchesFolder)) {
      try {
        const folders = fs.readdirSync(searchesFolder, { withFileTypes: true });
        for (const f of folders) {
          if (f.isDirectory()) {
            const cfgFile = path.join(searchesFolder, f.name, 'config.json');
            if (fs.existsSync(cfgFile)) {
              try {
                const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf-8'));
                const id = cfg.name || f.name;
                if (!this.searches.has(id)) {
                  this.searches.set(id, {
                    id: id,
                    userId: 'default_user',
                    query: cfg.title || cfg.name || f.name,
                    city: cfg.city || 'chelyabinsk',
                    minPrice: cfg.min_price || 0,
                    maxPrice: cfg.max_price || 0,
                    filters: {
                      onlyProfit: false,
                      privateSellers: cfg.private_only || false,
                      withDelivery: false,
                      noDefects: true
                    },
                    isActive: true,
                    createdAt: Date.now() - 86400000,
                    lastCheckedAt: Date.now()
                  });
                }
              } catch (_) {}
            }
          }
        }
      } catch (err) {
        console.error('[SearchModel] Error scanning searches folder:', err.message);
      }
    }
  }

  saveToDisk() {
    try {
      const list = Array.from(this.searches.values());
      fs.writeFileSync(SEARCHES_FILE, JSON.stringify(list, null, 2), 'utf-8');
    } catch (err) {
      console.error('[SearchModel] Error saving searches.json:', err.message);
    }
  }

  getAll() {
    return Array.from(this.searches.values()).sort((a, b) => b.createdAt - a.createdAt);
  }

  getById(id) {
    return this.searches.get(id) || null;
  }

  create(data) {
    const query = (data.query || '').trim();
    const city = (data.city || 'chelyabinsk').trim();
    const cleanQ = slugify(query);
    const cleanCity = slugify(city);
    const id = `${cleanQ}_${cleanCity}` || `search_${Date.now()}`;

    const newSearch = {
      id: id,
      userId: data.userId || 'default_user',
      query: query,
      city: city,
      minPrice: Number(data.minPrice) || 0,
      maxPrice: Number(data.maxPrice) || 0,
      filters: {
        onlyProfit: Boolean(data.filters?.onlyProfit),
        privateSellers: Boolean(data.filters?.privateSellers),
        withDelivery: Boolean(data.filters?.withDelivery),
        excludeAccessories: data.filters?.excludeAccessories !== false,
        noDefects: data.filters?.noDefects !== false
      },
      isActive: true,
      createdAt: Date.now(),
      lastCheckedAt: null
    };

    this.searches.set(id, newSearch);
    this.saveToDisk();
    return newSearch;
  }

  delete(id) {
    const exists = this.searches.has(id);
    if (exists) {
      this.searches.delete(id);
      this.saveToDisk();

      // Clean folder in data/searches/<id> if it exists
      const folder = path.join(DATA_DIR, 'searches', id);
      if (fs.existsSync(folder)) {
        try {
          fs.rmSync(folder, { recursive: true, force: true });
        } catch (_) {}
      }

      // Also clean seeds files if present
      [
        path.resolve(__dirname, '../../searches_seeds.json'),
        path.resolve(__dirname, '../../frontend/searches_seeds.json')
      ].forEach(seedPath => {
        if (fs.existsSync(seedPath)) {
          try {
            const seeds = JSON.parse(fs.readFileSync(seedPath, 'utf-8'));
            if (seeds[id]) {
              delete seeds[id];
              fs.writeFileSync(seedPath, JSON.stringify(seeds, null, 2), 'utf-8');
            }
          } catch (_) {}
        }
      });

      return true;
    }
    return false;
  }

  update(id, patch) {
    const s = this.searches.get(id);
    if (!s) return null;
    Object.assign(s, patch);
    this.saveToDisk();
    return s;
  }
}

module.exports = new SearchModel();
