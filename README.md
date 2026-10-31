# Job Finder Agent

Автоматизированный агент для поиска вакансий на **hh.ru** и **Хабр Карьере** с фильтрацией по релевантности и сохранением в PostgreSQL. 

**Зачем этот проект:** в апреле 2026 года HeadHunter закрыл публичный API для поиска вакансий. Этот агент обходит ограничение через парсинг HTML-страниц hh.ru и использует открытый API Хабр Карьеры, продолжая находить релевантные вакансии для аналитиков данных и DWH-инженеров.

## Содержание

- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Стек технологий](#стек-технологий)
- [Как это работает](#как-это-работает)
- [Установка и запуск](#установка-и-запуск)
- [Схема базы данных](#схема-базы-данных)
- [Результаты работы](#результаты-работы)
- [Структура репозитория](#структура-репозитория)
- [Автор](#автор)

## Возможности

- **Два источника:** автоматический сбор вакансий с **hh.ru** (парсинг HTML-страниц) и **Хабр Карьеры** (официальный API).
- **Фильтрация по релевантности:** скоринг по ключевым словам с весами (Data Quality, DWH, SQL, Python, Airflow, dbt, Greenplum и др.).
- **Хранение в PostgreSQL:** нормализованная схема, дедупликация по `hh_id` (для hh.ru) и `habr_id` (для Хабра).
- **ТОП-20 релевантных вакансий** — вывод в консоль с ссылками, компаниями и зарплатами.
- **Разделение ролей БД:** владелец (`postgres`) и пользователь приложения (`course` / `dwh_user`).
- **Обработка ошибок:** сетевые сбои, некорректные даты, дубликаты.

## Архитектура

```text
[hh.ru] (HTML)          [Хабр Карьера] (API)
    │                         │
    │ requests + BeautifulSoup│ requests
    ▼                         ▼
[job_agent.py]
  - fetch_vacancies()        (hh.ru)
  - fetch_habr_vacancies()   (Хабр)
  - save_vacancies()
  - filter_vacancies()
  - show_top_vacancies()
    │
    │ SQLAlchemy + psycopg2
    ▼
[PostgreSQL]
  vacancies
  filtered_vacancies
  applications
Стек технологий
Python 3.11+

```
requests — HTTP-запросы к hh.ru и Хабра

BeautifulSoup4 — парсинг HTML hh.ru

SQLAlchemy — ORM для работы с PostgreSQL

psycopg2 — драйвер PostgreSQL

python-dotenv — управление переменными окружения

PostgreSQL 17 — база данных

Как это работает
1. Сбор вакансий (fetch_vacancies / fetch_habr_vacancies)
hh.ru: Агент делает GET-запрос к hh.ru/search/vacancy с браузерным User-Agent. Внутри HTML-страницы в теге <template id="HH-Lux-InitialState"> лежит JSON с вакансиями. Мы извлекаем его и преобразуем в формат, похожий на ответ API.

Хабр Карьера: Агент обращается к публичному API https://career.habr.com/api/frontend/vacancies с параметрами q (поисковый запрос), remote=true (только удаленка) и page. Получает JSON-список вакансий.

2. Сохранение в БД (save_vacancies)
Каждая вакансия сохраняется в таблицу vacancies. Дубликаты отсекаются на уровне БД через ON CONFLICT (hh_id) DO NOTHING. Даты парсятся с учётом формата hh.ru ({"$date": "..."}) и Хабра.

3. Фильтрация (filter_vacancies)
Считается relevance_score — сумма весов найденных ключевых слов.
Актуальные веса (фокус на Data Quality и DWH):

data quality, качество данных → 10 баллов

great expectations, метаданные, каталог данных, data governance → 8 баллов

dwh, хранилище → 8 баллов

etl → 7 баллов

sql, python → 5 баллов

airflow, dbt, data vault → 6 баллов

Вакансии со скором ≥ 5 попадают в таблицу filtered_vacancies.

4. Вывод (show_top_vacancies)
ТОП-20 отфильтрованных вакансий выводится в консоль: название, компания, зарплата, релевантность, ссылка.

Установка и запуск
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
Параметры подключения к PostgreSQL и HH_USER_AGENT (обязательно с реальным email).

5. Создать таблицы в PostgreSQL
Выполни SQL из раздела Схема базы данных.

6. Запустить агента
bash
python job_agent.py
Схема базы данных
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
Таблица applications
sql
CREATE TABLE pavel_onichtchenko.applications (
    id SERIAL PRIMARY KEY,
    vacancy_id INT REFERENCES pavel_onichtchenko.vacancies(id),
    status VARCHAR(50) DEFAULT 'sent',
    notes TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vacancy_id)
);
Результаты работы
Пример вывода агента:

text
--- ИСТОЧНИК: HH.RU ---
🔎 HH: Ищу по запросу: 'Data Quality'
📄 Страница 1... Найдено 50.
📄 Страница 2... Найдено 2.

--- ИСТОЧНИК: ХАБР КАРЬЕРА ---
🔎 Хабр: Ищу по запросу: 'Data Quality'
  📄 Страница 1: Найдено 25
  📄 Страница 2: Найдено 25

📊 HH: Всего загружено: 486 вакансий
📊 Хабр: Всего загружено: 151 вакансия
💾 Сохранено новых: 637, пропущено: 0

🔍 Проверяю 637 новых вакансий...
✅ Отфильтровано (релевантных): 13
🚫 Отсеяно (мусор): 624

🏆 ТОП-15 СВЕЖИХ ВАКАНСИЙ (Data Quality / DWH / BI)
1. Аналитик DWH
   Компания: Джетлин
   Релевантность: 13
   Ссылка: https://career.habr.com/vacancies/1000167559
...
Структура репозитория
text
job-finder-agent/
├── README.md                # Этот файл
├── requirements.txt         # Зависимости Python
├── job_agent.py             # Основной код агента
├── .gitignore               # Что НЕ заливать в git
├── .env.example             # Шаблон переменных окружения
├── docs/
│   └── final_report.md      # Технический отчёт о проекте
└── data/                    # Папка для локальных данных
...

Планы по развитию
Telegram-уведомления о новых вакансиях (требует обхода блокировок).

Генерация сопроводительных писем через LLM (YandexGPT / OpenAI).

Дашборд на Plotly / Panel со статистикой поиска.

Расширение парсинга на другие площадки (Geekjob, LinkedIn).

Переход на официальный API при получении токена работодателя.

Автор
Онищенко Павел Владимирович

GitHub: @nconichtchenko-arch

Email: pavloni@mail.ru

Проект создан как инструмент для автоматизации поиска работы аналитиком данных. Использует только публично доступные данные hh.ru и открытый API Хабр Карьеры.
