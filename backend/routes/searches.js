const express = require('express');
const router = express.Router();
const SearchModel = require('../models/Search');
const { scanSearch } = require('../services/avito-scraper');

// GET /api/searches - List all active searches
router.get('/', (req, res) => {
  try {
    const searches = SearchModel.getAll();
    res.json({
      success: true,
      count: searches.length,
      searches: searches
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST /api/searches - Create a new search
router.post('/', async (req, res) => {
  try {
    const { query, city, minPrice, maxPrice, filters } = req.body;
    if (!query || !query.trim()) {
      return res.status(400).json({ success: false, error: 'Query is required' });
    }

    const newSearch = SearchModel.create({
      query,
      city: city || 'chelyabinsk',
      minPrice: Number(minPrice) || 0,
      maxPrice: Number(maxPrice) || 0,
      filters: filters || {}
    });

    // Spawn scan in background
    scanSearch(newSearch).catch(err => console.error('[Route/Searches] Scan error:', err.message));

    res.status(201).json({
      success: true,
      search: newSearch
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// DELETE /api/searches/:id - Delete a search
router.delete('/:id', (req, res) => {
  try {
    const id = req.params.id;
    const ok = SearchModel.delete(id);
    if (!ok) {
      return res.status(404).json({ success: false, error: 'Search not found' });
    }
    res.json({
      success: true,
      id: id,
      message: 'Search deleted successfully'
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST /api/searches/:id/scan - Trigger immediate re-scan
router.post('/:id/scan', async (req, res) => {
  try {
    const id = req.params.id;
    const s = SearchModel.getById(id);
    if (!s) {
      return res.status(404).json({ success: false, error: 'Search not found' });
    }
    const count = await scanSearch(s);
    res.json({ success: true, count: count, id: id });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

module.exports = router;
