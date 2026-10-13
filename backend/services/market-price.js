/**
 * Market price calculation and deal detection service.
 */

function calculateCleanMedian(prices) {
  if (!prices || prices.length === 0) return 0;
  const sorted = [...prices].filter(p => typeof p === 'number' && p > 0).sort((a, b) => a - b);
  if (sorted.length === 0) return 0;

  // Truncate bottom and top 10% outliers if enough sample size
  let slice = sorted;
  if (sorted.length >= 8) {
    const trim = Math.floor(sorted.length * 0.1);
    slice = sorted.slice(trim, sorted.length - trim);
  }

  const mid = Math.floor(slice.length / 2);
  if (slice.length % 2 === 0) {
    return Math.round((slice[mid - 1] + slice[mid]) / 2);
  }
  return Math.round(slice[mid]);
}

function annotateLotsWithMarket(lots) {
  if (!lots || lots.length === 0) return lots;

  // Filter out defective or combo listings from baseline median
  const validPrices = lots
    .filter(l => !l.isComboListing && !l.tags.some(t => t.includes('Дефект') || t.includes('Запчасти') || t.includes('Сборное')))
    .map(l => l.price)
    .filter(p => p > 0);

  const median = calculateCleanMedian(validPrices);

  lots.forEach(lot => {
    lot.marketPrice = median;
    if (median > 0 && lot.price > 0) {
      const diffPct = Math.round(((lot.price - median) / median) * 1000) / 10;
      lot.discount = diffPct;

      // Add badges/tags
      if (diffPct <= -20 && !lot.isComboListing) {
        if (!lot.tags.includes('🔥 Супер-цена')) lot.tags.unshift(`🔥 Выгодно (${diffPct}%)`);
      } else if (diffPct <= -12 && !lot.isComboListing) {
        if (!lot.tags.includes('🔥 Выгодно')) lot.tags.unshift(`🔥 Выгодно (${diffPct}%)`);
      }
    } else {
      lot.discount = 0;
    }
  });

  return lots;
}

module.exports = {
  calculateCleanMedian,
  annotateLotsWithMarket
};
