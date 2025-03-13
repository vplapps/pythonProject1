import random
import time
import os
from datetime import datetime, timedelta
from undetected_chromedriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException
from auth import login_to_threads, load_cookies, save_cookies, generate_browser_fingerprint
from utils import log_scroll_to_end, idle_scroll
from warmup import smooth_scroll, get_current_scroll_position, get_page_height, is_element_in_viewport, human_like_scroll

# Глобальний словник для відстеження коментарів на день
daily_comments = {}

def close_comment_window(driver, log_text, login):
    """Закриває вікно коментування через ESC."""
    try:
        actions = ActionChains(driver)
        for attempt in range(3):
            actions.send_keys(Keys.ESCAPE).perform()
            log_text.insert("end", f"[{login}] Спроба {attempt + 1}/3: Натиснуто Escape для закриття вікна коментування\n")
            log_scroll_to_end(log_text)
            time.sleep(2)
            if not driver.find_elements(By.CSS_SELECTOR, "div[contenteditable='true'][role='textbox']"):
                log_text.insert("end", f"[{login}] Вікно коментування закрито\n")
                log_scroll_to_end(log_text)
                return True
        log_text.insert("end", f"[{login}] Не вдалося закрити вікно коментування після всіх спроб\n")
        log_scroll_to_end(log_text)
        with open(f"comment_error_{login}_{int(time.time())}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return False
    except WebDriverException as e:
        log_text.insert("end", f"[{login}] Помилка при закритті вікна коментування: {str(e)}\n")
        log_scroll_to_end(log_text)
        return False

def clean_text(text):
    """Очищає текст від невидимих символів."""
    if not text:
        return ""
    text = text.replace('\u200b', '').replace('\u00a0', ' ').replace('\n', '').replace('\r', '').replace('\t', '')
    return text.strip()

def comment_posts(account, stop_event, min_likes, max_likes, max_comments, max_comments_per_day, max_comments_per_post,
                  comments, intensity, photo_paths, log_text, show_browser, work_interval=60, pause_interval=60,
                  gui=None):
    """
    Функція для автоматичного коментування постів у Threads.
    """
    login = account["login"]
    comments_made = 0  # Initialize here to avoid UnboundLocalError

    # Перевірка типу log_text
    if not hasattr(log_text, 'insert') or not callable(log_text.insert):
        print(f"Помилка: log_text не є коректним об’єктом Tkinter Text для {login}. Передано: {type(log_text)}")
        return

    # Використання специфічного відбитка браузера для аккаунта, якщо надано
    fingerprint = account.get("fingerprint", None)
    if not fingerprint:
        fingerprint = generate_browser_fingerprint(login)
        account["fingerprint"] = fingerprint  # Зберігаємо, якщо його не було
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
    driver = None
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

        # Завантажуємо кукі, специфічні для аккаунта, якщо вони є
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
            time.sleep(0.5)
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

        reset_daily_comments(login)
        log_text.insert("end", f"[{login}] Лічильник коментарів на день: {daily_comments[login]['count']}/{max_comments_per_day}\n")
        log_scroll_to_end(log_text)

        if intensity <= 0 or intensity > 30:
            intensity = min(max(intensity, 1), 30)
            log_text.insert("end", f"[{login}] Інтенсивність скоригована до {intensity} коментів/год\n")
            log_scroll_to_end(log_text)
        base_delay = 3600 / intensity
        log_text.insert("end", f"[{login}] Базова затримка між коментарями: {base_delay:.2f} секунд\n")
        log_scroll_to_end(log_text)

        work_interval_seconds = work_interval * 60
        pause_interval_seconds = pause_interval * 60
        start_time = time.time()

        driver.get("https://www.threads.net/")
        time.sleep(2)

        for _ in range(5):
            if stop_event.is_set():
                log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                log_scroll_to_end(log_text)
                break
            human_like_scroll(driver, log_text, login, 1, 1, 0, 0, gui)

        while comments_made < max_comments:
            if stop_event.is_set():
                log_text.insert("end", f"[{login}] Зупинено користувачем\n")
                log_scroll_to_end(log_text)
                break

            reset_daily_comments(login)
            if daily_comments[login]["count"] >= max_comments_per_day:
                log_text.insert("end", f"[{login}] Досягнуто ліміт коментарів на день ({max_comments_per_day}). Завершуємо.\n")
                log_scroll_to_end(log_text)
                break

            elapsed_time = time.time() - start_time
            if elapsed_time >= work_interval_seconds:
                log_text.insert("end", f"[{login}] Час роботи ({work_interval} хвилин) минув, пауза на {pause_interval} хвилин\n")
                log_scroll_to_end(log_text)
                time.sleep(pause_interval_seconds)
                start_time = time.time()
                driver.get("https://www.threads.net/")
                time.sleep(2)

            try:
                # Оновлені селектори для кнопок коментування
                comment_buttons = driver.find_elements(By.CSS_SELECTOR,
                    "div[role='button'] svg[aria-label='Відповісти'], "
                    "div[role='button'] svg[aria-label='Ответить'], "
                    "div[role='button'] svg[aria-label='Comment'], "
                    "div[role='button'] svg[aria-label='Reply'], "
                    "div[role='button'] svg[aria-label='Ответ'], "
                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='відповісти'], "
                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='ответить'], "
                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='comment'], "
                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='reply'], "
                    "div[role='button'][class*='x1i10hfl'] svg[aria-label*='ответ']"
                )
                log_text.insert("end", f"[{login}] Знайдено {len(comment_buttons)} кнопок коментування\n")
                log_scroll_to_end(log_text)
                if not comment_buttons:
                    log_text.insert("end", f"[{login}] Жодна кнопка коментування не знайдена. Зберігаю сторінку: comment_error_{login}.html\n")
                    with open(f"comment_error_{login}_{int(time.time())}.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    human_like_scroll(driver, log_text, login, 1, 1, 0, 0, gui)
                    continue

                visible_comment_button = next((btn for btn in comment_buttons if is_element_in_viewport(driver, btn)), None)
                if visible_comment_button:
                    # Перевірка, чи кнопка коректно визначена
                    button_html_check = driver.execute_script("return arguments[0].outerHTML;", visible_comment_button)
                    log_text.insert("end", f"[{login}] HTML кнопки перед пошуком батьківського елемента: {button_html_check}\n")
                    log_scroll_to_end(log_text)

                    # Розширений пошук батьківського елемента поста
                    post_element = driver.execute_script("""
                        (button) => {
                            if (!button) return null;
                            let parent = button.closest('article');
                            if (!parent) parent = button.closest('div[role="article"]');
                            if (!parent) parent = button.closest('div[data-testid="post"]');
                            if (!parent) parent = button.closest('div[class*="x1y1aw1k"]');
                            if (!parent) parent = button.closest('div[class*="x1lliihq"]');
                            if (!parent) parent = button.closest('div[class*="x1n2onr6"]');
                            if (!parent) parent = button.closest('div[class*="x78zum5"]');
                            if (!parent) parent = button.closest('div[class*="x1i10hfl"]');
                            if (!parent) {
                                let current = button.parentElement;
                                for (let i = 0; i < 20 && current; i++) {
                                    if (current.tagName.toLowerCase() === 'div' && 
                                        (current.className.includes('x1y1aw1k') || 
                                         current.className.includes('x1lliihq') || 
                                         current.className.includes('x1n2onr6') || 
                                         current.className.includes('x78zum5') || 
                                         current.className.includes('x1i10hfl') || 
                                         current.className.includes('x1cy8zhl'))) {
                                        return current;
                                    }
                                    current = current.parentElement;
                                }
                            }
                            if (!parent) {
                                let current = button.parentElement;
                                for (let i = 0; i < 20 && current; i++) {
                                    if (current.tagName.toLowerCase() === 'div') {
                                        return current;
                                    }
                                    current = current.parentElement;
                                }
                            }
                            return parent || null;
                        }
                    """, visible_comment_button)
                    if not post_element:
                        log_text.insert("end", f"[{login}] Не вдалося знайти батьківський елемент поста. Зберігаю HTML кнопки та її батьків: button_error_{login}.html\n")
                        log_scroll_to_end(log_text)
                        try:
                            button_html = driver.execute_script("""
                                (button) => {
                                    if (!button) return "Помилка: кнопка не передана";
                                    let result = button.outerHTML;
                                    let current = button.parentElement;
                                    for (let i = 0; i < 10 && current; i++) {
                                        result = current.outerHTML + "\\n" + result;
                                        current = current.parentElement;
                                    }
                                    return result;
                                }
                            """, visible_comment_button)
                            if not button_html:
                                log_text.insert("end", f"[{login}] Помилка: button_html повернув порожній результат. Зберігаю всю сторінку.\n")
                                log_scroll_to_end(log_text)
                                button_html = driver.page_source
                            with open(f"button_error_{login}_{int(time.time())}.html", "w", encoding="utf-8") as f:
                                f.write(button_html)
                        except Exception as e:
                            log_text.insert("end", f"[{login}] Помилка при збереженні HTML кнопки: {str(e)}. Зберігаю всю сторінку.\n")
                            log_scroll_to_end(log_text)
                            with open(f"button_error_{login}_{int(time.time())}.html", "w", encoding="utf-8") as f:
                                f.write(driver.page_source)
                        log_text.insert("end", f"[{login}] Продовжуємо коментування, ігноруючи перевірку кількості коментарів\n")
                        log_scroll_to_end(log_text)
                        # Продовжуємо без перевірки кількості коментарів
                        comment_count = 0
                    else:
                        # Нова логіка: перевірка лайків і коментарів перед кліком
                        try:
                            # Отримання кількості лайків
                            likes_element = driver.execute_script("""
                                (post) => {
                                    const likesSpan = post.querySelector('div.x6s0dn4.x17zd0t2.x78zum5.xl56j7k span.x17qophe');
                                    return likesSpan ? likesSpan.textContent.match(/\\d+/)?.[0] || '0' : '0';
                                }
                            """, post_element)
                            likes = int(likes_element) if likes_element.isdigit() else 0
                            log_text.insert("end", f"[{login}] Кількість лайків у пості: {likes}\n")
                            log_scroll_to_end(log_text)

                            # Отримання кількості коментарів
                            comment_count_element = driver.execute_script("""
                                (post) => {
                                    const commentSpan = post.querySelector('div.x6s0dn4.x78zum5.xl56j7k.xezivpi span.x17qophe');
                                    return commentSpan ? commentSpan.textContent.match(/\\d+/)?.[0] || '0' : '0';
                                }
                            """, post_element)
                            comment_count = int(comment_count_element) if comment_count_element.isdigit() else 0
                            log_text.insert("end", f"[{login}] Кількість коментарів у пості: {comment_count}\n")
                            log_scroll_to_end(log_text)
                        except Exception as e:
                            likes = 0
                            comment_count = 0
                            log_text.insert("end", f"[{login}] Не вдалося визначити кількість лайків або коментарів: {str(e)}. Вважаємо 0.\n")
                            log_scroll_to_end(log_text)

                        # Перевірка умов перед кліком
                        if min_likes <= likes <= max_likes and comment_count < max_comments_per_post:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", visible_comment_button)
                            time.sleep(1)  # Додаткова затримка перед кліком
                            visible_comment_button.click()
                            log_text.insert("end", f"[{login}] Клікнуто на кнопку коментування (пост відповідає критеріям: лайки {likes}, коментарі {comment_count})\n")
                            log_scroll_to_end(log_text)
                        else:
                            if likes < min_likes or likes > max_likes:
                                log_text.insert("end", f"[{login}] Пропускаємо пост: кількість лайків ({likes}) не в межах {min_likes}-{max_likes}\n")
                                log_scroll_to_end(log_text)
                            if comment_count >= max_comments_per_post:
                                log_text.insert("end", f"[{login}] Пропускаємо пост: кількість коментарів ({comment_count}) перевищує ліміт ({max_comments_per_post})\n")
                                log_scroll_to_end(log_text)
                            close_comment_window(driver, log_text, login)
                            continue

                    # Решта коду (пошук поля коментування, введення тексту тощо)
                    retries = 5
                    comment_field = None
                    for attempt in range(retries):
                        time.sleep(3)
                        comment_field = driver.find_elements(By.CSS_SELECTOR,
                            "div[contenteditable='true'][role='textbox'], "
                            "div[contenteditable='true'][data-lexical-editor='true'], "
                            "div[role='textbox'][aria-placeholder*='Відповісти']")
                        if comment_field and is_element_in_viewport(driver, comment_field[0]):
                            comment_field = comment_field[0]
                            log_text.insert("end", f"[{login}] Поле для коментування знайдено\n")
                            log_scroll_to_end(log_text)
                            break
                        log_text.insert("end", f"[{login}] Поле для коментування не з'явилося (спроба {attempt + 1}/{retries}), чекаємо...\n")
                        log_scroll_to_end(log_text)

                    if not comment_field:
                        log_text.insert("end", f"[{login}] Поле для коментування не знайдено, закриваю вікно\n")
                        log_scroll_to_end(log_text)
                        close_comment_window(driver, log_text, login)
                        continue

                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", comment_field)
                    likes = random.randint(0, 200)
                    if min_likes <= likes <= max_likes:
                        try:
                            comment = random.choice(comments)
                            log_text.insert("end", f"[{login}] Вводжу текст: {comment}\n")
                            log_scroll_to_end(log_text)

                            # Очищаємо поле перед введенням
                            comment_field.click()
                            driver.execute_script("arguments[0].innerText = '';", comment_field)
                            time.sleep(1)

                            # Введення тексту
                            for char in comment:
                                comment_field.send_keys(char)
                                time.sleep(random.uniform(0.05, 0.15))  # Імітація людського набору
                            log_text.insert("end", f"[{login}] Текст введено: {comment}\n")
                            log_scroll_to_end(log_text)

                            # Перевірка шляхів до зображень
                            log_text.insert("end", f"[{login}] Перевірка наявності зображень: {photo_paths}\n")
                            log_scroll_to_end(log_text)
                            valid_photo_paths = []
                            for path in photo_paths:
                                if os.path.exists(path):
                                    valid_photo_paths.append(path)
                                else:
                                    log_text.insert("end", f"[{login}] Файл не знайдено: {path}, пропускаємо\n")
                                    log_scroll_to_end(log_text)

                            # Додавання зображень
                            if valid_photo_paths:
                                log_text.insert("end", f"[{login}] Додаю зображення (всього {len(valid_photo_paths)} файлів)...\n")
                                log_scroll_to_end(log_text)
                                try:
                                    file_input = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                                    if file_input and is_element_in_viewport(driver, file_input[0]):
                                        driver.execute_script("arguments[0].style.display = 'block'", file_input[0])
                                        file_input[0].send_keys('\n'.join(valid_photo_paths))
                                        log_text.insert("end", f"[{login}] Завантажено {len(valid_photo_paths)} зображень: {valid_photo_paths}\n")
                                        log_scroll_to_end(log_text)
                                        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='blob:']")))
                                        log_text.insert("end", f"[{login}] Усі зображення успішно додано\n")
                                        log_scroll_to_end(log_text)
                                    else:
                                        attach_media_button = driver.find_elements(By.CSS_SELECTOR, "div svg[aria-label='Прикріпити медіафайли']")
                                        if attach_media_button and is_element_in_viewport(driver, attach_media_button[0]):
                                            attach_media_button = attach_media_button[0]
                                            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", attach_media_button)
                                            attach_media_button.click()
                                            log_text.insert("end", f"[{login}] Клікнуто на кнопку 'Прикріпити медіафайли'\n")
                                            log_scroll_to_end(log_text)
                                            file_input = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']")))
                                            if file_input:
                                                driver.execute_script("arguments[0].style.display = 'block'", file_input)
                                                file_input.send_keys('\n'.join(valid_photo_paths))
                                                log_text.insert("end", f"[{login}] Завантажено {len(valid_photo_paths)} зображень: {valid_photo_paths}\n")
                                                log_scroll_to_end(log_text)
                                                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='blob:']")))
                                                log_text.insert("end", f"[{login}] Усі зображення успішно додано\n")
                                                log_scroll_to_end(log_text)
                                            else:
                                                log_text.insert("end", f"[{login}] Поле <input type='file'> не знайдено після кліку, відправляємо текст\n")
                                                log_scroll_to_end(log_text)
                                        else:
                                            log_text.insert("end", f"[{login}] Кнопка 'Прикріпити медіафайли' не знайдена, відправляємо текст\n")
                                            log_scroll_to_end(log_text)
                                            with open(f"media_attach_error_{login}_{int(time.time())}.html", "w", encoding="utf-8") as f:
                                                f.write(driver.page_source)
                                except TimeoutException as e:
                                    log_text.insert("end", f"[{login}] Таймаут при очікуванні <input type='file'> або прев'ю зображень: {str(e)}, відправляємо текст\n")
                                    log_scroll_to_end(log_text)
                                except Exception as e:
                                    log_text.insert("end", f"[{login}] Помилка при завантаженні зображень: {str(e)}, відправляємо текст\n")
                                    log_scroll_to_end(log_text)

                            # Відправлення коментаря
                            time.sleep(2)
                            comment_field.click()
                            actions = ActionChains(driver)
                            actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
                            log_text.insert("end", f"[{login}] Відправлено коментар через Ctrl + Enter\n")
                            log_scroll_to_end(log_text)

                            log_text.insert("end", f"[{login}] Коментар опубліковано: {comment} (Лайків: {likes})\n")
                            log_text.insert("end", f"[{login}] Виконано коментарів: {comments_made + 1}/{max_comments}\n")
                            log_scroll_to_end(log_text)
                            comments_made += 1
                            daily_comments[login]["count"] += 1
                            log_text.insert("end", f"[{login}] Лічильник коментарів на день: {daily_comments[login]['count']}/{max_comments_per_day}\n")
                            log_scroll_to_end(log_text)
                            if gui:
                                gui.update_comment_stats(login, comments_made)

                            # Рандомна затримка з імітацією скролінгу
                            delay_variation = random.uniform(0.8, 1.2)
                            random_delay = base_delay * delay_variation
                            log_text.insert("end", f"[{login}] Очікування {random_delay:.2f} секунд перед наступним коментарем...\n")
                            log_scroll_to_end(log_text)
                            idle_scroll(driver, log_text, login, random_delay)

                        except Exception as e:
                            log_text.insert("end", f"[{login}] Помилка під час коментування: {str(e)}\n")
                            log_scroll_to_end(log_text)
                            close_comment_window(driver, log_text, login)
                            continue

                    else:
                        log_text.insert("end", f"[{login}] Пост не відповідає критеріям (Лайків: {likes}, потрібні: {min_likes}-{max_likes})\n")
                        log_scroll_to_end(log_text)
                        close_comment_window(driver, log_text, login)

                else:
                    log_text.insert("end", f"[{login}] Не знайдено видимих кнопок коментування, скролимо\n")
                    log_scroll_to_end(log_text)

                if not human_like_scroll(driver, log_text, login, 1, 1, 0, 0, gui):
                    log_text.insert("end", f"[{login}] Помилка скролінгу, завершуємо\n")
                    log_scroll_to_end(log_text)
                    break

            except TimeoutException as e:
                log_text.insert("end", f"[{login}] Таймаут: {str(e)}\n")
                log_scroll_to_end(log_text)
                human_like_scroll(driver, log_text, login, 1, 1, 0, 0, gui)
            except Exception as e:
                log_text.insert("end", f"[{login}] Помилка: {str(e)}\n")
                log_scroll_to_end(log_text)
                break

    except Exception as e:
        log_text.insert("end", f"[{login}] Помилка: {str(e)}\n")
        log_scroll_to_end(log_text)
    finally:
        if driver is not None:
            save_cookies(driver, login, log_text)
            try:
                driver.service.stop()  # Explicitly stop the service
                driver.quit()
                log_text.insert("end", f"[{login}] Браузер закрито\n")
                log_scroll_to_end(log_text)
            except Exception as e:
                log_text.insert("end", f"[{login}] Помилка при закритті драйвера: {str(e)}\n")
                log_scroll_to_end(log_text)
            finally:
                driver = None  # Ensure driver is set to None to avoid further access
        log_text.insert("end", f"[{login}] Завершено. Коментарів у сесії: {comments_made}, за день: {daily_comments.get(login, {'count': 0})['count']}/{max_comments_per_day}\n")
        log_scroll_to_end(log_text)

def reset_daily_comments(login):
    """Скидає лічильник коментарів на день, якщо дата змінилася."""
    current_date = datetime.now().date()
    if login not in daily_comments or daily_comments[login]["last_reset"].date() != current_date:
        daily_comments[login] = {"count": 0, "last_reset": datetime.now()}
        return True
    return False

if __name__ == "__main__":
    import tkinter as tk
    import threading

    root = tk.Tk()
    log_text = tk.Text(root)
    log_text.pack()
    account = {"login": "test_user", "password": "test_pass", "proxy": None}
    stop_event = threading.Event()
    photo_paths = [
        "path/to/your/image1.jpg",
        "path/to/your/image2.jpg",
        "path/to/your/image3.jpg"
    ]
    comment_posts(account, stop_event, 10, 100, 5, 50, 10, ["Круто"], 5, photo_paths, log_text, True)
    root.mainloop()