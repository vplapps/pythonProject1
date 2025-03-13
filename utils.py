import json
import requests
import re
import time
import random
import os
from undetected_chromedriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DATA_FILE = "bot_data.json"

def load_data():
    """Завантаження даних із файлу."""
    default_data = {
        "accounts": [],
        "warmup_settings": {
            "scroll_min": 7,
            "scroll_max": 12,
            "like_prob": 0.5,
            "days": 3,
            "work_interval": 60,
            "pause_interval": 60
        },
        "comment_settings": {
            "min_likes": 10,
            "max_likes": 100,
            "max_comments": 20,
            "max_comments_per_day": 50,
            "max_comments_per_post": 10,
            "comments": ["Круто!", "Супер!"],
            "intensity": 5,
            "photo_paths": [],
            "work_interval": 60,
            "pause_interval": 60
        },
        "settings": {"super_mode": False}
    }

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                save_data(default_data)
                return default_data
            data = json.loads(content)
            for key in default_data:
                if key not in data:
                    data[key] = default_data[key]
            if "comment_settings" in data:
                for key in default_data["comment_settings"]:
                    if key not in data["comment_settings"]:
                        data["comment_settings"][key] = default_data["comment_settings"][key]
            if "warmup_settings" in data:
                for key in default_data["warmup_settings"]:
                    if key not in data["warmup_settings"]:
                        data["warmup_settings"][key] = default_data["warmup_settings"][key]
            save_data(data)
            return data
    except FileNotFoundError:
        save_data(default_data)
        return default_data
    except json.JSONDecodeError as e:
        print(f"Помилка декодування JSON у {DATA_FILE}: {str(e)}. Використано стандартні дані.")
        save_data(default_data)
        return default_data

def save_data(data):
    """Збереження даних у файл."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Помилка збереження даних у {DATA_FILE}: {str(e)}")

def get_2fa_code(twofa_url, log_text):
    """
    Отримує 2FA-код через API або з веб-сторінки (як резерв).
    """
    def log_message(message):
        log_text.insert("end", f"[2FA] {message}\n")
        log_scroll_to_end(log_text)

    # Спроба отримати код через API
    try:
        api_url = '/api/otp/' + twofa_url.rstrip('/')
        log_message(f"Запит до API: {api_url}")
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()

        data = response.json()
        if not data.get("ok"):
            log_message(f"Помилка API: {data.get('error', 'Невідома помилка')}")
            return None

        twofa_code = data["data"]["otp"]
        time_remaining = int(data["data"]["timeRemaining"])

        log_message(f"Отриманий 2FA-код: {twofa_code}, залишилося часу: {time_remaining} секунд")

        if not twofa_code.isdigit() or len(twofa_code) != 6:
            log_message(f"Отриманий код не є валідним 6-значним числом: {twofa_code}")
            return None

        if time_remaining < 5:
            log_message(f"Залишилося мало часу ({time_remaining} секунд), очікування оновлення коду...")
            time.sleep(5 - time_remaining + 1)
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                log_message(f"Помилка при оновленні коду: {data.get('error', 'Невідома помилка')}")
                return None
            twofa_code = data["data"]["otp"]
            log_message(f"Код оновлено: {twofa_code}")

        return twofa_code
    except requests.exceptions.RequestException as e:
        log_message(f"Помилка при запиті до API: {str(e)}")

    # Резервний метод через undetected-chromedriver
    driver = None
    try:
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        driver = Chrome(options=options)
        driver.set_window_size(1280, 720)

        log_message(f"Спроба отримати код через сторінку: {twofa_url}")
        driver.get(twofa_url)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        code_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "verifyCode")),
            message="Не знайдено елемент із 2FA-кодом (id='verifyCode') на сторінці"
        )
        twofa_code = code_element.text.strip()
        log_message(f"Отриманий 2FA-код через сторінку: {twofa_code}")

        if not twofa_code.isdigit() or len(twofa_code) != 6:
            log_message(f"Код через сторінку не валідний: {twofa_code}")
            return None

        return twofa_code
    except Exception as e:
        log_message(f"Помилка при отриманні коду через сторінку: {str(e)}")
        return None
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception as e:
                log_message(f"Помилка при закритті драйвера: {str(e)}")

def log_scroll_to_end(log_text):
    """Прокрутка логів до кінця."""
    try:
        log_text.see("end")
    except Exception as e:
        print(f"Помилка прокрутки логів: {str(e)}")

def idle_scroll(driver, log_text, login, delay=None, min_scrolls=5, max_scrolls=10):
    """Імітація простого скролінгу для підтримання активності."""
    try:
        scroll_count = random.randint(min_scrolls, max_scrolls)
        for _ in range(scroll_count):
            driver.execute_script("window.scrollBy(0, 200);")
            time.sleep(random.uniform(0.5, 1.5))
        log_text.insert("end", f"[{login}] Виконано {scroll_count} прокруток\n")
        log_scroll_to_end(log_text)
        if delay:
            time.sleep(delay)
    except Exception as e:
        log_text.insert("end", f"[{login}] Помилка при idle прокрутці: {str(e)}\n")
        log_scroll_to_end(log_text)