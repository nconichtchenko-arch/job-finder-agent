Job Finder Agent 🤖
Автоматизированный агент для поиска вакансий на hh.ru с фильтрацией по релевантности и сохранением в PostgreSQL.

Зачем этот проект: в апреле 2026 года HeadHunter закрыл публичный API для поиска вакансий. Этот агент обходит ограничение через парсинг HTML-страниц и продолжает находить релевантные вакансии для аналитиков данных.

📋 Содержание
Возможности

Архитектура

Стек технологий

Как это работает

Установка и запуск

Схема базы данных

Результаты работы

Структура репозитория

Автор

✨ Возможности
🔍 Автоматический сбор вакансий с hh.ru (парсинг HTML-страниц, обход закрытого API).

🎯 Фильтрация по релевантности: скоринг по ключевым словам с весами (SQL, Python, аналитик, data и др.).

💾 Хранение в PostgreSQL: нормализованная схема, дедупликация по hh_id.

📊 ТОП-10 релевантных вакансий — вывод в консоль с ссылками, компаниями и зарплатами.

🔐 Разделение ролей БД: владелец (postgres) и пользователь приложения (course).

🛡️ Обработка ошибок: сетевые сбои, некорректные даты, дубликаты.

🏗 Архитектура
┌─────────────────────┐
│   hh.ru (HTML)      │  ← источник вакансий (API закрыт с 04.2026)
└──────────┬──────────┘
           │ requests + BeautifulSoup
           ▼
┌─────────────────────┐
│  job_agent.py       │  ← парсинг, фильтрация, скоринг
│  - fetch_vacancies  │
│  - save_vacancies   │
│  - filter_vacancies │
│  - show_top         │
└──────────┬──────────┘
           │ SQLAlchemy + psycopg3
           ▼
┌─────────────────────┐
│   PostgreSQL        │  ← хранение вакансий
│   vacancies         │
│   filtered_vacancies│
└─────────────────────┘

🛠 Стек технологий
Python 3.12

requests — HTTP-запросы к hh.ru

BeautifulSoup4 — парсинг HTML

SQLAlchemy — ORM для работы с PostgreSQL

psycopg3 — драйвер PostgreSQL

python-dotenv — управление переменными окружения

PostgreSQL 17 — база данных

⚙️ Как это работает
1. Сбор вакансий (fetch_vacancies)
Агент делает GET-запрос к hh.ru/search/vacancy с браузерным User-Agent. Внутри HTML-страницы в теге <template id="HH-Lux-InitialState"> лежит JSON с вакансиями. Мы извлекаем его и преобразуем в формат, похожий на ответ API.

2. Сохранение в БД (save_vacancies)
Каждая вакансия сохраняется в таблицу vacancies. Дубликаты отсекаются на уровне БД через ON CONFLICT (hh_id) DO NOTHING. Даты парсятся с учётом формата hh.ru ({"$date": "..."}).

3. Фильтрация (filter_vacancies)
Считается relevance_score — сумма весов найденных ключевых слов:

SQL, Python, Pandas → 5 баллов

Аналитик, BI, дашборд → 3-4 балла

Data, Analyst, отчет → 2-3 балла

Вакансии со скором ≥ 5 попадают в таблицу filtered_vacancies.

4. Вывод (show_top_vacancies)
ТОП-10 отфильтрованных вакансий выводится в консоль: название, компания, зарплата, релевантность, ссылка.

🚀 Установка и запуск
1. Клонировать репозиторий
bash
git clone https://github.com/nconichtchenko-arch/job-finder-agent.git
cd job-finder-agent
2. Создать виртуальное окружение
bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
3. Установить зависимости
bash
pip install -r requirements.txt
4. Настроить .env
Скопируй .env.example → .env и заполни своими данными:

bash
cp .env.example .env
Открой .env и укажи:

Параметры подключения к PostgreSQL

HH_USER_AGENT — обязательно с реальным email

5. Создать таблицы в PostgreSQL
Выполни SQL из раздела Схема базы данных.

6. Запустить агента
bash
python job_agent.py
🗄 Схема базы данных
Таблица vacancies
sql
CREATE TABLE pavel_onichtchenko.vacancies (
    id SERIAL PRIMARY KEY,
    hh_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    employer_name VARCHAR(500),
    salary_from INT,
    salary_to INT,
    currency VARCHAR(10),
    area_name VARCHAR(200),
    experience VARCHAR(100),
    schedule VARCHAR(100),
    description TEXT,
    url VARCHAR(1000),
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
Таблица filtered_vacancies
sql
CREATE TABLE pavel_onichtchenko.filtered_vacancies (
    id SERIAL PRIMARY KEY,
    vacancy_id INT REFERENCES pavel_onichtchenko.vacancies(id),
    relevance_score INT,
    match_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vacancy_id)
);
📊 Результаты работы
Пример вывода агента:

text
📊 Всего загружено: 100 вакансий
💾 Сохранено новых: 100, пропущено: 0

🔍 Проверяю 185 новых вакансий...
✅ Отфильтровано: 57 релевантных вакансий

🏆 ТОП-10 РЕЛЕВАНТНЫХ ВАКАНСИЙ

1. Дата-аналитик (SQL, Python)
   Компания: Честный знак.рф
   Релевантность: 14
   Ссылка: https://hh.ru/vacancy/136928020

2. Аналитик данных / Data Analyst
   Компания: ТАРГЕТ АДС
   Зарплата: 110000 - 200000 руб.
   Релевантность: 13

...
📁 Структура репозитория
text
job-finder-agent/
│
├── README.md              # Этот файл
├── requirements.txt       # Зависимости Python
├── job_agent.py           # Основной код агента
├── .gitignore             # Что НЕ заливать в git
├── .env.example           # Шаблон переменных окружения
│
├── docs/
│   └── final_report.md    # Технический отчёт о проекте
│
└── data/                  # Папка для локальных данных
💡 Планы по развитию
□ Telegram-уведомления о новых вакансиях
□ Генерация сопроводительных писем через LLM (YandexGPT / OpenAI)
□ Дашборд на Plotly / Panel со статистикой поиска
□ Расширение парсинга на Хабр Карьеру и LinkedIn
□ Переход на официальный API при получении токена работодателя

👤 Автор
Онищенко Павел Владимирович

GitHub: @nconichtchenko-arch

Email: pavloni@mail.ru

Проект создан как инструмент для автоматизации поиска работы аналитиком данных. Использует только публично доступные данные hh.ru.
