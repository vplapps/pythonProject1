import threading
import time
import os
import pickle
import random
from undetected_chromedriver import Chrome, ChromeOptions
from fake_useragent import UserAgent
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from utils import get_2fa_code, log_scroll_to_end

# Ініціалізація UserAgent
ua = UserAgent()

# Розширені списки для генерації відбитків браузера
VIEWPORT_SIZES = [
    {"width": 1024, "height": 768},
    {"width": 1280, "height": 720},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1600, "height": 900},
    {"width": 1920, "height": 1080},
    {"width": 2560, "height": 1440},
    {"width": 800, "height": 600},
]

LANGUAGES = [
    ["en-US", "en"],
    ["ru-RU", "ru"],
    ["uk-UA", "uk"],
    ["es-ES", "es"],
    ["fr-FR", "fr"],
    ["de-DE", "de"],
    ["it-IT", "it"],
    ["pt-PT", "pt"],
]

PLATFORMS = [
    "Win32",
    "MacIntel",
    "Linux x86_64",
    "Win64",
    "iPhone",
    "iPad",
]


def terminate_chrome_processes():
    """Примусове завершення всіх процесів Chrome."""
    try:
        os.system("taskkill /F /IM chrome.exe /T")
        print("Усі процеси Chrome примусово завершено")
    except Exception as e:
        print(f"Помилка при завершенні процесів Chrome: {str(e)}")


def generate_browser_fingerprint(login):
    """Генерує унікальний відбиток браузера для кожного логіну."""
    seed = hash(login + str(time.time())) % 1000
    random.seed(seed)
    user_agent = ua.random
    viewport = random.choice(VIEWPORT_SIZES)
    languages = random.sample(LANGUAGES, k=random.randint(1, 3))
    platform = random.choice(PLATFORMS)
    timezone_offset = random.randint(-12, 14) * 60
    return {
        "user_agent": user_agent,
        "viewport": viewport,
        "languages": languages,
        "platform": platform,
        "timezone_offset": timezone_offset
    }


def update_fingerprint(driver, fingerprint, log_text, login):
    """Оновлює відбиток браузера під час сесії."""
    new_fingerprint = generate_browser_fingerprint(login)
    driver.execute_script(f"""
        Object.defineProperty(navigator, 'userAgent', {{ get: () => '{new_fingerprint["user_agent"]}' }});
        Object.defineProperty(navigator, 'languages', {{ get: () => {new_fingerprint["languages"]} }});
        Object.defineProperty(navigator, 'platform', {{ get: () => '{new_fingerprint["platform"]}' }});
        Object.defineProperty(navigator, 'timezone', {{ get: () => {new_fingerprint["timezone_offset"]} }});
    """)
    driver.set_window_size(new_fingerprint["viewport"]["width"], new_fingerprint["viewport"]["height"])
    log_text.insert("end", f"[{login}] Оновлено відбиток браузера\n")
    log_scroll_to_end(log_text)
    return new_fingerprint


def accept_cookies(driver, log_text, login):
    """Обробка сповіщення про файли cookie."""
    try:
        cookie_button = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Дозволити всі файли cookie')]"))
        )
        cookie_button.click()
        log_text.insert("end", f"[{login}] Файли cookie прийняті\n")
        log_scroll_to_end(log_text)
        time.sleep(0.1)
    except TimeoutException:
        log_text.insert("end", f"[{login}] Сповіщення про файли cookie не знайдено, пропускаємо\n")
        log_scroll_to_end(log_text)


def simulate_human_typing(driver, selector, text, log_text, login, delay_range=(0.05, 0.1), timeout=3, max_retries=3):
    """Імітація ручного введення тексту з використанням ActionChains."""
    actions = ActionChains(driver)
    for attempt in range(max_retries):
        try:
            element = None
            for _ in range(3):
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and isinstance(elements[0], WebElement):
                    element = elements[0]
                    break
                time.sleep(0.2)
            if not element:
                raise NoSuchElementException(f"Елемент за селектором {selector} не знайдено")

            log_text.insert("end", f"[{login}] Знайдено елемент для {selector}: {type(element)}\n")
            log_scroll_to_end(log_text)

            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", element)
            time.sleep(0.1)

            actions.move_to_element(element).click().perform()
            log_text.insert("end", f"[{login}] Клік по елементу {selector}\n")
            log_scroll_to_end(log_text)
            time.sleep(0.1)

            element.clear()
            log_text.insert("end", f"[{login}] Поле {selector} очищене\n")
            log_scroll_to_end(log_text)
            time.sleep(0.1)

            for char in text:
                actions.send_keys(char).pause(random.uniform(*delay_range)).perform()
                if random.random() < 0.1:
                    actions.send_keys('\b').pause(0.05).send_keys(char).perform()
                time.sleep(0.01)

            current_value = element.get_attribute("value") if hasattr(element, "get_attribute") else ""
            log_text.insert("end", f"[{login}] Введене значення в {selector}: {current_value}\n")
            log_scroll_to_end(log_text)

            if current_value != text:
                log_text.insert("end", f"[{login}] Попередження: введене значення не відповідає очікуваному: {text}\n")
                log_scroll_to_end(log_text)
            else:
                log_text.insert("end", f"[{login}] Текст успішно введено в {selector}: {text}\n")
                log_scroll_to_end(log_text)
                return True

        except (TimeoutException, NoSuchElementException) as e:
            log_text.insert("end",
                            f"[{login}] Помилка введення в {selector} (спроба {attempt + 1}/{max_retries}): {str(e)}\n")
            log_scroll_to_end(log_text)
            with open(f"typing_error_{login}_{selector.replace(' ', '_')}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            return False
        except Exception as e:
            log_text.insert("end",
                            f"[{login}] Неочікувана помилка в {selector} (спроба {attempt + 1}/{max_retries}): {str(e)}\n")
            log_scroll_to_end(log_text)
            with open(f"typing_error_{login}_{selector.replace(' ', '_')}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            return False
    return False


def save_cookies(driver, login, log_text):
    """Збереження кукі в файл."""
    try:
        cookies = driver.get_cookies()
        cookies_file = f"cookies_{login}.pkl"
        with open(cookies_file, "wb") as f:
            pickle.dump(cookies, f)
        log_text.insert("end", f"[{login}] Кукі збережено у {cookies_file}\n")
        log_scroll_to_end(log_text)
    except Exception as e:
        log_text.insert("end", f"[{login}] Помилка при збереженні кукі: {str(e)}\n")
        log_scroll_to_end(log_text)


def load_cookies(driver, login, log_text):
    """Завантаження кукі з файлу."""
    cookies_file = f"cookies_{login}.pkl"
    if os.path.exists(cookies_file):
        try:
            with open(cookies_file, "rb") as f:
                cookies = pickle.load(f)
            for cookie in cookies:
                required_keys = {'name', 'value'}
                if not all(key in cookie for key in required_keys):
                    log_text.insert("end",
                                    f"[{login}] Помилка: кукі {cookie.get('name', 'невідомо')} не містить необхідних ключів\n")
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
            log_text.insert("end", f"[{login}] Кукі завантажено з {cookies_file}\n")
            log_scroll_to_end(log_text)
            return True
        except Exception as e:
            log_text.insert("end", f"[{login}] Помилка при завантаженні кукі: {str(e)}\n")
            log_scroll_to_end(log_text)
            return False
    log_text.insert("end", f"[{login}] Файл кукі для {login} не знайдено\n")
    log_scroll_to_end(log_text)
    return False


def delete_cookies(login, log_text):
    """Видалення файлу кукі при видаленні аккаунта."""
    cookies_file = f"cookies_{login}.pkl"
    if os.path.exists(cookies_file):
        os.remove(cookies_file)
        log_text.insert("end", f"[{login}] Файл кукі {cookies_file} видалено\n")
        log_scroll_to_end(log_text)
    else:
        log_text.insert("end", f"[{login}] Файл кукі не знайдено для видалення\n")
        log_scroll_to_end(log_text)


def login_to_threads(driver, account, log_text):
    """Логіка авторизації акаунта з обхідом антибот-захисту."""
    login = account["login"]
    # Генеруємо або використовуємо існуючий fingerprint
    if "fingerprint" not in account:
        account["fingerprint"] = generate_browser_fingerprint(login)
        log_text.insert("end", f"[{login}] Згенеровано новий відбиток браузера: {account['fingerprint']}\n")
        log_scroll_to_end(log_text)
    else:
        log_text.insert("end", f"[{login}] Використано існуючий відбиток браузера: {account['fingerprint']}\n")
        log_scroll_to_end(log_text)

    try:
        log_text.insert("end", f"[{login}] Перевірка наявності кукі...\n")
        log_scroll_to_end(log_text)
        if load_cookies(driver, login, log_text):
            driver.get("https://www.threads.net/")
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
            time.sleep(0.5)
            if "threads.net" in driver.current_url and "login" not in driver.current_url and driver.find_elements(
                    By.CSS_SELECTOR, "svg[aria-label='Profile']"):
                log_text.insert("end", f"[{login}] Успішна авторизація з кукі, поточний URL: {driver.current_url}\n")
                log_scroll_to_end(log_text)
                return True

        log_text.insert("end", f"[{login}] Завантаження сторінки threads.net...\n")
        log_scroll_to_end(log_text)
        driver.get("https://www.threads.net/")
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        time.sleep(0.5)

        # Оновлення сторінки для стабільного завантаження
        log_text.insert("end", f"[{login}] Оновлення сторінки для стабільного завантаження...\n")
        log_scroll_to_end(log_text)
        driver.refresh()
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        time.sleep(1)

        accept_cookies(driver, log_text, login)

        # Оновлений селектор для кнопки "Увійти"
        login_button_selector = "a[href='/login?show_choice_screen=true'] div.x6ikm8r.x10wlt62.xlyipyv"
        try:
            login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, login_button_selector)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_button)
            time.sleep(0.5)
            login_button.click()
            log_text.insert("end", f"[{login}] Натиснуто кнопку 'Увійти' на сторінці threads.net\n")
            log_scroll_to_end(log_text)
            time.sleep(1)
        except TimeoutException:
            log_text.insert("end",
                            f"[{login}] Не вдалося знайти кнопку 'Увійти', збережено: login_error_{login}.html\n")
            with open(f"login_error_{login}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return False

        # Очікування завантаження сторінки логіна
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        time.sleep(0.5)

        accept_cookies(driver, log_text, login)

        # Перевірка на проміжну сторінку "Продовжити через Instagram"
        continue_with_instagram_selector = "//a[@href='/login/?show_choice_screen=false']//span[contains(text(), 'Продовжити через Instagram')]"
        try:
            continue_with_instagram_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, continue_with_instagram_selector))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", continue_with_instagram_button)
            time.sleep(0.5)
            continue_with_instagram_button.click()
            log_text.insert("end", f"[{login}] Натиснуто кнопку 'Продовжити через Instagram'\n")
            log_scroll_to_end(log_text)
            time.sleep(1)
        except TimeoutException:
            log_text.insert("end",
                            f"[{login}] Проміжна сторінка 'Продовжити через Instagram' не знайдена, переходимо до наступного кроку\n")
            log_scroll_to_end(log_text)

        # Очікування завантаження сторінки після "Продовжити через Instagram"
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        time.sleep(0.5)

        accept_cookies(driver, log_text, login)

        # Клік на кнопку "Увійти натомість за допомогою імені користувача"
        username_login_selector = "a.x1i10hfl.xjbqb8w.x1ejq31n.xd10rxx.x1sy0etr.x17r0tee.x972fbf.xcfux6l.x1qhh985.xm0m39n.x9f619.x1ypdohk.xt0psk2.xe8uvvx.xdj266r.x11i5rnm.xat24cr.x1mh8g0r.xexx8yu.x4uap5.x18d9i69.xkhd6sd.x16tdsg8.x1hl2dhg.xggy1nq.x1a2a7pz.x1lku1pv.x12rw4y6.xrkepyr.x1citr7e.x37wo2f[href='/login/?show_choice_screen=false&variant=username']"
        try:
            username_login_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, username_login_selector)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", username_login_button)
            time.sleep(0.5)
            username_login_button.click()
            log_text.insert("end", f"[{login}] Натиснуто кнопку 'Увійти натомість за допомогою імені користувача'\n")
            log_scroll_to_end(log_text)
            time.sleep(1)
        except TimeoutException:
            log_text.insert("end",
                            f"[{login}] Не вдалося знайти кнопку 'Увійти натомість за допомогою імені користувача', збережено: login_error_{login}.html\n")
            with open(f"login_error_{login}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return False

        # Очікування завантаження сторінки логіна з полями
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        time.sleep(0.5)

        accept_cookies(driver, log_text, login)

        log_text.insert("end", f"[{login}] Очікування форми логіна протягом 5 секунд...\n")
        log_scroll_to_end(log_text)
        username_selectors = [
            "input[name='username']",
            "input[placeholder*='Username']",
            "input[autocomplete='username'][type='text']",
            "div[role='textbox'][aria-label*='Username']"
        ]
        username_element = None
        selected_username_selector = None
        for selector in username_selectors:
            try:
                username_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                selected_username_selector = selector
                log_text.insert("end", f"[{login}] Знайдено поле логіну за селектором: {selector}\n")
                log_scroll_to_end(log_text)
                break
            except TimeoutException:
                log_text.insert("end", f"[{login}] Не вдалося знайти поле логіну за селектором: {selector}\n")
                log_scroll_to_end(log_text)
                continue

        if not username_element:
            log_text.insert("end", f"[{login}] Не вдалося знайти поле логіну, збережено: login_error_{login}.html\n")
            with open(f"login_error_{login}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return False

        if not simulate_human_typing(driver, selected_username_selector, login, log_text, login):
            log_text.insert("end", f"[{login}] Помилка введення логіну, збережено: login_error_{login}.html\n")
            with open(f"login_error_{login}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return False

        password_selectors = [
            "input[name='password']",
            "input[placeholder*='Password']",
            "input[autocomplete='current-password'][type='password']",
            "div[role='textbox'][aria-label*='Password']"
        ]
        password_element = None
        selected_password_selector = None
        for selector in password_selectors:
            try:
                password_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                selected_password_selector = selector
                log_text.insert("end", f"[{login}] Знайдено поле пароля за селектором: {selector}\n")
                log_scroll_to_end(log_text)
                break
            except TimeoutException:
                log_text.insert("end", f"[{login}] Не вдалося знайти поле пароля за селектором: {selector}\n")
                log_scroll_to_end(log_text)
                continue

        if not password_element:
            log_text.insert("end", f"[{login}] Не вдалося знайти поле пароля, збережено: password_error_{login}.html\n")
            with open(f"password_error_{login}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return False

        if not simulate_human_typing(driver, selected_password_selector, account["password"], log_text, login):
            log_text.insert("end", f"[{login}] Помилка введення пароля, збережено: password_error_{login}.html\n")
            with open(f"password_error_{login}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return False

        actions = ActionChains(driver)
        actions.send_keys(Keys.RETURN).perform()
        log_text.insert("end", f"[{login}] Натискання Enter після введення логіну та пароля\n")
        log_scroll_to_end(log_text)

        log_text.insert("end", f"[{login}] Очікування 7 секунд перед запитом 2FA коду...\n")
        log_scroll_to_end(log_text)
        time.sleep(7)

        if account.get("2fa_url"):
            log_text.insert("end", f"[{login}] Спроба отримати 2FA код...\n")
            log_scroll_to_end(log_text)
            twofa_code = get_2fa_code(account["2fa_url"], log_text)
            if not twofa_code:
                log_text.insert("end", f"[{login}] Не вдалося отримати 2FA код, перевірте 2fa_url\n")
                log_scroll_to_end(log_text)
                return False

            log_text.insert("end", f"[{login}] Отримано 2FA код: {twofa_code}\n")
            log_scroll_to_end(log_text)
            time.sleep(0.5)

            twofa_selectors = [
                "input[name='code']",
                "input[placeholder*='code']",
                "input[autocomplete='one-time-code']",
                "input[aria-label*='Code']"
            ]
            twofa_element = None
            selected_2fa_selector = None
            for selector in twofa_selectors:
                try:
                    twofa_element = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    selected_2fa_selector = selector
                    log_text.insert("end", f"[{login}] Знайдено поле 2FA за селектором: {selector}\n")
                    log_scroll_to_end(log_text)
                    break
                except TimeoutException:
                    log_text.insert("end", f"[{login}] Не вдалося знайти поле 2FA за селектором: {selector}\n")
                    log_scroll_to_end(log_text)
                    continue

            if not twofa_element:
                log_text.insert("end", f"[{login}] Поле 2FA не знайдено, збережено: 2fa_error_{login}.html\n")
            with open(f"2fa_error_{login}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
                return False

            if not simulate_human_typing(driver, selected_2fa_selector, twofa_code, log_text, login,
                                         delay_range=(0.05, 0.1)):
                log_text.insert("end", f"[{login}] Помилка введення 2FA, збережено: 2fa_error_{login}.html\n")
                with open(f"2fa_error_{login}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                return False

            log_text.insert("end",
                            f"[{login}] Очікування 3 секунд перед натисканням Enter після введення 2FA коду...\n")
            log_scroll_to_end(log_text)
            time.sleep(3)

            actions.send_keys(Keys.RETURN).perform()
            log_text.insert("end", f"[{login}] Натискання Enter після введення 2FA коду\n")
            log_scroll_to_end(log_text)

        log_text.insert("end", f"[{login}] Очікування редіректу на threads.net (максимум 20 секунд)...\n")
        log_scroll_to_end(log_text)
        try:
            WebDriverWait(driver, 20).until(
                lambda driver: "threads.net" in driver.current_url and "login" not in driver.current_url
            )
            log_text.insert("end", f"[{login}] Редірект на threads.net виконано, поточний URL: {driver.current_url}\n")
            log_scroll_to_end(log_text)
        except TimeoutException:
            log_text.insert("end", f"[{login}] Таймаут при очікування редіректу, поточний URL: {driver.current_url}\n")
            log_scroll_to_end(log_text)

        if "threads.net" in driver.current_url and "login" not in driver.current_url:
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
                profile_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "svg[aria-label='Profile']"))
                )
                if profile_element:
                    log_text.insert("end",
                                    f"[{login}] Успішна авторизація, знайдено елемент профілю, поточний URL: {driver.current_url}\n")
                    log_scroll_to_end(log_text)
                    save_cookies(driver, login, log_text)
                    return True
            except TimeoutException:
                log_text.insert("end",
                                f"[{login}] Елемент профілю не знайдено, але авторизація може бути успішною, перевірте вручну\n")
                log_scroll_to_end(log_text)
                save_cookies(driver, login, log_text)
                return True

        log_text.insert("end", f"[{login}] Невдача авторизації, збережено: login_error_{login}.html\n")
        log_scroll_to_end(log_text)
        with open(f"login_error_{login}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return False

    except TimeoutException as e:
        log_text.insert("end", f"[{login}] Таймаут при очікування елемента: {str(e)}\n")
        log_scroll_to_end(log_text)
        with open(f"timeout_error_{login}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return False
    except Exception as e:
        log_text.insert("end", f"[{login}] Помилка авторизації: {str(e)}\n")
        log_scroll_to_end(log_text)
        with open(f"error_{login}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return False


def validate_account_async(login, password, proxy, twofa_url, callback, log_text, root):
    """Асинхронна перевірка акаунта."""

    def task():
        fingerprint = generate_browser_fingerprint(login)
        options = ChromeOptions()
        options.add_argument(f"--user-agent={fingerprint['user_agent']}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")

        driver = None
        driver_closed = False
        try:
            driver = Chrome(options=options, headless=False)
            driver.set_window_size(fingerprint["viewport"]["width"], fingerprint["viewport"]["height"])

            driver.execute_script(f"""
                Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});
                Object.defineProperty(navigator, 'languages', {{ get: () => {fingerprint['languages']} }});
                Object.defineProperty(navigator, 'platform', {{ get: () => '{fingerprint['platform']}' }});
                Object.defineProperty(navigator, 'timezone', {{ get: () => {fingerprint['timezone_offset']} }});
                const originalGetContext = HTMLCanvasElement.prototype.getContext;
                HTMLCanvasElement.prototype.getContext = function(type) {{
                    const context = originalGetContext.call(this, type);
                    if (type.includes('webgl') || type.includes('2d')) {{
                        const getParameter = context.getParameter;
                        context.getParameter = function(param) {{
                            if (param === 37445) return 'WebGL 1.0 (OpenGL ES)';
                            if (param === 37446) return 'WebGL 1.0 (OpenGL ES)';
                            if (param === 7937) return 'NVIDIA Corporation';
                            return getParameter.call(this, param);
                        }};
                        const toDataURL = this.toDataURL;
                        this.toDataURL = function() {{
                            return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==';
                        }};
                    }}
                    return context;
                }};
                Object.defineProperty(navigator, 'fonts', {{
                    get: () => ['Arial', 'Times New Roman', 'Helvetica', 'Courier New']
                }});
            """)

            log_text.insert("end", f"[{login}] Ініціалізація завершена з відбитком:\n")
            log_text.insert("end", f"  User-Agent: {fingerprint['user_agent']}\n")
            log_text.insert("end",
                            f"  Viewport: {fingerprint['viewport']['width']}x{fingerprint['viewport']['height']}\n")
            log_text.insert("end",
                            f"  Languages: {[lang for sublist in fingerprint['languages'] for lang in sublist]}\n")
            log_text.insert("end", f"  Platform: {fingerprint['platform']}\n")
            log_text.insert("end", f"  Timezone Offset: {fingerprint['timezone_offset']}\n")
            log_scroll_to_end(log_text)

            account_data = {"login": login, "password": password, "2fa_url": twofa_url, "fingerprint": fingerprint}
            success = login_to_threads(driver, account_data, log_text)
            if success:
                root.after(0, lambda: callback(success, driver=None))
                driver.quit()
                driver_closed = True
                log_text.insert("end", f"[{login}] Драйвер успішно закритий\n")
                log_scroll_to_end(log_text)
            else:
                log_text.insert("end",
                                f"[{login}] Авторизація не вдалася, браузер залишено відкритим для ручного введення\n")
                log_scroll_to_end(log_text)
                root.after(0, lambda: callback(success, driver=driver))  # Передаємо драйвер для ручного завершення

        except Exception as e:
            log_text.insert("end", f"[{login}] Помилка валідності: {str(e)}\n")
            log_scroll_to_end(log_text)
            if driver and not driver_closed:
                root.after(0, lambda: callback(False, driver=driver))  # Передаємо драйвер у випадку помилки
        finally:
            if driver is not None and not driver_closed and success:
                try:
                    driver.quit()
                    log_text.insert("end", f"[{login}] Драйвер успішно закритий\n")
                    log_scroll_to_end(log_text)
                except Exception as e:
                    log_text.insert("end", f"[{login}] Помилка при закритті драйвера: {str(e)}\n")
                    log_scroll_to_end(log_text)

    thread = threading.Thread(target=task, daemon=True)
    thread.start()
    log_text.insert("end", f"[{login}] Потік запущено\n")
    log_scroll_to_end(log_text)


def delete_account(login, log_text):
    """Видалення аккаунта та відповідних кукі."""
    delete_cookies(login, log_text)
    log_text.insert("end", f"[{login}] Аккаунт видалено\n")
    log_scroll_to_end(log_text)


if __name__ == "__main__":
    import tkinter as tk

    root = tk.Tk()
    log_text = tk.Text(root)
    log_text.pack()


    def callback(success, driver):
        print(f"Успіх: {success}, Драйвер: {driver}")


    validate_account_async("somehoww1", "your_password", None, "https://2fa.fb.rip/JXS4GPSRHAAY3MBHKTI63QPR46GZJ35K",
                           callback, log_text, root)
    root.mainloop()