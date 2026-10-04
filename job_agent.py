import os
import requests
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from bs4 import BeautifulSoup

# Загружаем переменные окружения
load_dotenv()

# === НАСТРОЙКИ ПОДКЛЮЧЕНИЯ К БД ===
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SCHEMA = os.getenv("DB_SCHEMA")

engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    connect_args={"options": f"-csearch_path={DB_SCHEMA}"}
)


def fetch_vacancies(pages=2):
    """
    Загружает вакансии с HTML-страницы поиска hh.ru (парсинг).
    pages: сколько страниц загрузить.
    """
    all_vacancies = []

    for page in range(pages):
        page_num = page + 1
        url = (
            f"https://hh.ru/search/vacancy"
            f"?text=аналитик+данных"
            f"&area=113"
            f"&schedule=remote"
            f"&page={page}"
            f"&per_page=100"
        )

        print(f"📄 Загружаю страницу {page_num} из {pages}...")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            response = requests.get(url, headers=headers, timeout=20)
        except requests.RequestException as e:
            print(f"❌ Сетевая ошибка: {e}")
            break

        if response.status_code != 200:
            print(f"❌ Ошибка запроса: {response.status_code}")
            print(response.text[:500])
            break

        soup = BeautifulSoup(response.text, "html.parser")

        template = soup.find("template", id="HH-Lux-InitialState")
        if not template:
            print("❌ Не удалось найти блок с данными вакансий на странице.")
            break

        try:
            data = json.loads(template.string)
        except Exception as e:
            print(f"❌ Ошибка разбора JSON: {e}")
            break

        vacancies_raw = data.get("vacancySearchResult", {}).get("vacancies", [])
        if not vacancies_raw:
            print("✅ Больше вакансий на странице нет.")
            break

        print(f"   Найдено {len(vacancies_raw)} вакансий на странице")

        for item in vacancies_raw:
            api_like = {
                "id": item.get("vacancyId"),
                "name": item.get("name"),
                "employer": {"name": item.get("company", {}).get("visibleName")},
                "salary": {
                    "from": item.get("compensation", {}).get("from"),
                    "to": item.get("compensation", {}).get("to"),
                    "currency": item.get("compensation", {}).get("currencyCode", "RUR"),
                },
                "area": {"name": item.get("area", {}).get("name")},
                "experience": {"name": item.get("workExperience")},
                "schedule": {"name": "Удаленная работа"},
                "snippet": {"requirement": item.get("snippet", {}).get("requirement", "")},
                "alternate_url": item.get("links", {}).get("desktop"),
                "published_at": item.get("publicationTime"),
            }
            all_vacancies.append(api_like)

        time.sleep(1.5)

    print(f"\n📊 Всего загружено: {len(all_vacancies)} вакансий")
    return all_vacancies


def save_vacancies(vacancies):
    """
    Сохраняет вакансии в БД. Пропускает дубликаты по hh_id.
    """
    saved = 0
    skipped = 0

    with engine.connect() as conn:
        for vac in vacancies:
            hh_id = vac.get("id")
            name = vac.get("name", "")
            employer = vac.get("employer", {}) or {}
            employer_name = employer.get("name", "")
            salary = vac.get("salary") or {}
            salary_from = salary.get("from")
            salary_to = salary.get("to")
            currency = salary.get("currency", "")
            area = vac.get("area", {}) or {}
            area_name = area.get("name", "")
            experience = vac.get("experience", {}) or {}
            experience_name = experience.get("name", "")
            schedule = vac.get("schedule", {}) or {}
            schedule_name = schedule.get("name", "")
            description = vac.get("snippet", {}).get("requirement", "") or ""
            url = vac.get("alternate_url", "")
            published_at = vac.get("published_at")

            # Парсим дату — в HTML-версии hh.ru дата приходит как словарь {"$date": "..."}
            if published_at:
                if isinstance(published_at, dict):
                    published_at = published_at.get("$date") or published_at.get("date")
                if isinstance(published_at, str):
                    try:
                        published_at = datetime.fromisoformat(
                            published_at.replace("Z", "+00:00")
                        )
                    except ValueError:
                        published_at = None
                else:
                    published_at = None

            try:
                conn.execute(text("""
                    INSERT INTO pavel_onichtchenko.vacancies
                    (hh_id, name, employer_name, salary_from, salary_to, currency,
                     area_name, experience, schedule, description, url, published_at)
                    VALUES
                    (:hh_id, :name, :employer_name, :salary_from, :salary_to, :currency,
                     :area_name, :experience, :schedule, :description, :url, :published_at)
                    ON CONFLICT (hh_id) DO NOTHING
                """), {
                    "hh_id": hh_id,
                    "name": name,
                    "employer_name": employer_name,
                    "salary_from": salary_from,
                    "salary_to": salary_to,
                    "currency": currency,
                    "area_name": area_name,
                    "experience": experience_name,
                    "schedule": schedule_name,
                    "description": description,
                    "url": url,
                    "published_at": published_at
                })
                saved += 1
            except Exception as e:
                skipped += 1
                print(f"⚠️ Пропуск {name}: {e}")

        conn.commit()

    print(f"💾 Сохранено новых: {saved}, пропущено: {skipped}")
    return saved


def filter_vacancies():
    """
    Фильтрует вакансии по ключевым словам и зарплате.
    Считает relevance_score.
    """
    # Ключевые слова для релевантности (чем больше совпадений, тем выше скор)
    # Веса увеличены, чтобы вакансии с "Аналитик" + "данных" набирали 7 баллов.
    keywords = {
        "sql": 5,
        "python": 5,
        "pandas": 4,
        "postgresql": 4,
        "power bi": 4,
        "tableau": 3,
        "excel": 3,
        "аналитик": 4,
        "данных": 3,
        "bi": 3,
        "дашборд": 3,
        "data": 3,
        "analyst": 3,
        "product": 2,
        "бизнес": 2,
        "отчет": 2,
    }

    with engine.connect() as conn:
        # Берём вакансии, которые ещё не в filtered_vacancies
        result = conn.execute(text("""
            SELECT v.id, v.name, v.description, v.salary_from, v.salary_to
            FROM pavel_onichtchenko.vacancies v
            LEFT JOIN pavel_onichtchenko.filtered_vacancies f ON v.id = f.vacancy_id
            WHERE f.id IS NULL
        """))

        rows = result.fetchall()
        print(f"\n🔍 Проверяю {len(rows)} новых вакансий...")

        filtered_count = 0

        for row in rows:
            vac_id = row[0]
            name = (row[1] or "").lower()
            description = (row[2] or "").lower()
            salary_from = row[3] or 0

            text_content = f"{name} {description}"

            # Считаем скор
            score = 0
            matched_keywords = []

            for keyword, weight in keywords.items():
                if keyword in text_content:
                    score += weight
                    matched_keywords.append(keyword)

            # Пока не отсекаем по зарплате — слишком мало вакансий с указанной вилкой
            # if salary_from and salary_from < 80000:
            #     continue

            # Минимальный порог релевантности
            if score < 5:
                continue

            # Сохраняем
            reason = f"Ключевые слова: {', '.join(matched_keywords)}"
            conn.execute(text("""
                INSERT INTO pavel_onichtchenko.filtered_vacancies
                (vacancy_id, relevance_score, match_reason)
                VALUES (:vac_id, :score, :reason)
                ON CONFLICT (vacancy_id) DO NOTHING
            """), {
                "vac_id": vac_id,
                "score": score,
                "reason": reason
            })
            filtered_count += 1

        conn.commit()

    print(f"✅ Отфильтровано: {filtered_count} релевантных вакансий")
    return filtered_count


def show_top_vacancies(limit=10):
    """
    Показывает топ отфильтрованных вакансий.
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT v.name, v.employer_name, v.salary_from, v.salary_to,
                   f.relevance_score, v.url
            FROM pavel_onichtchenko.filtered_vacancies f
            JOIN pavel_onichtchenko.vacancies v ON f.vacancy_id = v.id
            ORDER BY f.relevance_score DESC, v.published_at DESC NULLS LAST
            LIMIT :limit
        """), {"limit": limit})

        rows = result.fetchall()

    print("\n" + "=" * 80)
    print(f"🏆 ТОП-{limit} РЕЛЕВАНТНЫХ ВАКАНСИЙ")
    print("=" * 80)

    for i, row in enumerate(rows, 1):
        name, employer, sal_from, sal_to, score, url = row

        salary_str = ""
        if sal_from and sal_to:
            salary_str = f"{sal_from} - {sal_to} руб."
        elif sal_from:
            salary_str = f"от {sal_from} руб."
        elif sal_to:
            salary_str = f"до {sal_to} руб."
        else:
            salary_str = "зарплата не указана"

        print(f"\n{i}. {name}")
        print(f"   Компания: {employer}")
        print(f"   Зарплата: {salary_str}")
        print(f"   Релевантность: {score}")
        print(f"   Ссылка: {url}")


if __name__ == "__main__":
    print("Запуск агента поиска вакансий\n")

    # 1. Загружаем вакансии
    vacancies = fetch_vacancies(pages=2)

    # 2. Сохраняем в БД
    save_vacancies(vacancies)

    # 3. Фильтруем
    filter_vacancies()

    # 4. Показываем топ
    show_top_vacancies(limit=10)

    print("\nГотово!")