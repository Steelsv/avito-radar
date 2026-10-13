const ruToEnMap = {
  'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
  'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
  'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
  'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
  'я': 'ya'
};

function transliterate(str) {
  if (!str) return '';
  return str.toLowerCase().split('').map(c => ruToEnMap[c] || c).join('');
}

function slugify(text) {
  if (!text) return '';
  const trans = transliterate(text);
  return trans
    .replace(/[^a-z0-9_-]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function formatPrice(num) {
  if (!num || isNaN(num)) return 'Цена не указана';
  return `${Number(num).toLocaleString('ru-RU')} ₽`;
}

module.exports = {
  transliterate,
  slugify,
  formatPrice
};
