import random
import time
import json
from undetected_chromedriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from auth import login_to_threads, load_cookies, save_cookies, generate_browser_fingerprint
from utils import log_scroll_to_end

def smooth_scroll(driver, distance, duration):
    """Плавно скролить сторінку на задану відстань протягом заданого часу."""
    steps = 20
    step_distance = distance / steps
    step_duration = int(duration / steps * 1000)
    driver.execute_script(f"""
    let totalHeight = 0;
    let distance = {step_distance};
    let timer = setInterval(() => {{
        window.scrollBy(0, distance);
        totalHeight += distance;
        if (totalHeight >= {distance}) clearInterval(timer);
    }}, {step_duration});
    """)
    time.sleep(duration)

def get_current_scroll_position(driver):
    """Отримує поточну позицію скролінгу сторінки."""
    return driver.execute_script("return window.scrollY")

def get_page_height(driver):
    """Отримує повну висоту сторінки."""
    return driver.execute_script("return document.body.scrollHeight")

def is_element_in_viewport(driver, element):
    """Перевіряє, чи елемент видимий у поточній видимій області (viewport)."""
    return driver.execute_script("""
    const rect = arguments[0].getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
    """, element)

def save_stats(data, filename="bot_data.json"):
    """Зберігає статистику в файл."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def human_like_scroll(driver, log_text, login, day, days, posts_viewed, likes_made, gui, stop_event, pause_event):
    """Імітує людську поведінку при скролінгу."""
    try:
        if stop_event.is_set():
            return False

        current_position = get_current_scroll_position(driver)
        page_height = get_page_height(driver)
        log_text.insert("end", f"[{login}] Поточна позиція скролінгу: {current_position}, висота сторінки: {page_height}\n")
        log_scroll_to_end(log_text)

        scroll_speed = random.choice(["fast", "medium", "slow"])
        if scroll_speed == "fast":
            scroll_duration = random.uniform(0.3, 0.8)
        elif scroll_speed == "medium":
            scroll_duration = random.uniform(0.8, 1.5)
        else:  # slow
            scroll_duration = random.uniform(1.5, 2.5)

        scroll_distance = random.randint(200, 800)

        scroll_direction = random.choices(["down", "up"], weights=[0.8, 0.2], k=1)[0]

        if scroll_direction == "up":
            scroll_distance = -random.randint(300, 1000)
            log_text.insert("end", f"[{login}] Скорочуємо вгору на {abs(scroll_distance)} пікселів (швидкість: {scroll_speed})...\n")
        else:
            log_text.insert("end", f"[{login}] Гортаємо вниз на {scroll_distance} пікселів (швидкість: {scroll_speed})...\n")

        smooth_scroll(driver, scroll_distance, scroll_duration)

        if random.random() < 0.5:
            pause_time = random.uniform(1, 5)
            log_text.insert("end", f"[{login}] Пауза на {pause_time:.1f} секунд (імітація перегляду)...\n")
            time.sleep(pause_time)

        if random.random() < 0.1:
            quick_scroll_distance = random.randint(1000, 2000)
            log_text.insert("end", f"[{login}] Швидкий скрол вниз на {quick_scroll_distance} пікселів (пропуск контенту)...\n")
            smooth_scroll(driver, quick_scroll_distance, random.uniform(0.5, 1.0))

        new_position = get_current_scroll_position(driver)
        if new_position <= current_position and scroll_direction == "down":
            log_text.insert("end", f"[{login}] Сторінка скинула скролінг! Поточна позиція: {new_position}\n")
            smooth_scroll(driver, scroll_distance // 2, scroll_duration / 2)
            time.sleep(2)

        gui.root.after(0, lambda: gui.update_stats(login, day, days, posts_viewed, likes_made))
        return True
    except Exception as e:
        log_text.insert("end", f"[{login}] Помилка скролінгу: {str(e)}\n")
        log_scroll_to_end(log_text)
        return False

def warmup_account(account, stop_event, pause_event, scroll_min, scroll_max, like_prob, days, log_text, show_browser, gui, work_interval=60, pause_interval=60):
    """Виконує прогрів акаунта з імітацією людської поведінки."""
    login = account["login"]
    driver = None
    driver_closed = False

    fingerprint = account.get("fingerprint", None)
    if not fingerprint:
        fingerprint = generate_browser_fingerprint(login)
        account["fingerprint"] = fingerprint
        log_text.insert("end", f"[{login}] Згенеровано новий відбиток браузера: {fingerprint}\n")
        log_scroll_to_end(log_text)
    else:
        log_text.insert("end", f"[{login}] Використано існуючий відбиток браузера: {fingerprint}\n")
        log_scroll_to_end(log_text)

    options = ChromeOptions()
    options.add_argument(f"--user-agent={fingerprint['user_agent']}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    if account.get("proxy"):
        options.add_argument(f"--proxy-server={account['proxy']}")
    try:
        driver = Chrome(options=options, headless=not show_browser)
        driver.set_window_size(fingerprint["viewport"]["width"], fingerprint["viewport"]["height"])

        driver.execute_script(f"""
            Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});
            Object.defineProperty(navigator, 'languages', {{ get: () => {fingerprint['languages']} }});
            Object.defineProperty(navigator, 'platform', {{ get: () => '{fingerprint['platform']}' }});
        """)

        driver.get("https://www.threads.net/")
        time.sleep(2)

        log_text.insert("end", f"[{login}] Перевірка наявності кукі...\n")
        log_scroll_to_end(log_text)

        cookies = account.get("cookies", None)
        if cookies and isinstance(cookies, list):
            for cookie in cookies:
                required_keys = {'name', 'value'}
                if not all(key in cookie for key in required_keys):
                    log_text.insert("end", f"[{login}] Помилка: кукі {cookie.get('name', 'невідомо')} не містить необхідних ключів\n")
                    log_scroll_to_end(log_text)
                    continue
                driver.add_cookie({
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie.get('domain', '.threads.net'),
                    'path': cookie.get('path', '/')
                })
            driver.refresh()
            time.sleep(0.5)
            log_text.insert("end", f"[{login}] Кукі завантажено з аккаунта\n")
            log_scroll_to_end(log_text)
        elif load_cookies(driver, login, log_text):
            driver.get("https://www.threads.net/")
            time.sleep(2)
            if "threads.net" in driver.current_url and "login" not in driver.current_url:
                log_text.insert("end", f"[{login}] Сесія завантажена, пропускаємо логін\n")
                log_scroll_to_end(log_text)
            else:
                log_text.insert("end", f"[{login}] Сесія недійсна, виконуємо логін...\n")
                log_scroll_to_end(log_text)
                if not login_to_threads(driver, account, log_text):
                    raise Exception("Помилка логіну")
        else:
            if not login_to_threads(driver, account, log_text):
                raise Exception("Помилка логіну")

        work_interval_seconds = work_interval * 60
        pause_interval_seconds = pause_interval * 60
        day_seconds = 24 * 60 * 60
        cycle_duration = work_interval + pause_interval
        cycles_per_day = max(1, (24 * 60) // cycle_duration)

        posts_viewed = account["warmup_stats"]["posts_viewed"]
        likes_made = account["warmup_stats"]["likes_made"]
        current_day = account["warmup_stats"]["days_completed"] + 1

        for login_key, (thread, stop_event_val, pause_event_val, task_type, _) in list(gui.running_threads.items()):
            if login_key == login:
                gui.running_threads[login_key] = (thread, stop_event, pause_event, task_type, driver)
                break

        for day in range(current_day - 1, days):
            if stop_event.is_set():
                log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                log_scroll_to_end(log_text)
                break

            # Перевірка паузи перед початком дня
            if pause_event.is_set():
                log_text.insert("end", f"[{login}] Прогрів на паузі, чекаємо відновлення...\n")
                log_scroll_to_end(log_text)
                while pause_event.is_set():
                    time.sleep(0.1)  # Невелика затримка для уникнення зависань
                    if stop_event.is_set():
                        log_text.insert("end", f"[{login}] Зупинено користувачем під час паузи\n")
                        log_scroll_to_end(log_text)
                        break
                log_text.insert("end", f"[{login}] Прогрів відновлено, продовжуємо...\n")
                log_scroll_to_end(log_text)

            if driver_closed:
                log_text.insert("end", f"[{login}] Браузер закрито, зупиняємо прогрів\n")
                log_scroll_to_end(log_text)
                break

            total_scrolls = random.randint(scroll_min, scroll_max)
            scrolls_per_cycle = max(1, total_scrolls // cycles_per_day)
            log_text.insert("end", f"[{login}] День {day + 1}: Загалом {total_scrolls} тредів, {scrolls_per_cycle} тредів на цикл, {cycles_per_day} циклів\n")
            log_scroll_to_end(log_text)

            if stop_event.is_set():
                log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                log_scroll_to_end(log_text)
                break

            if driver_closed:
                log_text.insert("end", f"[{login}] Браузер закрито, зупиняємо прогрів\n")
                log_scroll_to_end(log_text)
                break

            driver.get("https://www.threads.net/")
            time.sleep(2)

            for _ in range(5):
                if stop_event.is_set():
                    log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                    log_scroll_to_end(log_text)
                    break

                if pause_event.is_set():
                    log_text.insert("end", f"[{login}] Прогрів на паузі, чекаємо відновлення...\n")
                    log_scroll_to_end(log_text)
                    while pause_event.is_set():
                        time.sleep(0.1)  # Невелика затримка для уникнення зависань
                        if stop_event.is_set():
                            log_text.insert("end", f"[{login}] Зупинено користувачем під час паузи\n")
                            log_scroll_to_end(log_text)
                            break
                    log_text.insert("end", f"[{login}] Прогрів відновлено, продовжуємо...\n")
                    log_scroll_to_end(log_text)

                if driver_closed:
                    log_text.insert("end", f"[{login}] Браузер закрито, зупиняємо прогрів\n")
                    log_scroll_to_end(log_text)
                    break

                if not human_like_scroll(driver, log_text, login, day + 1, days, posts_viewed, likes_made, gui, stop_event, pause_event):
                    break
                posts_viewed += 1
                # Оновлюємо статистику після кожного перегляду поста
                for acc in gui.data["accounts"]:
                    if acc["login"] == login:
                        acc["warmup_stats"]["posts_viewed"] = posts_viewed
                        break
                save_stats(gui.data)
                gui.root.after(0, lambda: gui.update_stats(login, day + 1, days, posts_viewed, likes_made))

            if stop_event.is_set():
                log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                log_scroll_to_end(log_text)
                break

            if driver_closed:
                log_text.insert("end", f"[{login}] Браузер закрито, зупиняємо прогрів\n")
                log_scroll_to_end(log_text)
                break

            try:
                post_elements = driver.find_elements(By.CSS_SELECTOR,
                    "div[role='button'] svg[aria-label*='Like'], "
                    "div[role='button'] svg[aria-label*='Нравится'], "
                    "div[role='button'] svg[aria-label*='Подобається'], "
                    "div[role='button'] svg[aria-label*='Unlike'], "
                    "div[role='button'] svg[aria-label*='Не нравится'], "
                    "div[role='button'] svg[aria-label*='Не подобається']")
                log_text.insert("end", f"[{login}] Знайдено {len(post_elements)} потенційних постів у DOM\n")
                log_scroll_to_end(log_text)
            except Exception as e:
                log_text.insert("end", f"[{login}] Помилка при пошуку потенційних постів: {str(e)}\n")
                log_scroll_to_end(log_text)
                break

            try:
                driver.find_element(By.CSS_SELECTOR,
                    "div[role='button'] svg[aria-label*='Like'], "
                    "div[role='button'] svg[aria-label*='Нравится'], "
                    "div[role='button'] svg[aria-label*='Подобається']")
                log_text.insert("end", f"[{login}] Пости завантажені, починаємо скролінг\n")
                log_scroll_to_end(log_text)
            except:
                log_text.insert("end", f"[{login}] Помилка завантаження постів, збережено: timeout_error_{login}.html\n")
                log_scroll_to_end(log_text)
                with open(f"timeout_error_{login}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source if not driver_closed else "")
                break

            day_start_time = time.time()
            cycle_count = 0

            while time.time() - day_start_time < day_seconds and cycle_count < cycles_per_day:
                if stop_event.is_set():
                    log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                    log_scroll_to_end(log_text)
                    break

                if pause_event.is_set():
                    log_text.insert("end", f"[{login}] Прогрів на паузі, чекаємо відновлення...\n")
                    log_scroll_to_end(log_text)
                    while pause_event.is_set():
                        time.sleep(0.1)  # Невелика затримка для уникнення зависань
                        if stop_event.is_set():
                            log_text.insert("end", f"[{login}] Зупинено користувачем під час паузи\n")
                            log_scroll_to_end(log_text)
                            break
                    log_text.insert("end", f"[{login}] Прогрів відновлено, продовжуємо цикл\n")
                    log_scroll_to_end(log_text)

                if driver_closed:
                    log_text.insert("end", f"[{login}] Браузер закрито, зупиняємо прогрів\n")
                    log_scroll_to_end(log_text)
                    break

                log_text.insert("end", f"[{login}] День {day + 1}, цикл {cycle_count + 1}/{cycles_per_day}: Гортаємо {scrolls_per_cycle} тредів\n")
                log_scroll_to_end(log_text)

                for _ in range(scrolls_per_cycle):
                    if stop_event.is_set():
                        log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                        log_scroll_to_end(log_text)
                        break

                    if pause_event.is_set():
                        log_text.insert("end", f"[{login}] Прогрів на паузі, чекаємо відновлення...\n")
                        log_scroll_to_end(log_text)
                        while pause_event.is_set():
                            time.sleep(0.1)  # Невелика затримка для уникнення зависань
                            if stop_event.is_set():
                                log_text.insert("end", f"[{login}] Зупинено користувачем під час паузи\n")
                                log_scroll_to_end(log_text)
                                break
                        log_text.insert("end", f"[{login}] Прогрів відновлено, продовжуємо...\n")
                        log_scroll_to_end(log_text)

                    if driver_closed:
                        log_text.insert("end", f"[{login}] Браузер закрито, зупиняємо прогрів\n")
                        log_scroll_to_end(log_text)
                        break

                    if not human_like_scroll(driver, log_text, login, day + 1, days, posts_viewed, likes_made, gui, stop_event, pause_event):
                        log_text.insert("end", f"[{login}] Помилка скролінгу, перериваємо цикл\n")
                        log_scroll_to_end(log_text)
                        break

                    posts_viewed += 1
                    # Оновлюємо статистику після кожного перегляду поста
                    for acc in gui.data["accounts"]:
                        if acc["login"] == login:
                            acc["warmup_stats"]["posts_viewed"] = posts_viewed
                            break
                    save_stats(gui.data)
                    gui.root.after(0, lambda: gui.update_stats(login, day + 1, days, posts_viewed, likes_made))

                    if random.random() < like_prob:
                        retries = 3
                        for attempt in range(retries):
                            try:
                                time.sleep(2)
                                like_buttons = driver.find_elements(By.CSS_SELECTOR,
                                    "div[role='button'] svg[aria-label*='Like'], "
                                    "div[role='button'] svg[aria-label*='Нравится'], "
                                    "div[role='button'] svg[aria-label*='Подобається'], "
                                    "div[role='button'] svg[aria-label*='Unlike'], "
                                    "div[role='button'] svg[aria-label*='Не нравится'], "
                                    "div[role='button'] svg[aria-label*='Не подобається'], "
                                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='like'], "
                                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='нравится'], "
                                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='подобається'], "
                                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='unlike'], "
                                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='не нравится'], "
                                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='не подобається']"
                                )
                                log_text.insert("end", f"[{login}] Знайдено {len(like_buttons)} кнопок лайка в DOM\n")
                                log_scroll_to_end(log_text)

                                if not like_buttons:
                                    log_text.insert("end", f"[{login}] Жодна кнопка лайка не знайдена. Зберігаю сторінку: like_error_{login}.html\n")
                                    log_scroll_to_end(log_text)
                                    with open(f"like_error_{login}.html", "w", encoding="utf-8") as f:
                                        f.write(driver.page_source if not driver_closed else "")
                                    break

                                like_button = next((btn for btn in like_buttons if is_element_in_viewport(driver, btn)), None)

                                if like_button:
                                    aria_label = like_button.get_attribute("aria-label").lower()
                                    log_text.insert("end", f"[{login}] Знайдено видиму кнопку з aria-label: {aria_label}\n")
                                    log_scroll_to_end(log_text)

                                    if "like" in aria_label or "нравится" in aria_label or "подобається" in aria_label:
                                        like_button.click()
                                        likes_made += 1
                                        log_text.insert("end", f"[{login}] Поставлено лайк\n")
                                        log_scroll_to_end(log_text)
                                        # Оновлюємо статистику після кожного лайка
                                        for acc in gui.data["accounts"]:
                                            if acc["login"] == login:
                                                acc["warmup_stats"]["likes_made"] = likes_made
                                                break
                                        save_stats(gui.data)
                                        gui.root.after(0, lambda: gui.update_stats(login, day + 1, days, posts_viewed, likes_made))
                                        break
                                    elif "unlike" in aria_label or "не нравится" in aria_label or "не подобається" in aria_label:
                                        log_text.insert("end", f"[{login}] Пост уже лайкнутий (aria-label={aria_label})\n")
                                        log_scroll_to_end(log_text)
                                        break
                                    else:
                                        log_text.insert("end", f"[{login}] Невідомий стан кнопки лайка (aria-label={aria_label})\n")
                                        log_scroll_to_end(log_text)
                                        break
                                else:
                                    log_text.insert("end", f"[{login}] Не знайдено видимих кнопок лайка у viewport\n")
                                    log_scroll_to_end(log_text)
                                    break
                            except Exception as e:
                                log_text.insert("end", f"[{login}] Помилка при спробі лайка (спроба {attempt + 1}/{retries}): {str(e)}\n")
                                log_scroll_to_end(log_text)
                                if attempt == retries - 1:
                                    log_text.insert("end", f"[{login}] Кнопка лайка не знайдена після всіх спроб. Зберігаю сторінку: like_error_{login}.html\n")
                                    log_scroll_to_end(log_text)
                                    with open(f"like_error_{login}.html", "w", encoding="utf-8") as f:
                                        f.write(driver.page_source if not driver_closed else "")
                                continue
                        time.sleep(random.uniform(2, 5))

                if stop_event.is_set():
                    log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                    log_scroll_to_end(log_text)
                    break

                if driver_closed:
                    log_text.insert("end", f"[{login}] Браузер закрито, зупиняємо прогрів\n")
                    log_scroll_to_end(log_text)
                    break

                log_text.insert("end", f"[{login}] Пауза на {pause_interval} хвилин\n")
                log_scroll_to_end(log_text)
                sleep_start = time.time()
                while time.time() - sleep_start < pause_interval_seconds:
                    if stop_event.is_set():
                        log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                        log_scroll_to_end(log_text)
                        break
                    if pause_event.is_set():
                        log_text.insert("end", f"[{login}] Прогрів на паузі під час перерви, чекаємо...\n")
                        log_scroll_to_end(log_text)
                        while pause_event.is_set():
                            time.sleep(0.1)  # Невелика затримка для уникнення зависань
                            if stop_event.is_set():
                                log_text.insert("end", f"[{login}] Зупинено користувачем під час паузи\n")
                                log_scroll_to_end(log_text)
                                break
                        log_text.insert("end", f"[{login}] Відновлено після паузи під час перерви\n")
                        log_scroll_to_end(log_text)
                    time.sleep(1)
                cycle_count += 1

                if stop_event.is_set():
                    log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                    log_scroll_to_end(log_text)
                    break

                if driver_closed:
                    log_text.insert("end", f"[{login}] Браузер закрито, зупиняємо прогрів\n")
                    log_scroll_to_end(log_text)
                    break

                driver.get("https://www.threads.net/")
                time.sleep(2)

            elapsed_day_time = time.time() - day_start_time
            if day < days - 1 and not stop_event.is_set() and not driver_closed:
                remaining_time = day_seconds - elapsed_day_time
                if remaining_time > 0:
                    log_text.insert("end", f"[{login}] Очікування до наступного дня ({remaining_time/60:.1f} хвилин)...\n")
                    log_scroll_to_end(log_text)
                    sleep_start = time.time()
                    while time.time() - sleep_start < remaining_time:
                        if stop_event.is_set():
                            log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                            log_scroll_to_end(log_text)
                            break
                        if pause_event.is_set():
                            log_text.insert("end", f"[{login}] Прогрів на паузі під час очікування дня, чекаємо...\n")
                            log_scroll_to_end(log_text)
                            while pause_event.is_set():
                                time.sleep(0.1)  # Невелика затримка для уникнення зависань
                                if stop_event.is_set():
                                    log_text.insert("end", f"[{login}] Зупинено користувачем під час паузи\n")
                                    log_scroll_to_end(log_text)
                                    break
                            log_text.insert("end", f"[{login}] Відновлено після паузи під час очікування дня\n")
                            log_scroll_to_end(log_text)
                        time.sleep(1)

            current_day = day + 1
            # Оновлюємо статистику після кожного дня
            for acc in gui.data["accounts"]:
                if acc["login"] == login:
                    acc["warmup_stats"]["posts_viewed"] = posts_viewed
                    acc["warmup_stats"]["likes_made"] = likes_made
                    acc["warmup_stats"]["days_completed"] = current_day - 1
                    break
            save_stats(gui.data)

    except Exception as e:
        log_text.insert("end", f"[{login}] Помилка прогріву: {str(e)}\n")
        log_scroll_to_end(log_text)
    finally:
        if driver is not None and not driver_closed:
            save_cookies(driver, login, log_text)
            try:
                driver.quit()
                driver_closed = True
                log_text.insert("end", f"[{login}] Браузер закрито.\n")
                log_scroll_to_end(log_text)
            except Exception as e:
                log_text.insert("end", f"[{login}] Помилка при закритті драйвера: {str(e)}\n")
                log_scroll_to_end(log_text)
        # Зберігаємо статистику при завершенні
        for acc in gui.data["accounts"]:
            if acc["login"] == login:
                acc["warmup_stats"]["posts_viewed"] = posts_viewed
                acc["warmup_stats"]["likes_made"] = likes_made
                acc["warmup_stats"]["days_completed"] = current_day - 1
                break
        save_stats(gui.data)
        log_text.insert("end", f"[{login}] Прогрів завершено. Переглянуто {posts_viewed} постів, лайків: {likes_made}\n")
        log_scroll_to_end(log_text)
        gui.root.after(0, lambda: gui.update_stats(login, current_day, days, posts_viewed, likes_made))
        for acc in gui.data["accounts"]:
            if acc["login"] == login:
                acc["status"] = "Готовий"
                break
        gui.update_warmup_accounts()