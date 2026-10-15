const BIKE_ACCESSORIES_REGEX = /(?<![\p{L}\p{N}])(?:покрышк\p{L}*|покрышка|покрышки|велопокрышк\p{L}*|шины\s+для\s+вело\p{L}*|велокамер\p{L}*|бескамерк\p{L}*|герметик\s+для\s+шин|сидушк\p{L}*|сидень\p{L}*\s+для|седл\p{L}*|седло|подседел\p{L}*|подседельный|педал\p{L}*|педали|контактн\p{L}*\s+педал\p{L}*|топталк\p{L}*|дропбар\p{L}*|вынос\s+руля|вынос\p{L}*|грипс\p{L}*|обмотк\p{L}*\s+руля|манетк\p{L}*|шифтер\p{L}*|рулев\p{L}*\s+колонк\p{L}*|велоцепь\p{L}*|цепь\s+для\s+вело\p{L}*|кассет\p{L}*\s+(?:shimano|sram|для)|трещотк\p{L}*|ротор\p{L}*\s+(?:тормозной|shimano|sram|160|180)|калипер\p{L}*|тормозн\p{L}*\s+колодк\p{L}*|байкпакинг\p{L}*|велосумк\p{L}*|подседельн\p{L}*\s+сумк\p{L}*|сумк\p{L}*\s+(?:на\s+раму|на\s+руль|под\s+раму)|багажник\s+(?:для\s+вело|на\s+вело|велосипедн)|велокрыл\p{L}*|крылья\s+(?:для\s+вело|на\s+вело)|флягодержател\p{L}*|велокомпьютер\p{L}*|велофара\p{L}*|велофонар\p{L}*|велошлем\p{L}*|велотуфл\p{L}*|велоформ\p{L}*|джерси\s+(?:вело|для)|велоперчатк\p{L}*|велозамок\p{L}*|велонасос\p{L}*|насос\s+(?:высокого\s+давления|для\s+вело)|велостанок\p{L}*|подножк\p{L}*\s+для\s+вело|фреймсет\p{L}*|веловилк\p{L}*)(?![\p{L}\p{N}])/iu;

const ELECTRONICS_ACCESSORIES_REGEX = /(?<![\p{L}\p{N}])(?:чехол\p{L}*|чехлы|чехольчик\p{L}*|бампер\s+(?:на|для)|стекл\p{L}*\s+(?:на|для|защитн\p{L}*)|защитн\p{L}*\s+стекл\p{L}*|пленк\p{L}*\s+(?:на|для|защитн\p{L}*)|гидрогелев\p{L}*|ремешок\p{L}*|браслет\s+(?:для|на)|стилус\p{L}*|s-pen|spen|apple\s+pencil|наконечник\p{L}*|амбушюр\p{L}*|кейс\s+(?:для|от)|коробк\p{L}*\s+от|коробка\s+(?:от|для)|док-станци\p{L}*|подставк\p{L}*\s+(?:для|под)|держатель\s+(?:для|в\s+авто)|magsafe|зарядк\p{L}*|зарядн\p{L}*\s+устройств\p{L}*|блок\p{L}*\s+питания|сетев\p{L}*\s+адаптер|кабел\p{L}*|провод\p{L}*|шнур\p{L}*|переходник\p{L}*|кулер\p{L}*|вентилятор\p{L}*|радиатор\p{L}*|термопаст\p{L}*|термопрокладк\p{L}*|райзер\p{L}*|бэкплейт\p{L}*|кронштейн\p{L}*|болтик\p{L}*|винтик\p{L}*|винты|шлейф\p{L}*|заглушк\p{L}*|кейкап\p{L}*|свитч\p{L}*|коврик\s+для\s+мыши)(?![\p{L}\p{N}])/iu;

const AUTO_ACCESSORIES_REGEX = /(?<![\p{L}\p{N}])(?:коврик\p{L}*|автоковрик\p{L}*|авточехл\p{L}*|накидк\p{L}*\s+на\s+сидень\p{L}*|брызговик\p{L}*|дворник\p{L}*|щетк\p{L}*\s+стеклоочистител\p{L}*|дефлектор\p{L}*|ветровик\p{L}*|колпак\p{L}*\s+на\s+колес\p{L}*|подлокотник\p{L}*|видеорегистратор\p{L}*|радар-детектор\p{L}*|ароматизатор\p{L}*|пахучк\p{L}*|шильдик\p{L}*|спойлер\p{L}*|оплетк\p{L}*\s+на\s+руль|органайзер\s+в\s+багажник|фаркоп\p{L}*|автобокс\p{L}*)(?![\p{L}\p{N}])/iu;

const GENERAL_ACCESSORIES_REGEX = /(?<![\p{L}\p{N}])(?:аксессуар\p{L}*|запчаст\p{L}*|комплектующ\p{L}*|детал\p{L}*|расходник\p{L}*|креплени\p{L}*|крепеж\p{L}*|ремкомплект\p{L}*|насадк\p{L}*|сменн\p{L}*)(?![\p{L}\p{N}])/iu;

function isAccessoryOrPart(title, description = '', searchQuery = '') {
  const t = (title || '').toLowerCase();
  const q = (searchQuery || '').toLowerCase();

  const queryMentions = (term) => q && term && term.length >= 3 && q.includes(term.toLowerCase());

  const mBike = BIKE_ACCESSORIES_REGEX.exec(t);
  if (mBike && !queryMentions(mBike[0].substring(0, 4))) return { isAccessory: true, tag: '🛡️ 🚲 Велозапчасть / Аксессуар' };

  if (/(?<![\p{L}\p{N}])руль(?![\p{L}\p{N}])/iu.test(t) && !/(?<![\p{L}\p{N}])руль(?![\p{L}\p{N}])/iu.test(q)) {
    if (/гравел|велосипед|шоссе|mtb|баран|дропбар/iu.test(t + ' ' + q)) {
      return { isAccessory: true, tag: '🛡️ 🚲 Велозапчасть / Аксессуар' };
    }
  }

  if (/(?<![\p{L}\p{N}])камер[аыеу](?![\p{L}\p{N}])/iu.test(t) && !/(?<![\p{L}\p{N}])камер/iu.test(q)) {
    if (/вело|700|28|29|26|27\.5|schwalbe|continental|maxxis|gravel|гравел/iu.test(t)) {
      return { isAccessory: true, tag: '🛡️ 🚲 Велозапчасть / Аксессуар' };
    }
  }

  const mElec = ELECTRONICS_ACCESSORIES_REGEX.exec(t);
  if (mElec && !queryMentions(mElec[0].substring(0, 4))) return { isAccessory: true, tag: '🛡️ 🧩 Аксессуар / Расходник' };

  const mAuto = AUTO_ACCESSORIES_REGEX.exec(t);
  if (mAuto && !queryMentions(mAuto[0].substring(0, 4))) return { isAccessory: true, tag: '🛡️ 🚗 Автоаксессуар / Расходник' };

  const mGen = GENERAL_ACCESSORIES_REGEX.exec(t);
  if (mGen && !queryMentions(mGen[0].substring(0, 4))) return { isAccessory: true, tag: '🛡️ 🔧 Запчасти / Комплектующие' };

  if (/^(?:для|на|к|под)\s+/i.test(t) && !/^(?:для|на|к|под)\s+/i.test(q)) {
    return { isAccessory: true, tag: '🛡️ 🧩 Аксессуар / Комплектующее' };
  }

  return { isAccessory: false, tag: null };
}

function calculateCleanMedian(prices) {
  if (!prices || prices.length === 0) return 0;
  let sorted = [...prices].filter(p => typeof p === 'number' && p > 0).sort((a, b) => a - b);
  if (sorted.length === 0) return 0;

  // Detect lower-tail outlier gap if high value distribution exists (protect against cheap accessories)
  if (sorted.length >= 4) {
    const upperHalf = sorted.slice(Math.floor(sorted.length / 2));
    const upperMed = upperHalf[Math.floor(upperHalf.length / 2)];
    if (upperMed >= 15000) {
      const cutoff = Math.max(1000, Math.floor(upperMed * 0.25));
      const trimmed = sorted.filter(p => p >= cutoff);
      if (trimmed.length >= 3) sorted = trimmed;
    } else if (upperMed >= 5000) {
      const cutoff = Math.max(500, Math.floor(upperMed * 0.20));
      const trimmed = sorted.filter(p => p >= cutoff);
      if (trimmed.length >= 3) sorted = trimmed;
    }
  }

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

  // 1. Storage detection (64, 128, 256, 512, 1tb / 1тб)
  const storageRe = new RegExp(`${WB_L}(64|128|256|512)\\s*(?:gb|гб)?${WB_R}|${WB_L}(1|2)\\s*(?:tb|тб)${WB_R}`, 'iu');
  const storageMatch = q.match(storageRe);
  if (storageMatch) {
    intent.storage = storageMatch[1] ? `${storageMatch[1]}gb` : `${storageMatch[2]}tb`;
  }

  // 2. Feature detection (esim, etc.)
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

  // 4. GPU detection (RTX 4070, RX 6700 XT, etc.)
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

  // 6. Generic brand + model number (e.g., Format 5222, BMW 3, Camry 70)
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

  // Storage
  const storageRe = new RegExp(`${WB_L}(64|128|256|512)\\s*(?:gb|гб)?${WB_R}|${WB_L}(1|2)\\s*(?:tb|тб)${WB_R}`, 'iu');
  const storageMatch = t.match(storageRe);
  if (storageMatch) {
    item.storage = storageMatch[1] ? `${storageMatch[1]}gb` : `${storageMatch[2]}tb`;
  }

  // eSIM
  const esimRe = new RegExp(`${WB_L}(?:esim|есим|e-sim)${WB_R}`, 'iu');
  if (esimRe.test(full)) {
    item.features.push('esim');
  }

  // iPhone
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

  // GPU
  const gpuRe = new RegExp(`${WB_L}(rtx|gtx|rx)\\s*(\\d{3,4})\\s*(ti\\s*super|super|ti|xtx|xt)?${WB_R}`, 'iu');
  const gpuMatch = t.match(gpuRe);
  if (gpuMatch) {
    item.brand = gpuMatch[1].toLowerCase();
    item.modelNumber = gpuMatch[2];
    item.subModel = (gpuMatch[3] || '').replace(/\s+/g, ' ').trim().toLowerCase() || 'base';
    return item;
  }

  // PlayStation
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

  // Generic brand + model number
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
      return false; // e.g. query 15 vs item 13 -> REJECT!
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

  // 4. Feature check (e.g. esim)
  if (intent.features && intent.features.length > 0) {
    for (const feat of intent.features) {
      if (!parsedItem.features.includes(feat)) {
        return false;
      }
    }
  }

  return true;
}

function annotateLotsWithMarket(lots, searchQuery = '') {
  if (!lots || lots.length === 0) return lots;

  // 1. Tag accessories and check model mismatch
  lots.forEach(lot => {
    if (!Array.isArray(lot.tags)) {
      lot.tags = [];
    }

    const accCheck = isAccessoryOrPart(lot.title, lot.description, searchQuery);
    if (accCheck.isAccessory) {
      lot.isAccessory = true;
      if (accCheck.tag && !lot.tags.includes(accCheck.tag)) {
        lot.tags.unshift(accCheck.tag);
      }
    } else if (lot.isAccessory === undefined) {
      lot.isAccessory = false;
    }

    // Model mismatch check
    lot.isMismatchedModel = !isItemMatchingSearch(lot.title, lot.description, searchQuery);
    if (lot.isMismatchedModel && !lot.tags.some(t => t.includes('Другая модель'))) {
      lot.tags.push('⚠️ Другая модель');
    }
  });

  // 2. Filter valid lots that strictly match query and are not accessories, defective, or combo listings
  const validLots = lots.filter(l =>
    !l.isMismatchedModel &&
    !l.isAccessory &&
    !l.isComboListing &&
    !(Array.isArray(l.tags) && l.tags.some(t => t.includes('Дефект') || t.includes('Запчасти') || t.includes('Сборное') || t.includes('Аксессуар') || t.includes('Другая модель'))) &&
    l.price > 0
  );

  // Group valid lots by sub-model segment (e.g. "base", "pro", "pro max", "plus")
  const segmentPrices = new Map();
  validLots.forEach(lot => {
    const parsed = parseItemModel(lot.title, lot.description);
    const segKey = parsed.subModel || 'base';
    if (!segmentPrices.has(segKey)) segmentPrices.set(segKey, []);
    segmentPrices.get(segKey).push(lot.price);
  });

  const segmentMedians = new Map();
  for (const [key, prices] of segmentPrices.entries()) {
    segmentMedians.set(key, calculateCleanMedian(prices));
  }

  // Global clean median across all valid matching items
  const overallMedian = calculateCleanMedian(validLots.map(l => l.price));

  // 3. Annotate each lot against its sub-model segment median
  lots.forEach(lot => {
    if (lot.isMismatchedModel) {
      // Mismatched items should NOT get a misleading high market price or deal tags
      lot.marketPrice = null;
      lot.discount = 0;
      return;
    }

    const parsed = parseItemModel(lot.title, lot.description);
    const segKey = parsed.subModel || 'base';
    const targetMedian = segmentMedians.get(segKey) || overallMedian;

    lot.marketPrice = targetMedian;
    if (targetMedian > 0 && lot.price > 0) {
      const diffPct = Math.round(((lot.price - targetMedian) / targetMedian) * 1000) / 10;
      lot.discount = diffPct;

      // Add badges/tags only for actual matching products (never for accessories or combo bait listings)
      if (!lot.isComboListing && !lot.isAccessory) {
        if (diffPct <= -20) {
          if (!lot.tags.includes('🔥 Супер-цена')) lot.tags.unshift(`🔥 Выгодно (${diffPct}%)`);
        } else if (diffPct <= -12) {
          if (!lot.tags.includes('🔥 Выгодно')) lot.tags.unshift(`🔥 Выгодно (${diffPct}%)`);
        }
      }
    } else {
      lot.discount = 0;
    }
  });

  return lots;
}

module.exports = {
  calculateCleanMedian,
  annotateLotsWithMarket,
  isAccessoryOrPart,
  parseQueryIntent,
  parseItemModel,
  isItemMatchingSearch
};
