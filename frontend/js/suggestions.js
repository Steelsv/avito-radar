/**
 * AvitoRadar — Smart Search Autocomplete & Vehicle Trims Catalog
 * Provides real-time instant autocomplete for vehicles, trims, configurations, and top electronics.
 */

(function () {
  'use strict';

  // Slang & transliteration normalizer
  const SLANG_MAP = {
    'бмв': 'bmw',
    'бумер': 'bmw',
    'мерс': 'mercedes',
    'мерседес': 'mercedes',
    'бенц': 'mercedes',
    'амг': 'amg',
    'ауди': 'audi',
    'тойота': 'toyota',
    'камри': 'toyota camry',
    'кэмри': 'toyota camry',
    'крузак': 'toyota land cruiser',
    'прадик': 'toyota land cruiser prado',
    'лада': 'lada',
    'ваз': 'lada',
    'таз': 'lada',
    'веста': 'lada vesta',
    'гранта': 'lada granta',
    'нива': 'lada niva',
    'ларгус': 'lada largus',
    'приора': 'lada priora',
    'фольксваген': 'volkswagen',
    'фольц': 'volkswagen',
    'ваг': 'volkswagen',
    'тигуан': 'volkswagen tiguan',
    'поло': 'volkswagen polo',
    'туарег': 'volkswagen touareg',
    'пассат': 'volkswagen passat',
    'гольф': 'volkswagen golf',
    'шкода': 'skoda',
    'октавия': 'skoda octavia',
    'кодиак': 'skoda kodiaq',
    'рапид': 'skoda rapid',
    'суперб': 'skoda superb',
    'карок': 'skoda karoq',
    'киа': 'kia',
    'кио': 'kia',
    'рио': 'kia rio',
    'спортейдж': 'kia sportage',
    'спортаж': 'kia sportage',
    'соренто': 'kia sorento',
    'сид': 'kia ceed',
    'хендай': 'hyundai',
    'хёндай': 'hyundai',
    'хюндай': 'hyundai',
    'хундай': 'hyundai',
    'солярис': 'hyundai solaris',
    'соляра': 'hyundai solaris',
    'санта фе': 'hyundai santa fe',
    'туссан': 'hyundai tucson',
    'туксон': 'hyundai tucson',
    'крета': 'hyundai creta',
    'джили': 'geely',
    'монджаро': 'geely monjaro',
    'манжаро': 'geely monjaro',
    'тугелла': 'geely tugella',
    'кулрей': 'geely coolray',
    'атлас': 'geely atlas',
    'хавал': 'haval',
    'хавейл': 'haval',
    'джолион': 'haval jolion',
    'дарго': 'haval dargo',
    'чери': 'chery',
    'тигго': 'chery tiggo',
    'арризо': 'chery arrizo',
    'танк': 'tank',
    'зикр': 'zeekr',
    'зикер': 'zeekr',
    'ли': 'lixiang',
    'лисян': 'lixiang',
    'мазда': 'mazda',
    'сх5': 'mazda cx-5',
    'ниссан': 'nissan',
    'кашкай': 'nissan qashqai',
    'икстрейл': 'nissan x-trail',
    'форд': 'ford',
    'фокус': 'ford focus',
    'мондео': 'ford mondeo',
    'куга': 'ford kuga',
    'рено': 'renault',
    'дастер': 'renault duster',
    'каптюр': 'renault kaptur',
    'логан': 'renault logan',
    'лексус': 'lexus',
    'порше': 'porsche',
    'порш': 'porsche',
    'кайен': 'porsche cayenne',
    'макан': 'porsche macan',
    'панамера': 'porsche panamera',
    'гелик': 'mercedes g 63 amg',
    'гелендваген': 'mercedes g-класс',
    'айфон': 'iphone',
    'ифон': 'iphone',
    'про макс': 'pro max',
    'макбук': 'macbook',
    'мак': 'macbook',
    'плойка': 'playstation',
    'пс5': 'playstation 5',
    'пс4': 'playstation 4',
    'сонька': 'playstation',
    'бокс': 'xbox',
    'хбокс': 'xbox',
    'стим дек': 'steam deck',
    'видюха': 'rtx',
    'видеокарта': 'rtx',
    'самсунг': 'samsung',
    'сяоми': 'xiaomi',
    'дайсон': 'dyson'
  };

  const CATALOG = [
    // --- АВТОМОБИЛИ: BMW ---
    {
      title: 'BMW 3 серии (G20) 320d xDrive M Sport',
      query: 'BMW 320d M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport',
      meta: '2.0d (190 л.с.) • Полный привод xDrive • M Sport Pro',
      minPrice: 2800000,
      keywords: ['бмв', 'bmw', '320', '320d', '3 серии', 'g20', 'm sport', 'м спорт', 'дизель', 'xdrive']
    },
    {
      title: 'BMW 3 серии (G20) 320i M Sport Pure',
      query: 'BMW 320i M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport',
      meta: '2.0 бензин (184 л.с.) • M-пакет • Кожа Vernasca',
      minPrice: 2700000,
      keywords: ['бмв', 'bmw', '320', '320i', '3 серии', 'g20', 'm sport', 'м спорт']
    },
    {
      title: 'BMW 3 серии (F30) 320i / 320d M Sport',
      query: 'BMW 320 F30 M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport',
      meta: 'Поколение F30 Рестайлинг • Спортивные сиденья, LED оптика',
      minPrice: 1500000,
      keywords: ['бмв', 'bmw', 'f30', 'ф30', '320', '320i', '320d', '3 серии']
    },
    {
      title: 'BMW 330i xDrive M Sport Pro (G20)',
      query: 'BMW 330i M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport Pro',
      meta: '2.0 бензин (258 л.с.) • Тормоза M Sport • Harman Kardon',
      minPrice: 3400000,
      keywords: ['бмв', 'bmw', '330', '330i', '3 серии', 'g20', 'm sport pro']
    },
    {
      title: 'BMW 5 серии (G30) 520d xDrive M Sport',
      query: 'BMW 520d M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport',
      meta: '2.0d (190 л.с.) • M-пакет • Панель Sensatec, Ambient light',
      minPrice: 3200000,
      keywords: ['бмв', 'bmw', '520', '520d', '5 серии', 'g30', 'г30', 'm sport', 'пятерка']
    },
    {
      title: 'BMW 5 серии (G30) 530d xDrive M Sport Pro',
      query: 'BMW 530d M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport Pro',
      meta: '3.0d 6 цилиндров (249 л.с.) • Лазерные фары, доводчики',
      minPrice: 4200000,
      keywords: ['бмв', 'bmw', '530', '530d', '5 серии', 'g30', 'm sport', 'дизель']
    },
    {
      title: 'BMW 5 серии (F10) 520d / 528i M Sport',
      query: 'BMW 5 F10 M Sport',
      category: 'auto',
      badge: '🚗 Авто • F10',
      meta: 'Бизнес-седан F10 • Рестайлинг • Кожаный салон, LED оптика',
      minPrice: 1600000,
      keywords: ['бмв', 'bmw', 'f10', 'ф10', '520', '528', '5 серии']
    },
    {
      title: 'BMW X5 (G05) xDrive30d M Sport Plus',
      query: 'BMW X5 G05 30d M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport Plus',
      meta: '3.0d (249 л.с.) • Пневмоподвеска • Колеса R21, Панорама',
      minPrice: 5500000,
      keywords: ['бмв', 'bmw', 'x5', 'х5', 'g05', 'г05', '30d', 'm sport']
    },
    {
      title: 'BMW X5 (F15) xDrive30d / 40d M Sport',
      query: 'BMW X5 F15 30d M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport',
      meta: '3.0d (249 л.с.) • Комфортные сиденья, панорамная крыша',
      minPrice: 2900000,
      keywords: ['бмв', 'bmw', 'x5', 'х5', 'f15', 'ф15', '30d', 'm sport']
    },
    {
      title: 'BMW X6 (G06) xDrive30d / 40i M Sport Pro',
      query: 'BMW X6 G06 M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport Pro',
      meta: 'Купе-кроссовер • Решетка Iconic Glow • Пневма, звук Harman',
      minPrice: 6500000,
      keywords: ['бмв', 'bmw', 'x6', 'х6', 'g06', '30d', '40i', 'm sport']
    },
    {
      title: 'BMW X3 (G01) xDrive20d / 30d M Sport',
      query: 'BMW X3 G01 M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport',
      meta: 'Премиум SUV • M Sport пакет, адаптивные фары, вентиляция',
      minPrice: 3500000,
      keywords: ['бмв', 'bmw', 'x3', 'х3', 'g01', 'm sport', '20d']
    },
    {
      title: 'BMW X7 (G07) xDrive30d / 40d M Sport',
      query: 'BMW X7 G07 M Sport',
      category: 'auto',
      badge: '🚗 Авто • M Sport',
      meta: 'Флагманский 7-местный внедорожник • Пневма, крыша Sky Lounge',
      minPrice: 8000000,
      keywords: ['бмв', 'bmw', 'x7', 'х7', 'g07', 'm sport', '30d']
    },

    // --- АВТОМОБИЛИ: LADA / ВАЗ ---
    {
      title: 'Lada Vesta SW Cross 1.6 / 1.8 Luxe Prestige',
      query: 'Lada Vesta SW Cross Luxe',
      category: 'auto',
      badge: '🚗 Авто • SW Cross Luxe',
      meta: 'Универсал • Клиренс 203 мм • Черный салон, климат, обогрев лба',
      minPrice: 850000,
      keywords: ['лада', 'lada', 'веста', 'vesta', 'sw cross', 'св кросс', 'кросс', 'luxe', 'люкс', 'ваз']
    },
    {
      title: 'Lada Vesta NG 1.6 Techno / Life',
      query: 'Lada Vesta NG Techno',
      category: 'auto',
      badge: '🚗 Авто • NG Techno',
      meta: 'Новое поколение NG • Вертикальный экран 10.4", цифровая приборка',
      minPrice: 1100000,
      keywords: ['лада', 'lada', 'веста', 'vesta', 'ng', 'нг', 'techno', 'техно', 'ваз']
    },
    {
      title: 'Lada Vesta 1.6 Comfort / Enjoy',
      query: 'Lada Vesta Comfort',
      category: 'auto',
      badge: '🚗 Авто • Comfort',
      meta: 'Седан • Кондиционер, парктроники, мультируль, подогрев',
      minPrice: 600000,
      keywords: ['лада', 'lada', 'веста', 'vesta', 'comfort', 'комфорт', 'седан']
    },
    {
      title: 'Lada Vesta Sport 1.8 (145 л.с.)',
      query: 'Lada Vesta Sport',
      category: 'auto',
      badge: '🚗 Авто • Sport',
      meta: 'Спортивные сиденья с алькантарой, заниженная подвеска, обвес',
      minPrice: 950000,
      keywords: ['лада', 'lada', 'веста', 'vesta', 'sport', 'спорт', '145']
    },
    {
      title: 'Lada Granta 1.6 Classic / Comfort',
      query: 'Lada Granta Comfort',
      category: 'auto',
      badge: '🚗 Авто • Comfort',
      meta: 'Седан / Лифтбек 1.6 8V/16V • Кондиционер, ЭУР, АБС',
      minPrice: 450000,
      keywords: ['лада', 'lada', 'гранта', 'granta', 'classic', 'comfort', 'лифтбек', 'седан']
    },
    {
      title: 'Lada Granta Drive Active 1.6',
      query: 'Lada Granta Drive Active',
      category: 'auto',
      badge: '🚗 Авто • Drive Active',
      meta: 'Спортивный обвес, красная отделка, подвеска с занижением',
      minPrice: 650000,
      keywords: ['лада', 'lada', 'гранта', 'granta', 'drive active', 'драйв актив']
    },
    {
      title: 'Lada Niva Legend 1.7 4x4 Urban / Luxe',
      query: 'Lada Niva Legend Urban',
      category: 'auto',
      badge: '🚗 Авто • 4x4 Urban',
      meta: 'Полный привод 4х4 • Понижайка, блокировка, кондиционер, литье',
      minPrice: 500000,
      keywords: ['лада', 'lada', 'нива', 'niva', 'legend', 'легенд', 'urban', 'урбан', '4х4', '4x4']
    },
    {
      title: 'Lada Niva Travel 1.7 Luxe / Off-road',
      query: 'Lada Niva Travel Luxe',
      category: 'auto',
      badge: '🚗 Авто • Travel Luxe',
      meta: 'Внедорожник • Шноркель, камера заднего вида, экран, обогрев лба',
      minPrice: 850000,
      keywords: ['лада', 'lada', 'нива', 'niva', 'travel', 'тревел', 'off-road', 'люкс']
    },
    {
      title: 'Lada Largus 1.6 Cross 7 мест Luxe',
      query: 'Lada Largus Cross 7 мест',
      category: 'auto',
      badge: '🚗 Авто • Cross 7 мест',
      meta: 'Семейный 7-местный универсал • Клиренс 170 мм, рейлинги',
      minPrice: 700000,
      keywords: ['лада', 'lada', 'ларгус', 'largus', 'cross', 'кросс', '7 мест', 'семь мест']
    },
    {
      title: 'Lada Priora 1.6 16V Люкс',
      query: 'Lada Priora Люкс',
      category: 'auto',
      badge: '🚗 Авто • Priora Люкс',
      meta: 'Хэтчбек/седан • Кондиционер Halla/Panasonic, датчик дождя',
      minPrice: 300000,
      keywords: ['лада', 'lada', 'приора', 'priora', 'люкс', '16v']
    },
    {
      title: 'ВАЗ 2114 Самара 1.6 инжектор',
      query: 'ВАЗ 2114 инжектор',
      category: 'auto',
      badge: '🚗 Авто • ВАЗ 2114',
      meta: 'Хэтчбек 8 клапанов • Евро-панель, бортовой компьютер',
      minPrice: 150000,
      keywords: ['ваз', '2114', 'четырка', 'четырнадцатая', 'самара', 'инжектор']
    },

    // --- АВТОМОБИЛИ: TOYOTA ---
    {
      title: 'Toyota Camry 2.5 (XV70) Elegance Safety',
      query: 'Toyota Camry 2.5 Elegance',
      category: 'auto',
      badge: '🚗 Авто • Elegance Safety',
      meta: '2.5 (181 л.с.) • Автомат • Комплекс систем безопасности Toyota Safety Sense',
      minPrice: 2200000,
      keywords: ['тойота', 'toyota', 'камри', 'camry', 'xv70', '70', 'elegance', 'элеганс', '2.5']
    },
    {
      title: 'Toyota Camry 3.5 (XV70) Люкс Safety / Executive',
      query: 'Toyota Camry 3.5 Люкс',
      category: 'auto',
      badge: '🚗 Авто • Люкс Safety 3.5',
      meta: '3.5 V6 (249 л.с.) • Аудиосистема JBL, вентиляция передних кресел',
      minPrice: 2800000,
      keywords: ['тойота', 'toyota', 'камри', 'camry', '3.5', 'люкс', 'executive', 'jbl', 'xv70']
    },
    {
      title: 'Toyota Camry GR Sport 2.5 / 3.5',
      query: 'Toyota Camry GR Sport',
      category: 'auto',
      badge: '🚗 Авто • GR Sport',
      meta: 'Спортивный стиль • Черная крыша, черные диски R18, красный декор',
      minPrice: 2600000,
      keywords: ['тойота', 'toyota', 'камри', 'camry', 'gr sport', 'гр спорт', 'xv70']
    },
    {
      title: 'Toyota Camry 2.5 (XV50) Престиж / Элеганс Плюс',
      query: 'Toyota Camry 50 Престиж',
      category: 'auto',
      badge: '🚗 Авто • XV50 Престиж',
      meta: 'Надежное поколение 50 • Ксенон, кожа, задний блок управления климатом',
      minPrice: 1500000,
      keywords: ['тойота', 'toyota', 'камри', 'camry', 'xv50', '50', 'полтинник', 'престиж']
    },
    {
      title: 'Toyota RAV4 2.0 / 2.5 (XA50) 4WD Comfort',
      query: 'Toyota RAV4 Comfort 4WD',
      category: 'auto',
      badge: '🚗 Авто • Comfort 4WD',
      meta: 'Полный привод Dynamic Torque Vectoring AWD • Зимний пакет, подогревы',
      minPrice: 2400000,
      keywords: ['тойота', 'toyota', 'рав4', 'рав 4', 'rav4', 'xa50', 'комфорт', 'comfort', '4wd']
    },
    {
      title: 'Toyota Land Cruiser 300 GR Sport / 70th Anniversary',
      query: 'Toyota Land Cruiser 300 GR Sport',
      category: 'auto',
      badge: '🚗 Авто • GR Sport',
      meta: '3.3D дизель (299 л.с.) / 3.5 бензин (415 л.с.) • E-KDSS, блокировки',
      minPrice: 8500000,
      keywords: ['тойота', 'toyota', 'лэнд крузер', 'ленд крузер', 'land cruiser', '300', 'крузак', 'крузер', 'gr sport']
    },
    {
      title: 'Toyota Land Cruiser 200 4.5D Executive Lounge',
      query: 'Toyota Land Cruiser 200 Executive Lounge',
      category: 'auto',
      badge: '🚗 Авто • Executive Lounge',
      meta: 'Дизель V8 битурбо • Гидропневматическая подвеска 4 Wheel AHC, кожа Nappa',
      minPrice: 4500000,
      keywords: ['тойота', 'toyota', 'лэнд крузер', 'land cruiser', '200', 'крузак', 'двухсотка', 'executive lounge']
    },
    {
      title: 'Toyota Land Cruiser Prado 150 2.8D Elegance Plus',
      query: 'Toyota Land Cruiser Prado 150 Elegance',
      category: 'auto',
      badge: '🚗 Авто • Prado Elegance',
      meta: 'Турбодизель (200 л.с.) • Рамный внедорожник, система стабилизации KDSS',
      minPrice: 3500000,
      keywords: ['тойота', 'toyota', 'прадо', 'prado', '150', 'прадик', 'land cruiser prado', 'elegance']
    },
    {
      title: 'Toyota Corolla 1.6 Comfort / Prestige',
      query: 'Toyota Corolla Comfort',
      category: 'auto',
      badge: '🚗 Авто • Comfort',
      meta: 'Экономичный седан • Вариатор, подогрев сидений и руля, диодная оптика',
      minPrice: 1200000,
      keywords: ['тойота', 'toyota', 'королла', 'corolla', 'комфорт', 'comfort']
    },

    // --- АВТОМОБИЛИ: MERCEDES-BENZ ---
    {
      title: 'Mercedes-Benz E 200 / E 220 d (W213) AMG Line',
      query: 'Mercedes E 200 AMG Line W213',
      category: 'auto',
      badge: '🚗 Авто • AMG Line',
      meta: 'Бизнес-класс • AMG пакет, панорама, Widescreen Cockpit, подсветка 64 цвета',
      minPrice: 2800000,
      keywords: ['мерседес', 'mercedes', 'е класс', 'e class', 'e 200', 'e 220', 'w213', 'amg line', 'амг']
    },
    {
      title: 'Mercedes-Benz C 180 / C 200 (W205) AMG Line',
      query: 'Mercedes C 180 AMG Line W205',
      category: 'auto',
      badge: '🚗 Авто • AMG Line',
      meta: 'Спортивный обвес AMG, комбинированный салон Artico/Dinamica, диски R18',
      minPrice: 1800000,
      keywords: ['мерседес', 'mercedes', 'ц класс', 'c class', 'c 180', 'c 200', 'w205', 'amg']
    },
    {
      title: 'Mercedes-Benz S 350 d / S 400 d 4MATIC (W222)',
      query: 'Mercedes S 350 d W222',
      category: 'auto',
      badge: '🚗 Авто • S-Класс W222',
      meta: 'Представительский седан • Пневмоподвеска Airmatic, звук Burmester, вентиляция',
      minPrice: 3500000,
      keywords: ['мерседес', 'mercedes', 's класс', 's class', 'w222', '222', 's 350', 's 400']
    },
    {
      title: 'Mercedes-Benz GLE 300 d / 400 d 4MATIC AMG Line',
      query: 'Mercedes GLE 300 d AMG Line',
      category: 'auto',
      badge: '🚗 Авто • GLE AMG Line',
      meta: 'Кроссовер V167 • Пневмоподвеска, AMG обвес, фары Multibeam LED',
      minPrice: 6000000,
      keywords: ['мерседес', 'mercedes', 'гле', 'gle', '300d', '400d', 'v167', 'amg line']
    },
    {
      title: 'Mercedes-Benz G 63 AMG 4.0 V8 (W463)',
      query: 'Mercedes G 63 AMG',
      category: 'auto',
      badge: '🚗 Авто • G 63 AMG',
      meta: 'Легендарный Гелендваген • V8 Biturbo (585 л.с.) • Спортивный выхлоп AMG',
      minPrice: 13000000,
      keywords: ['мерседес', 'mercedes', 'гелик', 'гелендваген', 'г класс', 'g class', 'g 63', 'amg', 'w463']
    },

    // --- АВТОМОБИЛИ: AUDI ---
    {
      title: 'Audi A4 (B9) 2.0 TFSI / TDI S Line quattro',
      query: 'Audi A4 B9 S Line quattro',
      category: 'auto',
      badge: '🚗 Авто • S Line quattro',
      meta: 'Полный привод quattro • Virtual Cockpit, спортивный обвес S Line, Matrix LED',
      minPrice: 2100000,
      keywords: ['ауди', 'audi', 'а4', 'a4', 'b9', 'б9', 's line', 'quattro', 'кватро']
    },
    {
      title: 'Audi A6 (C8) 45 TFSI / 40 TDI quattro S Line',
      query: 'Audi A6 C8 S Line',
      category: 'auto',
      badge: '🚗 Авто • S Line',
      meta: 'Бизнес-седан • Двойные сенсорные дисплеи MMI Touch, двойное остекление',
      minPrice: 3600000,
      keywords: ['ауди', 'audi', 'а6', 'a6', 'c8', 'с8', 's line', 'quattro']
    },
    {
      title: 'Audi Q5 (FY) 45 TFSI / 40 TDI quattro S Line',
      query: 'Audi Q5 S Line quattro',
      category: 'auto',
      badge: '🚗 Авто • Q5 S Line',
      meta: 'Кроссовер • Полный привод quattro, спортивные сиденья, панорамная крыша',
      minPrice: 2900000,
      keywords: ['ауди', 'audi', 'ку5', 'q5', 'fy', 's line', 'quattro']
    },
    {
      title: 'Audi Q7 (4M) 45 TDI (3.0d 249 л.с.) quattro S Line',
      query: 'Audi Q7 3.0 TDI S Line',
      category: 'auto',
      badge: '🚗 Авто • Q7 S Line',
      meta: 'Надежный 3.0 V6 TDI • Пневмоподвеска, звук Bose, подруливающая задняя ось',
      minPrice: 4200000,
      keywords: ['ауди', 'audi', 'ку7', 'q7', '4m', 's line', '3.0 tdi', 'дизель']
    },

    // --- АВТОМОБИЛИ: VOLKSWAGEN ---
    {
      title: 'Volkswagen Tiguan 2.0 TSI (180/220 л.с.) 4Motion R-Line',
      query: 'VW Tiguan 2.0 TSI R-Line',
      category: 'auto',
      badge: '🚗 Авто • R-Line 4Motion',
      meta: 'Спортивный обвес R-Line • Цифровая панель Active Info Display, панорама',
      minPrice: 2300000,
      keywords: ['фольксваген', 'volkswagen', 'vw', 'тигуан', 'tiguan', 'r-line', 'р лайн', '2.0 tsi', '4motion']
    },
    {
      title: 'Volkswagen Tiguan 2.0 TDI (150 л.с.) 4Motion Offroad',
      query: 'VW Tiguan 2.0 TDI Offroad',
      category: 'auto',
      badge: '🚗 Авто • TDI Offroad',
      meta: 'Экономичный дизель • Увеличенный угол въезда, предпусковой подогреватель',
      minPrice: 2100000,
      keywords: ['фольксваген', 'volkswagen', 'vw', 'тигуан', 'tiguan', 'дизель', 'tdi', 'offroad', 'оффроуд']
    },
    {
      title: 'Volkswagen Polo 1.6 / 1.4 TSI Status / Exclusive',
      query: 'VW Polo Exclusive',
      category: 'auto',
      badge: '🚗 Авто • Exclusive',
      meta: 'Лифтбек • Бесключевой доступ Kessy, светодиодная оптика проекционного типа',
      minPrice: 1100000,
      keywords: ['фольксваген', 'volkswagen', 'vw', 'поло', 'polo', 'status', 'exclusive', 'лифтбек']
    },
    {
      title: 'Volkswagen Touareg 3.0 TDI (249 л.с.) 4Motion R-Line',
      query: 'VW Touareg 3.0 TDI R-Line',
      category: 'auto',
      badge: '🚗 Авто • Touareg R-Line',
      meta: 'Цифровой кокпит Innovision 15" • Пневмоподвеска, матричные фары IQ.Light',
      minPrice: 4200000,
      keywords: ['фольксваген', 'volkswagen', 'vw', 'туарег', 'touareg', 'r-line', '3.0 tdi']
    },

    // --- АВТОМОБИЛИ: KIA & HYUNDAI ---
    {
      title: 'Kia K5 2.5 (194 л.с.) GT Line / GT Line+',
      query: 'Kia K5 2.5 GT Line',
      category: 'auto',
      badge: '🚗 Авто • GT Line+',
      meta: 'Спортивный седан • Красная кожа, панорамная крыша, камеры кругового обзора',
      minPrice: 2200000,
      keywords: ['киа', 'kia', 'к5', 'k5', 'gt line', 'гт лайн', '2.5']
    },
    {
      title: 'Kia Rio 1.6 Prestige / Premium',
      query: 'Kia Rio 1.6 Prestige',
      category: 'auto',
      badge: '🚗 Авто • Prestige',
      meta: 'Надежный городской седан • Подогрев лобового стекла, климат-контроль',
      minPrice: 1000000,
      keywords: ['киа', 'kia', 'рио', 'rio', 'prestige', 'premium', 'престиж']
    },
    {
      title: 'Kia Rio X (X-Line) 1.6 Premium',
      query: 'Kia Rio X-Line Premium',
      category: 'auto',
      badge: '🚗 Авто • X-Line Premium',
      meta: 'Кросс-хэтчбек • Клиренс 195 мм, пластиковый защитный обвес, кожаный салон',
      minPrice: 1150000,
      keywords: ['киа', 'kia', 'рио', 'rio', 'x-line', 'х лайн', 'икс лайн', 'кросс']
    },
    {
      title: 'Kia Sportage 2.0 / 2.5 4WD Drive / Prestige',
      query: 'Kia Sportage 4WD Prestige',
      category: 'auto',
      badge: '🚗 Авто • Prestige 4WD',
      meta: 'Кроссовер • Полный привод, подогрев руля и сидений, цифровая приборка',
      minPrice: 1900000,
      keywords: ['киа', 'kia', 'спортейдж', 'спортаж', 'sportage', '4wd', 'prestige']
    },
    {
      title: 'Hyundai Solaris 1.6 Elegance / Comfort',
      query: 'Hyundai Solaris Elegance',
      category: 'auto',
      badge: '🚗 Авто • Elegance',
      meta: 'Седан • Климат-контроль, линзованная оптика с поворотным светом, парктроники',
      minPrice: 950000,
      keywords: ['хендай', 'хёндай', 'hyundai', 'солярис', 'solaris', 'elegance', 'comfort', 'элеганс']
    },
    {
      title: 'Hyundai Tucson 2.0 / 2.5 4WD Lifestyle / Family',
      query: 'Hyundai Tucson 4WD Lifestyle',
      category: 'auto',
      badge: '🚗 Авто • Lifestyle 4WD',
      meta: 'Полный привод HTRAC • Электронный селектор АКПП, бесключевой доступ',
      minPrice: 2200000,
      keywords: ['хендай', 'hyundai', 'туссан', 'туксон', 'tucson', 'htrac', '4wd']
    },
    {
      title: 'Hyundai Santa Fe 2.2 CRDi 4WD High-Tech',
      query: 'Hyundai Santa Fe 2.2 High-Tech',
      category: 'auto',
      badge: '🚗 Авто • High-Tech',
      meta: 'Турбодизель (200 л.с.) • Премиум акустика Krell, панорамная крыша, проекция',
      minPrice: 2900000,
      keywords: ['хендай', 'hyundai', 'санта фе', 'santa fe', '2.2 crdi', 'дизель', 'high-tech']
    },

    // --- АВТОМОБИЛИ: SKODA ---
    {
      title: 'Skoda Octavia (A8) 1.4 TSI / 2.0 TSI Style Plus',
      query: 'Skoda Octavia A8 Style',
      category: 'auto',
      badge: '🚗 Авто • Style Plus',
      meta: 'Лифтбек • Матричные фары Matrix LED, цифровая приборка, звук Canton',
      minPrice: 2200000,
      keywords: ['шкода', 'skoda', 'октавия', 'octavia', 'a8', 'а8', 'style', 'стайл', '1.4 tsi']
    },
    {
      title: 'Skoda Octavia (A7) 1.4 / 1.8 TSI Ambition / Style',
      query: 'Skoda Octavia A7 Style',
      category: 'auto',
      badge: '🚗 Авто • A7 Style',
      meta: 'Рестайлинг • Раздельные фары, климат Climatronic, огромный багажник',
      minPrice: 1300000,
      keywords: ['шкода', 'skoda', 'октавия', 'octavia', 'a7', 'а7', '1.4 tsi', '1.8 tsi']
    },
    {
      title: 'Skoda Kodiaq 2.0 TDI / 2.0 TSI 4x4 Hockey Edition',
      query: 'Skoda Kodiaq Hockey Edition',
      category: 'auto',
      badge: '🚗 Авто • Hockey Edition',
      meta: 'Семейный 7-местный кроссовер • Полный привод 4х4, зимний пакет, багажник с электроприводом',
      minPrice: 2600000,
      keywords: ['шкода', 'skoda', 'кодиак', 'kodiaq', 'hockey edition', 'хоккей', '4x4', '2.0 tdi']
    },
    {
      title: 'Skoda Rapid 1.6 / 1.4 TSI Monte Carlo / Ambition',
      query: 'Skoda Rapid Monte Carlo',
      category: 'auto',
      badge: '🚗 Авто • Monte Carlo',
      meta: 'Спортивная спецверсия Monte Carlo • Черные зеркала, спойлер, спорт-руль',
      minPrice: 1100000,
      keywords: ['шкода', 'skoda', 'рапид', 'rapid', 'monte carlo', 'монте карло', '1.4 tsi']
    },

    // --- АВТОМОБИЛИ: GEELY, HAVAL, CHERY, TANK, ZEEKR ---
    {
      title: 'Geely Monjaro 2.0 4WD Exclusive / Flagship',
      query: 'Geely Monjaro Flagship',
      category: 'auto',
      badge: '🚗 Авто • Flagship 4WD',
      meta: 'Платформа Volvo CMA 238 л.с. • 3 экрана на торпедо, отделка замшей, автомат Aisin 8ст',
      minPrice: 3200000,
      keywords: ['джили', 'geely', 'монджаро', 'манжаро', 'monjaro', 'flagship', 'exclusive', '4wd']
    },
    {
      title: 'Geely Tugella 2.0 4WD Flagship Sport',
      query: 'Geely Tugella Flagship Sport',
      category: 'auto',
      badge: '🚗 Авто • Flagship Sport',
      meta: 'Купе-кроссовер 238 л.с. • Черные диски R20, комбинированный салон, панорама',
      minPrice: 2600000,
      keywords: ['джили', 'geely', 'тугелла', 'tugella', 'flagship sport', 'купе кроссовер']
    },
    {
      title: 'Geely Coolray 1.5 Flagship / Flagship Sport',
      query: 'Geely Coolray Flagship Sport',
      category: 'auto',
      badge: '🚗 Авто • Flagship Sport',
      meta: 'Городской кроссовер • Спортивный спойлер, красные суппорты, панорамная крыша',
      minPrice: 1700000,
      keywords: ['джили', 'geely', 'кулрей', 'coolray', 'flagship sport', 'флагшип']
    },
    {
      title: 'Haval Jolion 1.5 4WD Premium / Tech Plus',
      query: 'Haval Jolion 4WD Premium',
      category: 'auto',
      badge: '🚗 Авто • Premium 4WD',
      meta: 'Полный привод • Адаптивный круиз, автопарковщик, вентиляция сиденья водителя',
      minPrice: 1700000,
      keywords: ['хавал', 'хавейл', 'haval', 'джолион', 'jolion', 'premium', 'премиум', '4wd']
    },
    {
      title: 'Haval Dargo 2.0 4WD Tech Plus / Premium',
      query: 'Haval Dargo Tech Plus',
      category: 'auto',
      badge: '🚗 Авто • Tech Plus 4WD',
      meta: 'Внедорожный кроссовер • Блокировка заднего дифференциала, прозрачный капот',
      minPrice: 2500000,
      keywords: ['хавал', 'haval', 'дарго', 'dargo', 'tech plus', '4wd', 'блокировка']
    },
    {
      title: 'Tank 300 2.0 4WD City / Premium',
      query: 'Tank 300 Premium',
      category: 'auto',
      badge: '🚗 Авто • Tank 300 Premium',
      meta: 'Настоящий рамный внедорожник • Понижающая передача, блокировки перед/зад, люк',
      minPrice: 3200000,
      keywords: ['танк', 'tank', '300', 'триста', 'premium', 'премиум', 'рамный']
    },
    {
      title: 'Tank 500 3.0 V6 4WD Premium',
      query: 'Tank 500 Premium',
      category: 'auto',
      badge: '🚗 Авто • Tank 500 Premium',
      meta: 'Люкс внедорожник • V6 Twin-Turbo (299 л.с.), электроподножки, доводчики дверей',
      minPrice: 5100000,
      keywords: ['танк', 'tank', '500', 'пятьсот', 'premium', 'v6', 'твин турбо']
    },
    {
      title: 'Chery Tiggo 7 Pro Max 1.6 AWD Ultimate',
      query: 'Chery Tiggo 7 Pro Max Ultimate',
      category: 'auto',
      badge: '🚗 Авто • Ultimate AWD',
      meta: 'Полный привод • Сдвоенные экраны 24.6", коричневый салон, панорама',
      minPrice: 2100000,
      keywords: ['чери', 'chery', 'тигго', 'tiggo', '7 pro max', '7 про макс', 'ultimate', 'awd']
    },
    {
      title: 'Zeekr 001 YOU / ME 4WD (544 л.с.)',
      query: 'Zeekr 001 YOU',
      category: 'auto',
      badge: '⚡ Электро • Zeekr 001',
      meta: 'Электролифтбек • Пневмоподвеска, батарея 100 кВт·ч, акустика Yamaha, двери с электроприводом',
      minPrice: 4700000,
      keywords: ['зикр', 'зикер', 'zeekr', '001', 'you', 'me', 'электрокар']
    },
    {
      title: 'Lixiang L7 / L9 Max Ultra',
      query: 'Lixiang L7 Max',
      category: 'auto',
      badge: '🔋 Гибрид • Lixiang L7/L9',
      meta: 'Последовательный гибрид • Пневмоподвеска, монитор для задних пассажиров, массаж сидений',
      minPrice: 5200000,
      keywords: ['ли', 'лисян', 'lixiang', 'li auto', 'l7', 'л7', 'l9', 'л9', 'max', 'ultra']
    },

    // --- ЭЛЕКТРОНИКА: IPHONE & APPLE ---
    {
      title: 'iPhone 15 Pro Max 256GB / 512GB',
      query: 'iPhone 15 Pro Max 256GB',
      category: 'tech',
      badge: '📱 Apple • Флагман',
      meta: 'Титановый корпус • Чип Apple A17 Pro • Перископическая камера 5x',
      minPrice: 85000,
      keywords: ['айфон', 'iphone', '15 pro max', '15 про макс', '256gb', 'титан', 'apple']
    },
    {
      title: 'iPhone 15 Pro 128GB / 256GB',
      query: 'iPhone 15 Pro 128GB',
      category: 'tech',
      badge: '📱 Apple • Pro',
      meta: 'Экран 120 Гц ProMotion • Кнопка Action Button • USB-C 3.0',
      minPrice: 75000,
      keywords: ['айфон', 'iphone', '15 pro', '15 про', '128gb', '256gb', 'apple']
    },
    {
      title: 'iPhone 15 128GB',
      query: 'iPhone 15 128GB',
      category: 'tech',
      badge: '📱 Apple • Базовый',
      meta: 'Dynamic Island • Камера 48 Мп • Разъем USB-C • Матовое стекло',
      minPrice: 55000,
      keywords: ['айфон', 'iphone', '15', '128gb', 'dynamic island', 'apple']
    },
    {
      title: 'iPhone 14 Pro Max 128GB / 256GB',
      query: 'iPhone 14 Pro Max',
      category: 'tech',
      badge: '📱 Apple • Pro Max',
      meta: 'Dynamic Island • Always-On Display • Чип A16 Bionic',
      minPrice: 65000,
      keywords: ['айфон', 'iphone', '14 pro max', '14 про макс', 'apple']
    },
    {
      title: 'iPhone 13 128GB',
      query: 'iPhone 13 128GB',
      category: 'tech',
      badge: '📱 Apple • Хит продаж',
      meta: 'Чип A15 Bionic • Кинематографический режим видео • Дисплей Super Retina XDR',
      minPrice: 38000,
      keywords: ['айфон', 'iphone', '13', '128gb', 'apple']
    },
    {
      title: 'MacBook Air 13 M2 8/256GB',
      query: 'MacBook Air 13 M2',
      category: 'tech',
      badge: '💻 Ноутбук • MacBook',
      meta: 'Тонкий легкий корпус • Чип Apple M2 • Зарядка MagSafe 3',
      minPrice: 70000,
      keywords: ['макбук', 'macbook', 'air', 'm2', 'м2', 'ноутбук', 'apple']
    },
    {
      title: 'MacBook Pro 14 M3 Pro 18/512GB',
      query: 'MacBook Pro 14 M3 Pro',
      category: 'tech',
      badge: '💻 Ноутбук • MacBook Pro',
      meta: 'Экран Liquid Retina XDR 120 Гц • Цвет Space Black • Чип M3 Pro',
      minPrice: 150000,
      keywords: ['макбук', 'macbook', 'pro', 'm3 pro', 'м3 про', 'apple']
    },

    // --- ЭЛЕКТРОНИКА: КОНСОЛИ ---
    {
      title: 'PlayStation 5 Slim с дисководом 1TB',
      query: 'PlayStation 5 Slim 1TB',
      category: 'tech',
      badge: '🎮 Консоль • PS5 Slim',
      meta: 'Новая ревизия Slim • 1TB SSD • Геймпад DualSense, поддержка 4K 120Hz',
      minPrice: 42000,
      keywords: ['сони', 'плейстейшн', 'playstation', 'ps5', 'пс5', 'slim', 'слим', 'консоль']
    },
    {
      title: 'PlayStation 5 Digital Edition (CFI-1200 / Slim)',
      query: 'PlayStation 5 Digital Edition',
      category: 'tech',
      badge: '🎮 Консоль • PS5 Digital',
      meta: 'Версия без дисковода • Быстрый SSD, поддержка трассировки лучей',
      minPrice: 35000,
      keywords: ['сони', 'playstation', 'ps5', 'пс5', 'digital edition', 'диджитал']
    },
    {
      title: 'PlayStation 5 Pro 2TB',
      query: 'PlayStation 5 Pro',
      category: 'tech',
      badge: '🎮 Консоль • PS5 Pro',
      meta: 'Флагманская консоль • Улучшенная графика PSSR 4K 60fps, 2TB SSD',
      minPrice: 75000,
      keywords: ['сони', 'playstation', 'ps5 pro', 'пс5 про', 'про']
    },
    {
      title: 'Steam Deck OLED 512GB / 1TB',
      query: 'Steam Deck OLED 512GB',
      category: 'tech',
      badge: '🎮 Портатив • Steam Deck',
      meta: 'Экран 90Hz HDR OLED • Увеличенная батарея 50 Вт·ч • Тихий вентилятор',
      minPrice: 48000,
      keywords: ['стим дек', 'steam deck', 'oled', 'олед', '512gb', 'valve']
    },
    {
      title: 'Xbox Series X 1TB',
      query: 'Xbox Series X 1TB',
      category: 'tech',
      badge: '🎮 Консоль • Xbox Series X',
      meta: '12 терафлопс мощности • Функция Quick Resume • Привод 4K Blu-ray',
      minPrice: 38000,
      keywords: ['бокс', 'хбокс', 'xbox', 'series x', 'сериес х', 'microsoft']
    },

    // --- ЭЛЕКТРОНИКА: ВИДЕОКАРТЫ (GPU) ---
    {
      title: 'NVIDIA GeForce RTX 4070 Super 12GB',
      query: 'RTX 4070 Super 12GB',
      category: 'tech',
      badge: '⚡ GPU • RTX 4070 Super',
      meta: '7168 CUDA ядер • Память GDDR6X 12GB • Поддержка DLSS 3.5 Frame Gen',
      minPrice: 55000,
      keywords: ['видеокарта', 'видюха', 'rtx', 'ртх', '4070 super', '4070 супер', 'nvidia']
    },
    {
      title: 'NVIDIA GeForce RTX 4070 Ti Super 16GB',
      query: 'RTX 4070 Ti Super 16GB',
      category: 'tech',
      badge: '⚡ GPU • RTX 4070 Ti Super',
      meta: 'Чип AD103 • 16GB памяти с 256-битной шиной • Идеально для 4K гейминга',
      minPrice: 75000,
      keywords: ['видеокарта', 'rtx', '4070 ti super', 'ти супер', '16gb', 'nvidia']
    },
    {
      title: 'NVIDIA GeForce RTX 4080 Super 16GB',
      query: 'RTX 4080 Super 16GB',
      category: 'tech',
      badge: '⚡ GPU • RTX 4080 Super',
      meta: '10240 CUDA ядер • Ультимативная производительность для 4K и нейросетей',
      minPrice: 90000,
      keywords: ['видеокарта', 'rtx', '4080 super', '4080 супер', 'nvidia']
    },
    {
      title: 'NVIDIA GeForce RTX 4090 24GB',
      query: 'RTX 4090 24GB',
      category: 'tech',
      badge: '⚡ GPU • Флагман RTX 4090',
      meta: '24GB GDDR6X • Мощнейший графический процессор в мире для игр и AI',
      minPrice: 150000,
      keywords: ['видеокарта', 'rtx', '4090', '24gb', 'топ', 'nvidia']
    },
    {
      title: 'NVIDIA GeForce RTX 4060 Ti 8GB / 16GB',
      query: 'RTX 4060 Ti',
      category: 'tech',
      badge: '⚡ GPU • RTX 4060 Ti',
      meta: 'Энергоэффективная карта для 1080p / 1440p на ультра настройках с DLSS 3',
      minPrice: 34000,
      keywords: ['видеокарта', 'rtx', '4060 ti', 'тиай', 'nvidia']
    },
    {
      title: 'AMD Radeon RX 6700 XT 12GB',
      query: 'RX 6700 XT 12GB',
      category: 'tech',
      badge: '⚡ GPU • RX 6700 XT',
      meta: '12GB GDDR6 • Быстрее RTX 3060 на 30% • Отличный выбор для 2K',
      minPrice: 25000,
      keywords: ['видеокарта', 'amd', 'rx', '6700 xt', '6700xt', 'радион', 'radeon']
    },
    {
      title: 'AMD Radeon RX 7800 XT 16GB',
      query: 'RX 7800 XT 16GB',
      category: 'tech',
      badge: '⚡ GPU • RX 7800 XT',
      meta: '16GB памяти • Прямой конкурент RTX 4070 по выгодной цене',
      minPrice: 45000,
      keywords: ['видеокарта', 'amd', 'rx', '7800 xt', '16gb', 'radeon']
    },

    // --- ЭЛЕКТРОНИКА: SAMSUNG & DYSON ---
    {
      title: 'Samsung Galaxy S24 Ultra 256GB / 512GB',
      query: 'Samsung Galaxy S24 Ultra',
      category: 'tech',
      badge: '📱 Samsung • Ultra',
      meta: 'Титановая рамка • Стилус S Pen • Камера 200 Мп • Функции Galaxy AI',
      minPrice: 75000,
      keywords: ['самсунг', 'samsung', 'galaxy', 's24 ultra', 'с24 ультра', 'айфон']
    },
    {
      title: 'Стайлер Dyson Airwrap Complete Long',
      query: 'Dyson Airwrap Complete Long',
      category: 'tech',
      badge: '💨 Dyson • Стайлер',
      meta: 'Эффект Коанда • Цилиндрические насадки для завивки, чехол для хранения',
      minPrice: 35000,
      keywords: ['дайсон', 'dyson', 'airwrap', 'эйрврап', 'стайлер', 'complete long']
    },
    {
      title: 'Фен Dyson Supersonic HD07 / HD08',
      query: 'Dyson Supersonic',
      category: 'tech',
      badge: '💨 Dyson • Фен',
      meta: 'Интеллектуальный контроль температуры • Магнитные насадки, бережная сушка',
      minPrice: 25000,
      keywords: ['дайсон', 'dyson', 'supersonic', 'суперсоник', 'фен']
    }
  ];

  function normalize(str) {
    if (!str) return '';
    return str.toLowerCase().replace(/[^a-z0-9а-яё]/gi, ' ').replace(/\s+/g, ' ').trim();
  }

  function searchSuggestions(inputQuery, limit = 8) {
    if (!inputQuery) return [];
    let raw = inputQuery.toLowerCase().trim();
    if (raw.length < 2) return [];

    // Check if input matches or starts with any slang term
    const slangTerm = SLANG_MAP[raw];
    let queryVariants = [raw];
    if (slangTerm) {
      queryVariants.push(slangTerm);
    }
    // Also check word-by-word slang translation
    const words = raw.split(/\s+/);
    const translatedWords = words.map(w => SLANG_MAP[w] || w);
    const translatedJoined = translatedWords.join(' ');
    if (translatedJoined !== raw) {
      queryVariants.push(translatedJoined);
    }

    const scored = [];

    for (const item of CATALOG) {
      const titleNorm = normalize(item.title);
      const queryNorm = normalize(item.query);
      const metaNorm = normalize(item.meta);
      const kwNorms = item.keywords.map(normalize);

      let bestScore = 0;

      for (const q of queryVariants) {
        const qNorm = normalize(q);
        if (!qNorm) continue;

        // Exact query match
        if (queryNorm === qNorm || titleNorm === qNorm) {
          bestScore = Math.max(bestScore, 100);
          continue;
        }

        // Starts with query
        if (queryNorm.startsWith(qNorm) || titleNorm.startsWith(qNorm)) {
          bestScore = Math.max(bestScore, 85);
          continue;
        }

        // Substring in query or title
        if (queryNorm.includes(qNorm) || titleNorm.includes(qNorm)) {
          bestScore = Math.max(bestScore, 70);
          continue;
        }

        // Match in keywords
        for (const kw of kwNorms) {
          if (kw === qNorm) {
            bestScore = Math.max(bestScore, 65);
          } else if (kw.startsWith(qNorm)) {
            bestScore = Math.max(bestScore, 55);
          } else if (kw.includes(qNorm) || qNorm.includes(kw)) {
            bestScore = Math.max(bestScore, 40);
          }
        }

        // Match in meta
        if (metaNorm.includes(qNorm)) {
          bestScore = Math.max(bestScore, 30);
        }
      }

      if (bestScore > 0) {
        scored.push({ item, score: bestScore });
      }
    }

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, limit).map(s => s.item);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function highlightMatches(text, query) {
    if (!text || !query) return escapeHtml(text);
    const escapedText = escapeHtml(text);
    const words = query.trim().split(/\s+/).filter(w => w.length >= 2);
    if (words.length === 0) return escapedText;

    const pattern = new RegExp(`(${words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
    return escapedText.replace(pattern, '<mark>$1</mark>');
  }

  function initAutocomplete(inputEl, dropdownEl, options = {}) {
    if (!inputEl || !dropdownEl) return;

    let activeIndex = -1;
    let currentSuggestions = [];

    function renderSuggestions(items, query) {
      currentSuggestions = items;
      activeIndex = -1;

      if (!items || items.length === 0) {
        dropdownEl.innerHTML = '';
        dropdownEl.classList.add('hidden');
        return;
      }

      const html = items.map((item, idx) => {
        const badgeClass = item.category === 'auto' ? 'auto' : 'tech';
        const highlightedTitle = highlightMatches(item.title, query);
        return `
          <div class="suggestion-item" data-index="${idx}" role="button" tabindex="0">
            <div class="suggestion-left">
              <div class="suggestion-title">${highlightedTitle}</div>
              <div class="suggestion-meta">${escapeHtml(item.meta)}</div>
            </div>
            <span class="suggestion-badge ${badgeClass}">${escapeHtml(item.badge)}</span>
          </div>
        `;
      }).join('');

      dropdownEl.innerHTML = html;
      dropdownEl.classList.remove('hidden');

      dropdownEl.querySelectorAll('.suggestion-item').forEach(el => {
        el.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          const idx = Number(el.dataset.index);
          selectItem(items[idx]);
        });
      });
    }

    function selectItem(item) {
      if (!item) return;
      inputEl.value = item.query;
      closeDropdown();

      if (typeof window !== 'undefined' && window.TelegramService) {
        window.TelegramService.haptic('light');
      }

      if (typeof options.onSelect === 'function') {
        options.onSelect(item);
      }
    }

    function closeDropdown() {
      dropdownEl.classList.add('hidden');
      dropdownEl.innerHTML = '';
      currentSuggestions = [];
      activeIndex = -1;
    }

    inputEl.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      if (q.length < 2) {
        closeDropdown();
        return;
      }

      const matches = searchSuggestions(q, options.limit || 7);
      renderSuggestions(matches, q);
    });

    inputEl.addEventListener('focus', () => {
      const q = inputEl.value.trim();
      if (q.length >= 2) {
        const matches = searchSuggestions(q, options.limit || 7);
        renderSuggestions(matches, q);
      }
    });

    inputEl.addEventListener('keydown', (e) => {
      if (dropdownEl.classList.contains('hidden') || currentSuggestions.length === 0) {
        return;
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIndex = (activeIndex + 1) % currentSuggestions.length;
        updateActiveItem();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = (activeIndex - 1 + currentSuggestions.length) % currentSuggestions.length;
        updateActiveItem();
      } else if (e.key === 'Enter') {
        if (activeIndex >= 0 && activeIndex < currentSuggestions.length) {
          e.preventDefault();
          selectItem(currentSuggestions[activeIndex]);
        }
      } else if (e.key === 'Escape') {
        closeDropdown();
      }
    });

    function updateActiveItem() {
      const items = dropdownEl.querySelectorAll('.suggestion-item');
      items.forEach((el, idx) => {
        if (idx === activeIndex) {
          el.classList.add('active');
          el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else {
          el.classList.remove('active');
        }
      });
    }

    // Close on click outside
    document.addEventListener('click', (e) => {
      if (!inputEl.contains(e.target) && !dropdownEl.contains(e.target)) {
        closeDropdown();
      }
    });
  }

  // Export globally
  window.Suggestions = {
    search: searchSuggestions,
    init: initAutocomplete,
    catalog: CATALOG,
    slangMap: SLANG_MAP
  };

})();
