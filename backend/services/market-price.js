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

function annotateLotsWithMarket(lots, searchQuery = '') {
  if (!lots || lots.length === 0) return lots;

  // Detect and tag accessories
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
  });

  // Filter out accessories, defective or combo listings from baseline median
  const validPrices = lots
    .filter(l => !l.isAccessory && !l.isComboListing && !(Array.isArray(l.tags) && l.tags.some(t => t.includes('Дефект') || t.includes('Запчасти') || t.includes('Сборное') || t.includes('Аксессуар'))))
    .map(l => l.price)
    .filter(p => p > 0);

  const median = calculateCleanMedian(validPrices);

  lots.forEach(lot => {
    lot.marketPrice = median;
    if (median > 0 && lot.price > 0) {
      const diffPct = Math.round(((lot.price - median) / median) * 1000) / 10;
      lot.discount = diffPct;

      // Add badges/tags only for actual products (never for accessories or combo bait listings)
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
  isAccessoryOrPart
};
