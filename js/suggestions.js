/**
 * AvitoRadar — Smart Search Autocomplete & Vehicle Trims Catalog
 * Provides real-time instant autocomplete for vehicles, trims, configurations, and top electronics.
 */

(function () {
  'use strict';

  // Slang, hardware abbreviations & transliteration normalizer
  const SLANG_MAP = {
    // RAM / DDR
    'ддр5': 'ddr5',
    'ддр 5': 'ddr5',
    'ддр4': 'ddr4',
    'ддр 4': 'ddr4',
    'ддр': 'ddr5',
    'ddr': 'ddr5',
    'оперативка': 'ddr5 32gb',
    'озу': 'ddr5 32gb',
    'память': 'ddr5',
    // GPUs
    'видяха': 'rtx',
    'видюха': 'rtx',
    'видеокарта': 'rtx',
    'ртх': 'rtx',
    'радион': 'radeon rx',
    'радики': 'radeon rx',
    // CPUs & Boards
    'проц': 'ryzen',
    'процессор': 'ryzen',
    'райзен': 'ryzen',
    'интел': 'core i5',
    'мать': 'материнская плата b650',
    'материнка': 'материнская плата',
    'мамка': 'материнская плата',
    'ссд': 'ssd m.2 nvme',
    'бп': 'блок питания',
    'водянка': 'водяное охлаждение 360',
    'кулер': 'кулер для процессора',
    // Consoles & Gaming
    'плойка': 'playstation 5',
    'сонька': 'playstation 5',
    'пс5': 'playstation 5',
    'пс4': 'playstation 4',
    'бокс': 'xbox series x',
    'хбокс': 'xbox series x',
    'сыч': 'nintendo switch oled',
    'свич': 'nintendo switch',
    'стим дек': 'steam deck oled',
    'стимдек': 'steam deck oled',
    'дэк': 'steam deck oled',
    // Apple & Phones
    'айфон': 'iphone',
    'ифон': 'iphone',
    'эппл': 'apple',
    'яблоко': 'apple',
    'про макс': 'pro max',
    'макбук': 'macbook air',
    'мак': 'macbook',
    'эир': 'macbook air',
    'ноут': 'ноутбук',
    'уши': 'airpods pro',
    'подсы': 'airpods pro',
    'наушники': 'airpods pro',
    'часы': 'apple watch',
    'вотчи': 'apple watch',
    'самсунг': 'samsung galaxy',
    'сяоми': 'xiaomi',
    'редми': 'redmi',
    'пиксель': 'google pixel',
    // Appliances & Tools
    'пылесос': 'dyson',
    'дайсон': 'dyson',
    'стайлер': 'dyson airwrap',
    'фен': 'dyson supersonic',
    'робот': 'робот пылесос roborock',
    'кофемашина': 'кофемашина delonghi',
    'перфоратор': 'перфоратор makita',
    // Wheels & Tires
    'колеса': 'колеса r17 r18',
    'диски': 'литые диски r17 r18',
    'резина': 'зимняя резина r16 r17',
    'шины': 'летние шины r16 r17',
    // Cars
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
    'дэу': 'daewoo',
    'дэо': 'daewoo',
    'деу': 'daewoo',
    'деву': 'daewoo',
    'матиз': 'daewoo matiz',
    'матизик': 'daewoo matiz',
    'нексия': 'daewoo nexia',
    'некси': 'daewoo nexia',
    'джентра': 'daewoo gentra',
    'ланос': 'chevrolet lanos',
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
    'гелендваген': 'mercedes g-класс'
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

    // --- АВТОМОБИЛИ: DAEWOO MATIZ & БЮДЖЕТНЫЕ МОДЕЛИ ---
    {
      title: 'Daewoo Matiz 0.8 МКПП (механика)',
      query: 'Daewoo Matiz 0.8 МКПП',
      category: 'auto',
      badge: '🚗 Авто • Matiz 0.8',
      meta: '0.8 л (52 л.с.) МКПП • Экономичный расход 5.5л/100км, надежная механика, дешевое обслуживание',
      minPrice: 80000,
      keywords: ['дэу', 'daewoo', 'матиз', 'matiz', '0.8', 'мкпп', 'механика', 'хэтчбек']
    },
    {
      title: 'Daewoo Matiz 0.8 АКПП (автомат)',
      query: 'Daewoo Matiz автомат АКПП',
      category: 'auto',
      badge: '🚗 Авто • Matiz АКПП',
      meta: 'Редкая комфортная версия с надежным японским 4-ступенчатым автоматом Jatco',
      minPrice: 140000,
      keywords: ['дэу', 'daewoo', 'матиз', 'matiz', '0.8', 'акпп', 'автомат', 'jatco']
    },
    {
      title: 'Daewoo Matiz 1.0 Best (4 цилиндра)',
      query: 'Daewoo Matiz 1.0 Best',
      category: 'auto',
      badge: '🚗 Авто • Matiz Best 1.0',
      meta: '1.0 л (64 л.с.) 4 цилиндра • Топовая резвая версия Best, ГУР, кондиционер, 4 электростеклоподъемника',
      minPrice: 130000,
      keywords: ['дэу', 'daewoo', 'матиз', 'matiz', '1.0', 'best', 'бест', '4 цилиндра', 'гур']
    },
    {
      title: 'Daewoo Matiz с кондиционером и ГУР',
      query: 'Daewoo Matiz с кондиционером',
      category: 'auto',
      badge: '🚗 Авто • Matiz с кондиционером',
      meta: 'Комплектация MX / Best • Кондиционер, гидроусилитель руля (ГУР), центральный замок',
      minPrice: 110000,
      keywords: ['дэу', 'daewoo', 'матиз', 'matiz', 'кондиционер', 'гур', 'mx', 'best']
    },
    {
      title: 'Daewoo Matiz Рестайлинг (2008–2015)',
      query: 'Daewoo Matiz Рестайлинг',
      category: 'auto',
      badge: '🚗 Авто • Matiz Рестайлинг',
      meta: 'Поздние годы выпуска кузов M150 • Обновленная оптика и салон, евро-3/4, честный пробег',
      minPrice: 120000,
      keywords: ['дэу', 'daewoo', 'матиз', 'matiz', 'рестайлинг', 'm150', '2008', '2010', '2012', '2014']
    },
    {
      title: 'Daewoo Matiz до 150 000 ₽ на полном ходу',
      query: 'Daewoo Matiz до 150000',
      category: 'auto',
      badge: '🚗 Авто • Matiz бюджет',
      meta: 'Бюджетный рабочий автомобиль на каждый день • Сел и поехал, без критичной коррозии',
      minPrice: 80000,
      keywords: ['дэу', 'daewoo', 'матиз', 'matiz', 'до 150000', 'на ходу', 'бюджет']
    },
    {
      title: 'Daewoo Nexia 1.6 16v (109 л.с.)',
      query: 'Daewoo Nexia 1.6',
      category: 'auto',
      badge: '🚗 Авто • Nexia 1.6 16v',
      meta: 'Мотор Lacetti 1.6 (109 л.с.) • Кондиционер, ГУР, вместительный багажник',
      minPrice: 110000,
      keywords: ['дэу', 'daewoo', 'нексия', 'nexia', '1.6', '16v', '1.5', 'седан']
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
    },

    // --- КОМПЬЮТЕРЫ: ОПЕРАТИВНАЯ ПАМЯТЬ (RAM DDR5 / DDR4) ---
    {
      title: 'DDR5 32GB (2x16GB) 6000MHz CL30 Kingston Fury Beast',
      query: 'DDR5 32GB 6000MHz Kingston',
      category: 'tech',
      badge: '⚡ ОЗУ • DDR5 32GB 6000MHz',
      meta: 'Комплект 32GB (2x16GB) • Низкие тайминги CL30/CL36 • EXPO и XMP профили',
      minPrice: 7500,
      keywords: ['ddr5', 'ддр5', 'ddr 5', 'ддр 5', 'оперативка', 'память', 'kingston', 'fury', '32gb', '6000mhz', 'озу', 'ram']
    },
    {
      title: 'DDR5 32GB (2x16GB) 6000MHz G.Skill Trident Z5 RGB',
      query: 'DDR5 32GB G.Skill Trident Z5',
      category: 'tech',
      badge: '⚡ ОЗУ • G.Skill Trident Z5',
      meta: 'Флагманские чипы Hynix A-die • CL30 • Настраиваемая яркая подсветка RGB',
      minPrice: 9500,
      keywords: ['ddr5', 'ддр5', 'ddr 5', 'g.skill', 'g skill', 'trident z5', 'rgb', '32gb', '6000mhz', 'cl30']
    },
    {
      title: 'DDR5 32GB (2x16GB) 6400MHz Corsair Vengeance RGB',
      query: 'DDR5 32GB 6400MHz Corsair',
      category: 'tech',
      badge: '⚡ ОЗУ • Corsair Vengeance',
      meta: 'Высокая частота 6400MHz • Алюминиевые радиаторы охлаждения',
      minPrice: 9000,
      keywords: ['ddr5', 'ддр5', 'corsair', 'vengeance', '32gb', '6400mhz', 'оперативка']
    },
    {
      title: 'DDR5 32GB (2x16GB) 6000MHz ADATA XPG Lancer Blade',
      query: 'DDR5 32GB ADATA XPG 6000MHz',
      category: 'tech',
      badge: '⚡ ОЗУ • ADATA XPG',
      meta: 'Компактные радиаторы под башенные кулеры • Чипы SK Hynix',
      minPrice: 7500,
      keywords: ['ddr5', 'ддр5', 'adata', 'xpg', 'lancer', '32gb', '6000mhz']
    },
    {
      title: 'DDR5 64GB (2x32GB) 6000MHz CL30 Kingston / G.Skill',
      query: 'DDR5 64GB 6000MHz',
      category: 'tech',
      badge: '⚡ ОЗУ • DDR5 64GB',
      meta: 'Мощный объем 64GB для 3D рендера, работы и топовых игр без компромиссов',
      minPrice: 16000,
      keywords: ['ddr5', 'ддр5', '64gb', '64 gb', 'оперативка', 'память', '2x32gb']
    },
    {
      title: 'DDR5 16GB (1x16GB) 4800MHz / 5600MHz Kingston Fury',
      query: 'DDR5 16GB 5600MHz',
      category: 'tech',
      badge: '⚡ ОЗУ • DDR5 16GB',
      meta: 'Одиночная планка 16GB для бюджетных сборок или апгрейда второго слота',
      minPrice: 3500,
      keywords: ['ddr5', 'ддр5', '16gb', '16 gb', 'память', 'оперативка']
    },
    {
      title: 'DDR5 SODIMM 16GB / 32GB для ноутбука',
      query: 'DDR5 SODIMM 4800MHz 5600MHz',
      category: 'tech',
      badge: '⚡ ОЗУ • Ноутбук DDR5',
      meta: 'Форм-фактор SO-DIMM для игровых ноутбуков ASUS, Lenovo Legion, MSI, Acer',
      minPrice: 3500,
      keywords: ['ddr5', 'ддр5', 'sodimm', 'содимм', 'ноутбук', 'для ноутбука', 'лэптоп']
    },
    {
      title: 'Комплект DDR5 32GB + AM5 B650 + Ryzen 7500F',
      query: 'Комплект AM5 B650 Ryzen 7500F DDR5',
      category: 'tech',
      badge: '⚡ Сет • AM5 + DDR5',
      meta: 'Готовая связка: процессор Ryzen 5 7500F + плата B650 + память DDR5 32GB',
      minPrice: 28000,
      keywords: ['комплект', 'сет', 'am5', 'b650', 'ddr5', 'ддр5', 'ryzen 7500f', 'связка']
    },
    {
      title: 'DDR4 32GB (2x16GB) 3200MHz / 3600MHz Kingston Fury Beast',
      query: 'DDR4 32GB 3200MHz Kingston Fury',
      category: 'tech',
      badge: '⚡ ОЗУ • DDR4 32GB',
      meta: 'Популярнейший надежный комплект DDR4 для платформы AM4 и LGA1700',
      minPrice: 4500,
      keywords: ['ddr4', 'ддр4', 'ddr 4', 'ддр 4', 'kingston', 'fury', '32gb', '3200mhz', '3600mhz', 'оперативка']
    },
    {
      title: 'DDR4 16GB (2x8GB) 3200MHz Kingston Fury Beast',
      query: 'DDR4 16GB 3200MHz Kingston',
      category: 'tech',
      badge: '⚡ ОЗУ • DDR4 16GB',
      meta: 'Классический комплект 2x8GB для быстрых народных сборок',
      minPrice: 2500,
      keywords: ['ddr4', 'ддр4', '16gb', '3200mhz', 'память']
    },
    {
      title: 'DDR4 SODIMM 16GB / 32GB для ноутбука',
      query: 'DDR4 SODIMM 3200MHz',
      category: 'tech',
      badge: '⚡ ОЗУ • Ноутбук DDR4',
      meta: 'Память SO-DIMM DDR4 3200MHz для модернизации рабочих ноутбуков',
      minPrice: 2500,
      keywords: ['ddr4', 'ддр4', 'sodimm', 'содимм', 'ноутбук']
    },

    // --- КОМПЬЮТЕРЫ: ПРОЦЕССОРЫ (CPU) ---
    {
      title: 'AMD Ryzen 7 7800X3D (AM5)',
      query: 'Ryzen 7 7800X3D',
      category: 'tech',
      badge: '⚡ CPU • Ryzen 7 7800X3D',
      meta: 'Лучший игровой процессор в мире • 8 ядер / 16 потоков • 96MB 3D V-Cache • AM5',
      minPrice: 29000,
      keywords: ['процессор', 'проц', 'ryzen', '7800x3d', 'райзен', 'am5', 'amd']
    },
    {
      title: 'AMD Ryzen 5 7500F / 7600 (AM5)',
      query: 'Ryzen 5 7500F',
      category: 'tech',
      badge: '⚡ CPU • Ryzen 5 7500F',
      meta: 'Хит продаж под DDR5 • 6 ядер Zen 4 • Идеален для видеокарт уровня RTX 4070',
      minPrice: 11000,
      keywords: ['процессор', 'проц', 'ryzen', '7500f', '7600', 'райзен', 'am5']
    },
    {
      title: 'AMD Ryzen 5 5600 / 5600X (AM4)',
      query: 'Ryzen 5 5600',
      category: 'tech',
      badge: '⚡ CPU • Ryzen 5 5600',
      meta: 'Легендарный народный процессор под сокет AM4 • 6 ядер / 12 потоков',
      minPrice: 8000,
      keywords: ['процессор', 'проц', 'ryzen', '5600', '5600x', 'am4', 'райзен']
    },
    {
      title: 'AMD Ryzen 7 5700X3D (AM4)',
      query: 'Ryzen 7 5700X3D',
      category: 'tech',
      badge: '⚡ CPU • Ryzen 7 5700X3D',
      meta: 'Финальный апгрейд платформы AM4 с кэшем 3D V-Cache для тяжелых игр',
      minPrice: 16000,
      keywords: ['процессор', 'ryzen', '5700x3d', 'am4', 'райзен']
    },
    {
      title: 'Intel Core i5 13400F / 14400F (LGA1700)',
      query: 'Core i5 13400F',
      category: 'tech',
      badge: '⚡ CPU • Core i5 13400F',
      meta: '10 ядер (6P + 4E) • До 4.6 ГГц • Поддержка DDR4 и DDR5 памяти',
      minPrice: 14000,
      keywords: ['процессор', 'intel', 'i5', '13400f', '14400f', 'интел', 'lga1700']
    },
    {
      title: 'Intel Core i5 12400F (LGA1700)',
      query: 'Core i5 12400F',
      category: 'tech',
      badge: '⚡ CPU • Core i5 12400F',
      meta: '6 производительных ядер • Народный процессор под видеокарты RTX 4060',
      minPrice: 9000,
      keywords: ['процессор', 'intel', 'i5', '12400f', 'lga1700', 'интел']
    },
    {
      title: 'Intel Core i5 13600KF / 14600KF (LGA1700)',
      query: 'Core i5 13600KF',
      category: 'tech',
      badge: '⚡ CPU • Core i5 13600KF',
      meta: '14 ядер • Разблокированный множитель • Частота до 5.1 ГГц',
      minPrice: 23000,
      keywords: ['процессор', 'intel', 'i5', '13600kf', '14600kf']
    },
    {
      title: 'Intel Core i7 13700KF / 14700KF (LGA1700)',
      query: 'Core i7 13700KF',
      category: 'tech',
      badge: '⚡ CPU • Core i7 13700KF',
      meta: '16 ядер / 24 потока • Мощная производительность для монтажа и 4K игр',
      minPrice: 32000,
      keywords: ['процессор', 'intel', 'i7', '13700kf', '14700kf']
    },

    // --- КОМПЬЮТЕРЫ: МАТЕРИНСКИЕ ПЛАТЫ И SSD ---
    {
      title: 'Материнская плата B650 AM5 (MSI, ASUS, Gigabyte)',
      query: 'Материнская плата B650',
      category: 'tech',
      badge: '⚡ Плата • AM5 B650',
      meta: 'Поддержка процессоров Ryzen 7000/8000/9000 • Слоты DDR5, PCIe 4.0/5.0 M.2',
      minPrice: 12000,
      keywords: ['материнская плата', 'материнка', 'мать', 'b650', 'am5', 'msi', 'asus', 'gigabyte']
    },
    {
      title: 'Материнская плата B760 LGA1700 DDR5 / DDR4',
      query: 'Материнская плата B760',
      category: 'tech',
      badge: '⚡ Плата • LGA1700 B760',
      meta: 'Поддержка процессоров Intel Core 12, 13 и 14 поколения • Мощный VRM питания',
      minPrice: 10000,
      keywords: ['материнская плата', 'материнка', 'b760', 'lga1700', 'ddr5', 'ddr4']
    },
    {
      title: 'Материнская плата Z790 LGA1700 DDR5',
      query: 'Материнская плата Z790',
      category: 'tech',
      badge: '⚡ Плата • Z790 DDR5',
      meta: 'Топовый чипсет для разгона процессора и оперативной памяти DDR5 7000+ MHz',
      minPrice: 18000,
      keywords: ['материнская плата', 'z790', 'lga1700', 'ddr5']
    },
    {
      title: 'SSD M.2 NVMe 1TB Samsung 980 Pro / 990 Pro',
      query: 'Samsung 980 Pro 1TB',
      category: 'tech',
      badge: '⚡ SSD • Samsung 980 Pro',
      meta: 'Скорость чтения до 7000-7450 МБ/с • Буфер DRAM • Высокий ресурс TBW',
      minPrice: 7500,
      keywords: ['ssd', 'ссд', 'm.2', 'nvme', 'samsung', '980 pro', '990 pro', '1tb']
    },
    {
      title: 'SSD M.2 NVMe 2TB Samsung 990 Pro / Kingston KC3000',
      query: 'SSD 2TB M.2 NVMe',
      category: 'tech',
      badge: '⚡ SSD • 2TB NVMe',
      meta: 'Огромный объем 2000GB под библиотеку современных игр и быстрый запуск системы',
      minPrice: 14000,
      keywords: ['ssd', 'ссд', '2tb', 'm.2', 'nvme', '990 pro', 'kc3000']
    },
    {
      title: 'SSD M.2 NVMe 1TB Kingston KC3000',
      query: 'Kingston KC3000 1TB',
      category: 'tech',
      badge: '⚡ SSD • Kingston KC3000',
      meta: 'Скорость 7000 МБ/с • Контроллер Phison E18 • Графеновый радиатор',
      minPrice: 7000,
      keywords: ['ssd', 'ссд', 'kingston', 'kc3000', '1tb', 'm.2']
    },

    // --- МОНИТОРЫ ---
    {
      title: 'Монитор 27" 2K 144Hz / 165Hz / 180Hz IPS',
      query: 'Монитор 27 2K 165Hz',
      category: 'tech',
      badge: '🖥 Монитор • 27" 2K 165Hz',
      meta: 'Разрешение 2560x1440 • Быстрая IPS матрица 1мс • G-Sync / FreeSync',
      minPrice: 15000,
      keywords: ['монитор', '27', '2k', '144hz', '165hz', '180hz', 'ips', 'гейминг']
    },
    {
      title: 'OLED монитор 27" 240Hz 2K (LG, ASUS, AOC)',
      query: 'OLED монитор 27 240Hz',
      category: 'tech',
      badge: '🖥 Монитор • 27" OLED 240Hz',
      meta: 'Идеальный черный цвет • Отклик 0.03 мс • Плавность 240Hz для киберспорта',
      minPrice: 60000,
      keywords: ['монитор', 'oled', 'олед', '240hz', '27']
    },

    // --- СМАРТФОНЫ И ГАДЖЕТЫ ---
    {
      title: 'iPhone 16 Pro Max 256GB / 512GB',
      query: 'iPhone 16 Pro Max 256GB',
      category: 'tech',
      badge: '📱 Apple • 16 Pro Max',
      meta: 'Экран 6.9 дюймов • Кнопка Camera Control • Чип A18 Pro • Титановый корпус',
      minPrice: 95000,
      keywords: ['айфон', 'iphone', '16 pro max', '16 про макс', 'apple']
    },
    {
      title: 'iPhone 16 Pro 128GB / 256GB',
      query: 'iPhone 16 Pro',
      category: 'tech',
      badge: '📱 Apple • 16 Pro',
      meta: 'Экран 6.3" ProMotion 120Hz • Камера 5x перископ • Автономность',
      minPrice: 85000,
      keywords: ['айфон', 'iphone', '16 pro', '16 про', 'apple']
    },
    {
      title: 'iPhone 16 128GB / 256GB',
      query: 'iPhone 16 128GB',
      category: 'tech',
      badge: '📱 Apple • iPhone 16',
      meta: 'Новая вертикальная камера для пространственного видео • Чип A18 • Action Button',
      minPrice: 65000,
      keywords: ['айфон', 'iphone', '16', 'apple']
    },
    {
      title: 'iPhone 14 Pro Max 128GB / 256GB',
      query: 'iPhone 14 Pro Max',
      category: 'tech',
      badge: '📱 Apple • 14 Pro Max',
      meta: 'Dynamic Island • Камера 48 Мп • Всегда включенный экран Always-On',
      minPrice: 62000,
      keywords: ['айфон', 'iphone', '14 pro max', '14 про макс', 'apple']
    },
    {
      title: 'iPhone 13 128GB',
      query: 'iPhone 13 128GB',
      category: 'tech',
      badge: '📱 Apple • iPhone 13',
      meta: 'Хит продаж • Яркий OLED Super Retina • Двойная диагональная камера',
      minPrice: 35000,
      keywords: ['айфон', 'iphone', '13', 'apple']
    },
    {
      title: 'Apple AirPods Pro 2 (Type-C / MagSafe)',
      query: 'AirPods Pro 2 Type-C',
      category: 'tech',
      badge: '🎧 Apple • AirPods Pro 2',
      meta: 'Активное шумоподавление нового поколения 2x • Разъем USB Type-C',
      minPrice: 14000,
      keywords: ['аирподс', 'airpods', 'airpods pro 2', 'про 2', 'наушники', 'apple']
    },
    {
      title: 'Apple AirPods Max',
      query: 'AirPods Max',
      category: 'tech',
      badge: '🎧 Apple • AirPods Max',
      meta: 'Полноразмерные беспроводные наушники • Алюминиевые чашки, премиум звук',
      minPrice: 35000,
      keywords: ['аирподс макс', 'airpods max', 'макс', 'apple', 'наушники']
    },
    {
      title: 'Apple Watch Ultra 2 (49mm)',
      query: 'Apple Watch Ultra 2',
      category: 'tech',
      badge: '⌚️ Apple • Watch Ultra 2',
      meta: 'Титановый корпус 49мм • Сапфировое стекло 3000 нит • Двухчастотный GPS',
      minPrice: 55000,
      keywords: ['эппл вотч', 'apple watch', 'ultra 2', 'ультра 2', 'часы']
    },
    {
      title: 'MacBook Air 13 M2 8/256GB / 16/512GB',
      query: 'MacBook Air M2',
      category: 'tech',
      badge: '💻 Apple • MacBook Air M2',
      meta: 'Экран Liquid Retina 13.6" • Тонкий алюминиевый корпус • До 18 часов работы',
      minPrice: 65000,
      keywords: ['макбук', 'macbook', 'air m2', 'эир м2', 'apple', 'ноутбук']
    },
    {
      title: 'Nintendo Switch OLED 64GB',
      query: 'Nintendo Switch OLED',
      category: 'tech',
      badge: '🎮 Консоль • Switch OLED',
      meta: 'Красочный 7-дюймовый OLED дисплей • Широкая опора • LAN-порт в док-станции',
      minPrice: 22000,
      keywords: ['нинтендо', 'свитч', 'сыч', 'nintendo', 'switch oled', 'консоль']
    },
    {
      title: 'ASUS ROG Ally Z1 Extreme',
      query: 'ASUS ROG Ally Z1 Extreme',
      category: 'tech',
      badge: '🎮 Портатив • ROG Ally',
      meta: 'Процессор AMD Z1 Extreme • Экран Full HD 120Hz с VRR • Windows 11',
      minPrice: 45000,
      keywords: ['asus', 'rog ally', 'рог элай', 'z1 extreme', 'портатив']
    },

    // --- БЫТОВАЯ ТЕХНИКА И ИНСТРУМЕНТЫ ---
    {
      title: 'Робот-пылесос Roborock S8 / Q Revo',
      query: 'Roborock S8',
      category: 'tech',
      badge: '🤖 Уборка • Roborock',
      meta: 'Двойная турбощетка DuoRoller • Сила всасывания 6000 Па • Лидар навигация',
      minPrice: 30000,
      keywords: ['робот пылесос', 'роборок', 'roborock', 's8', 'q revo', 'пылесос']
    },
    {
      title: 'Кофемашина DeLonghi Magnifica S / Evo',
      query: 'DeLonghi Magnifica',
      category: 'tech',
      badge: '☕️ Кофемашина • DeLonghi',
      meta: 'Автоматическое приготовление эспрессо и капучино • Встроенная кофемолка',
      minPrice: 22000,
      keywords: ['делонги', 'delonghi', 'magnifica', 'магнифика', 'кофемашина']
    },
    {
      title: 'Перфоратор Makita HR2470 / HR2630 SDS-Plus',
      query: 'Перфоратор Makita HR2470',
      category: 'tech',
      badge: '🛠 Инструмент • Makita',
      meta: '780 Вт • Энергия удара 2.7 Дж • 3 режима работы • Надежная муфта',
      minPrice: 6000,
      keywords: ['макита', 'makita', 'перфоратор', 'hr2470', 'инструмент']
    },

    // --- АВТО: КОЛЕСА И ШИНЫ ---
    {
      title: 'Колеса в сборе R17 / R18 / R19 (диски + шины)',
      query: 'Колеса в сборе R18',
      category: 'auto',
      badge: '🛞 Колеса • В сборе',
      meta: 'Оригинальные легкосплавные диски с сезонной резиной в отличном состоянии',
      minPrice: 20000,
      keywords: ['колеса', 'в сборе', 'r17', 'r18', 'r19', 'диски', 'резина']
    },
    {
      title: 'Литые диски R17 / R18 (5x112, 5x114.3, 5x108)',
      query: 'Литые диски R18',
      category: 'auto',
      badge: '🛞 Колеса • Литые диски',
      meta: 'Без варок и трещин • Ровная геометрия • Проверка на балансировочном станке',
      minPrice: 18000,
      keywords: ['диски', 'литые', 'r17', 'r18', '5x112', '5x114.3', 'литье']
    },
    {
      title: 'Зимняя резина шипованная / липучка R16 / R17 / R18',
      query: 'Зимняя резина R17',
      category: 'auto',
      badge: '🛞 Шины • Зимние',
      meta: 'Nokian, Michelin, Continental, Pirelli • Все шипы на месте, остаток 80%+',
      minPrice: 12000,
      keywords: ['резина', 'шины', 'зимняя', 'зима', 'липучка', 'шипы', 'r16', 'r17', 'r18']
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

        // Multi-word token matching (e.g. "daewoo matiz" or "matiz 0.8" or "матиз автомат")
        const tokens = qNorm.split(/\s+/).filter(t => t.length >= 2);
        if (tokens.length > 1) {
          const matchCount = tokens.filter(t =>
            titleNorm.includes(t) || queryNorm.includes(t) || metaNorm.includes(t) || kwNorms.some(k => k.includes(t))
          ).length;
          if (matchCount === tokens.length) {
            bestScore = Math.max(bestScore, 80);
          } else if (matchCount > 1) {
            bestScore = Math.max(bestScore, 50 + matchCount * 10);
          }
        }
      }

      if (bestScore > 0) {
        scored.push({ item, score: bestScore });
      }
    }

    scored.sort((a, b) => b.score - a.score);

    // =========================================================================
    // DYNAMIC CONTINUATION ENGINE ("Самый оптимизированный выход")
    // If fewer than limit items found, generate contextual Avito intent continuations
    // =========================================================================
    if (scored.length < limit) {
      const existingQueries = new Set(scored.map(s => s.item.query.toLowerCase()));
      const rawTrimmed = inputQuery.trim();
      const lowerTrimmed = rawTrimmed.toLowerCase();

      const isDdr = /ddr|ддр/i.test(lowerTrimmed);
      const isGpu = /rtx|ртх|rx|gtx|видюх|видеокарт/i.test(lowerTrimmed);
      const isCpu = /ryzen|райзен|core|intel|интел|проц/i.test(lowerTrimmed);
      const isApple = /айфон|iphone|apple|эппл|ipad|айпад|macbook|макбук/i.test(lowerTrimmed);
      const isMatiz = /матиз|matiz/i.test(lowerTrimmed);
      const isAuto = isMatiz || /бмв|bmw|мерс|mercedes|лада|lada|веста|vesta|тойота|toyota|камри|camry|ауди|audi|киа|kia|хендай|hyundai|фолькс|vw|volkswagen|дэу|daewoo|некси|nexia|ланос|lanos|шевроле|chevrolet|ваз|vaz|приор|priora|грант|granta|калин|kalina|нива|niva|солярис|solaris|рио|rio|форд|ford|фокус|focus|рено|renault|логан|logan|шкода|skoda|октави|octavia|рапид|rapid|мазда|mazda|митсубис|mitsubishi|хонда|honda|ниссан|nissan|пежо|peugeot|ситроен|citroen|опель|opel|джили|geely|хавал|haval|чери|chery|танк|tank|зикр|zeekr|лисян|lixiang|седан|хэтчбек|универсал|кроссовер|внедорожник|колес|диск|резин|шин/i.test(lowerTrimmed);
      const isTech = isDdr || isGpu || isCpu || isApple || /samsung|самсунг|ps5|пс5|xbox|steam|ssd|ссд|монитор|гравел|велосипед/i.test(lowerTrimmed);

      let continuations = [];
      if (isMatiz) {
        continuations = [
          { suffix: '0.8 МКПП', meta: '0.8 л (52 л.с.) МКПП • Экономичный расход, надежная механика', minPrice: 80000 },
          { suffix: '0.8 АКПП Автомат', meta: 'Редкая версия с надежным 4-ступенчатым японским автоматом Jatco', minPrice: 140000 },
          { suffix: '1.0 Best (4 цилиндра)', meta: '1.0 л (64 л.с.) 4-цилиндровый мотор • Топовая резвая версия Best с ГУР', minPrice: 130000 },
          { suffix: 'с кондиционером и ГУР', meta: 'Комфортная комплектация MX / Best • Кондиционер, ГУР, электростекла', minPrice: 110000 },
          { suffix: 'Рестайлинг (2008-2015)', meta: 'Поздние годы выпуска M150 • Обновленная оптика и салон, евро-3/4', minPrice: 120000 },
          { suffix: 'до 150 000 ₽', meta: 'Бюджетный рабочий авто на каждый день на уверенном ходу', minPrice: 80000 }
        ];
      } else if (isAuto) {
        continuations = [
          { suffix: 'автомат / АКПП', meta: 'Классическая автоматическая трансмиссия, плавный ход в городе', minPrice: 350000 },
          { suffix: 'механика / МКПП', meta: 'Надежная механическая коробка передач, экономичный расход', minPrice: 150000 },
          { suffix: 'с кондиционером', meta: 'Рабочий климат/кондиционер, комфорт в любое время года', minPrice: 200000 },
          { suffix: '1 владелец без ДТП', meta: 'Зеленая Автотека, заводской окрас, оригинальный ПТС', minPrice: 400000 },
          { suffix: 'в максимальной комплектации', meta: 'Полный пакет опций, мультимедиа, подогревы сидений', minPrice: 600000 },
          { suffix: 'рестайлинг', meta: 'Обновленная версия кузова, доработанные двигатели и оптика', minPrice: 300000 }
        ];
      } else if (isDdr) {
        continuations = [
          { suffix: '32GB 6000MHz', meta: 'Оптимальный комплект памяти CL30/CL36 для игр', minPrice: 7000 },
          { suffix: '64GB (2x32GB)', meta: 'Двухканальный комплект для тяжелых задач и рендера', minPrice: 15000 },
          { suffix: 'Kingston Fury Beast 32GB', meta: 'Проверенная память с алюминиевыми радиаторами', minPrice: 7500 },
          { suffix: 'G.Skill Trident Z5 RGB 32GB', meta: 'Топовые чипы Hynix с синхронизацией RGB', minPrice: 9500 },
          { suffix: 'SODIMM для ноутбука', meta: 'Компактные планки SO-DIMM для игровых лэптопов', minPrice: 3500 },
          { suffix: 'комплект с AM5 B650', meta: 'Готовая связка: процессор + материнская плата + ОЗУ', minPrice: 25000 }
        ];
      } else if (isGpu) {
        continuations = [
          { suffix: 'новый на пломбах', meta: 'Запечатанная коробка с чеком и гарантией', minPrice: 35000 },
          { suffix: 'в идеальном состоянии', meta: 'Любые тесты FurMark / Superposition, без майнинга', minPrice: 25000 },
          { suffix: '12GB / 16GB GDDR6X', meta: 'Запас видеопамяти под современные 2K/4K игры', minPrice: 45000 },
          { suffix: 'с гарантией DNS / Ситилинк', meta: 'Официальный чек и остаток гарантии в РФ', minPrice: 30000 }
        ];
      } else if (isCpu) {
        continuations = [
          { suffix: 'BOX с кулером', meta: 'Коробочная версия с оригинальным кулером', minPrice: 12000 },
          { suffix: 'новый запечатанный', meta: 'Заводские пломбы, ножки целые', minPrice: 10000 },
          { suffix: 'комплект с платой и памятью', meta: 'Проверенная готовая основа для ПК', minPrice: 20000 }
        ];
      } else if (isApple) {
        continuations = [
          { suffix: '128GB оригинал', meta: 'Отличное состояние, Face ID и True Tone работают', minPrice: 40000 },
          { suffix: '256GB полный комплект', meta: 'Коробка, провод, аккумулятор 88%+', minPrice: 50000 },
          { suffix: 'новый не активирован', meta: 'Запечатан, официальная гарантия Apple 1 год', minPrice: 65000 }
        ];
      } else {
        continuations = [
          { suffix: 'в отличном состоянии', meta: 'Полностью исправен, бережная эксплуатация, без дефектов', minPrice: 2000 },
          { suffix: 'в полном комплекте', meta: 'Оригинальная заводская коробка, документы, все аксессуары', minPrice: 3000 },
          { suffix: 'новый в упаковке', meta: 'Запечатан, заводские пломбы, не был в использовании', minPrice: 4000 },
          { suffix: 'оригинал с чеком', meta: 'Подлинный товар с чеком из магазина и остатком гарантии', minPrice: 2500 }
        ];
      }

      for (const c of continuations) {
        const lowerSuffix = c.suffix.toLowerCase();
        if (lowerTrimmed.includes(lowerSuffix)) continue;

        const fullTitle = `${rawTrimmed} ${c.suffix}`;
        if (!existingQueries.has(fullTitle.toLowerCase())) {
          scored.push({
            item: {
              title: fullTitle,
              query: fullTitle,
              category: isAuto ? 'auto' : (isTech ? 'tech' : 'goods'),
              badge: isMatiz ? '🚗 Matiz' : (isAuto ? '🚗 Авто' : (isDdr ? '⚡ DDR' : (isGpu ? '⚡ GPU' : (isTech ? '⚡ Электроника' : '🔍 Каталог')))),
              meta: c.meta,
              minPrice: c.minPrice || 0,
              keywords: [rawTrimmed.toLowerCase()]
            },
            score: 50
          });
          existingQueries.add(fullTitle.toLowerCase());
          if (scored.length >= limit) break;
        }
      }
    }

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
