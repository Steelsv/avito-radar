const express = require('express');
const router = express.Router();
const LotModel = require('../models/Lot');

// GET /api/lots - List lots with filters
router.get('/', (req, res) => {
  try {
    const filters = {
      searchId: req.query.searchId || req.query.search_id,
      onlyProfit: req.query.onlyProfit === 'true' || req.query.deals === 'true',
      privateSellers: req.query.privateSellers === 'true' || req.query.private === 'true',
      withDelivery: req.query.withDelivery === 'true' || req.query.delivery === 'true',
      noDefects: req.query.noDefects === 'true' || req.query.nodefects === 'true',
      includeDismissed: req.query.includeDismissed === 'true',
      q: req.query.q || req.query.search,
      sort: req.query.sort || 'deal'
    };

    const lots = LotModel.getAll(filters);
    res.json({
      success: true,
      count: lots.length,
      lots: lots
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST /api/lots/:id/dismiss - Vanish (hide) lot
router.post('/:id/dismiss', (req, res) => {
  try {
    const id = req.params.id;
    LotModel.dismiss(id);
    res.json({
      success: true,
      id: id,
      isDismissed: true,
      message: 'Lot vanished successfully'
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST /api/lots/:id/restore - Restore previously dismissed lot
router.post('/:id/restore', (req, res) => {
  try {
    const id = req.params.id;
    LotModel.restore(id);
    res.json({
      success: true,
      id: id,
      isDismissed: false,
      message: 'Lot restored successfully'
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

module.exports = router;
