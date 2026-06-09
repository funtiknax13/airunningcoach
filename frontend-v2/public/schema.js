(function () {
  var schemas = [
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "name": "AI RunningCoach",
      "url": "https://airunningcoach.pro",
      "description": "Персональный AI-тренер по бегу. Генерация планов тренировок, анализ пробежек, импорт GPX и FIT файлов из Garmin, Coros, Suunto.",
      "applicationCategory": "SportsApplication",
      "operatingSystem": "Web",
      "inLanguage": ["ru", "en"],
      "offers": [
        {
          "@type": "Offer",
          "name": "Basic",
          "price": "0",
          "priceCurrency": "RUB",
          "description": "Запись пробежек, импорт GPX/FIT, AI-тренер 10 сообщений в день"
        },
        {
          "@type": "Offer",
          "name": "Premium",
          "price": "490",
          "priceCurrency": "RUB",
          "billingIncrement": "P1M",
          "description": "Безлимитный AI-тренер, генерация планов тренировок, детальная аналитика"
        }
      ],
      "featureList": [
        "Персональные планы тренировок на основе AI",
        "Импорт пробежек из Garmin, Coros, Suunto, Polar (GPX, FIT)",
        "Анализ темпа, пульса, каденса и сплитов",
        "Подготовка к 5 км, 10 км, полумарафону и марафону",
        "AI-тренер: отвечает на вопросы по технике и питанию",
        "Цели и отслеживание прогресса"
      ],
      "screenshot": "https://airunningcoach.pro/images/og-image.png",
      "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": "4.8",
        "reviewCount": "1"
      }
    },
    {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "Что такое AI RunningCoach?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "AI RunningCoach — это веб-приложение с персональным AI-тренером по бегу."
          }
        },
        {
          "@type": "Question",
          "name": "Как импортировать пробежки из Garmin или Coros?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "AI RunningCoach поддерживает импорт файлов GPX и FIT из Garmin Connect, Coros, Suunto или Polar."
          }
        },
        {
          "@type": "Question",
          "name": "Можно ли подготовиться к марафону с помощью AI?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Да. AI RunningCoach составляет персональные планы подготовки к 5 км, 10 км, полумарафону и марафону."
          }
        },
        {
          "@type": "Question",
          "name": "Сколько стоит AI RunningCoach?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Базовый план бесплатный. Premium — 490 рублей в месяц. При регистрации — 14 дней Premium бесплатно."
          }
        },
        {
          "@type": "Question",
          "name": "Работает ли приложение без скачивания?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Да, AI RunningCoach — это веб-приложение. Работает в браузере, никакой установки не требуется."
          }
        }
      ]
    }
  ];

  schemas.forEach(function (schema) {
    var el = document.createElement('script');
    el.type = 'application/ld+json';
    el.textContent = JSON.stringify(schema);
    document.head.appendChild(el);
  });
})();
