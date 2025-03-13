import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import random
from utils import load_data, save_data, log_scroll_to_end
from auth import validate_account_async, delete_account, generate_browser_fingerprint
from warmup import warmup_account
from commenting import comment_posts

class ThreadsBotGUI:
    def log_scroll_to_end(self):
        """Прокрутка текстового поля логів до кінця."""
        self.log_text.see("end")

    def __init__(self, root):
        self.root = root
        self.root.title("Жосткий бот для Threads")
        self.root.geometry("1200x800")
        self.root.configure(fg_color="#1e1e2f")

        # Add global exception handler for Tkinter
        def handle_exception(exctype, value, traceback):
            self.log_text.insert("end", f"Неперехоплена помилка: {value}\n")
            self.log_scroll_to_end()

        import sys
        sys.excepthook = handle_exception

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure("Treeview",
                             background="#2a2a3d",
                             fieldbackground="#2a2a3d",
                             foreground="white",
                             font=("Segoe UI", 12))
        self.style.configure("Treeview.Heading",
                             background="#3b3b58",
                             foreground="white",
                             font=("Segoe UI", 13, "bold"))
        self.style.map("Treeview",
                       background=[("selected", "#4a4a6d")],
                       foreground=[("selected", "white")])

        self.data = load_data()
        self.running_threads = {}  # {login: (thread, stop_event, pause_event, task_type, driver)}
        self.show_browser = ctk.BooleanVar(value=False)
        self.last_save_time = time.time()
        self.save_interval = 600
        self.current_fingerprint = None
        self.pending_driver = None  # Зберігаємо драйвер для ручного завершення

        self.current_login = ctk.StringVar(value="")

        for acc in self.data["accounts"]:
            if "warmup_stats" not in acc:
                acc["warmup_stats"] = {
                    "days_completed": 0,
                    "days_total": 0,
                    "posts_viewed": 0,
                    "likes_made": 0
                }
            if "comment_stats" not in acc:
                acc["comment_stats"] = {
                    "comments_made": 0
                }
            if "status" not in acc:
                acc["status"] = "Готовий"

        if "max_comments_per_day" not in self.data["comment_settings"]:
            self.data["comment_settings"]["max_comments_per_day"] = 50
        if "max_comments_per_post" not in self.data["comment_settings"]:
            self.data["comment_settings"]["max_comments_per_post"] = 10
        if "photo_paths" not in self.data["comment_settings"]:
            self.data["comment_settings"]["photo_paths"] = []

        self.setup_gui()

    def setup_gui(self):
        main_frame = ctk.CTkFrame(self.root, fg_color="#1e1e2f")
        main_frame.pack(fill="both", expand=True)

        header_frame = ctk.CTkFrame(self.root, fg_color="#2a2a3d", height=50)
        header_frame.pack(fill="x")
        ctk.CTkLabel(header_frame, text="Жосткий бот для Threads", text_color="white",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=10)

        sidebar_frame = ctk.CTkFrame(main_frame, fg_color="#2a2a3d", width=200)
        sidebar_frame.pack(side="left", fill="y")

        self.tabs = {
            "Акаунти": ctk.CTkFrame(main_frame, fg_color="#1e1e2f"),
            "Прогрів": ctk.CTkFrame(main_frame, fg_color="#1e1e2f"),
            "Коментування": ctk.CTkFrame(main_frame, fg_color="#1e1e2f"),
            "Налаштування": ctk.CTkFrame(main_frame, fg_color="#1e1e2f")
        }
        self.current_tab = None

        for tab_name in self.tabs:
            btn = ctk.CTkButton(sidebar_frame, text=tab_name, fg_color="#2a2a3d", hover_color="#4a4a6d",
                                text_color="white",
                                font=ctk.CTkFont(size=12, weight="bold"),
                                command=lambda name=tab_name: self.show_tab(name))
            btn.pack(fill="x", padx=5, pady=2)

        log_frame = ctk.CTkFrame(self.root, fg_color="#1e1e2f")
        log_frame.pack(side="bottom", fill="both", expand=True)
        self.log_text = ctk.CTkTextbox(log_frame, height=10, fg_color="#2a2a3d", text_color="white",
                                       font=ctk.CTkFont(size=10))
        self.log_text.pack(fill="both", expand=True)

        self.stop_btn = ctk.CTkButton(self.root, text="Зупинити все", fg_color="#4a4a6d", hover_color="#6a6a8d",
                                      text_color="white",
                                      command=self.stop_all, state="disabled")
        self.stop_btn.pack(pady=10)

        self.setup_accounts_tab()
        self.setup_warmup_tab()
        self.setup_commenting_tab()
        self.setup_settings_tab()
        self.show_tab("Акаунти")

    def show_tab(self, tab_name):
        if self.current_tab:
            self.current_tab.pack_forget()
        self.current_tab = self.tabs[tab_name]
        self.current_tab.pack(side="left", fill="both", expand=True)

    def setup_accounts_tab(self):
        accounts_tab = self.tabs["Акаунти"]

        input_frame = ctk.CTkFrame(accounts_tab, fg_color="#1e1e2f")
        input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(input_frame, text="Логін:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=0, column=0,
                                                                                                     padx=5, pady=5,
                                                                                                     sticky="e")
        self.login_entry = ctk.CTkEntry(input_frame, fg_color="#2a2a3d", text_color="white", width=200,
                                        textvariable=self.current_login)
        self.login_entry.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkButton(input_frame, text="Вставити", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=lambda: self.insert_from_clipboard(self.login_entry)).grid(row=0, column=2, padx=5,
                                                                                         pady=5)

        ctk.CTkLabel(input_frame, text="Пароль:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=1, column=0,
                                                                                                      padx=5, pady=5,
                                                                                                      sticky="e")
        self.password_entry = ctk.CTkEntry(input_frame, fg_color="#2a2a3d", text_color="white", width=200, show="*")
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)
        ctk.CTkButton(input_frame, text="Вставити", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=lambda: self.insert_from_clipboard(self.password_entry)).grid(row=1, column=2, padx=5,
                                                                                            pady=5)

        ctk.CTkLabel(input_frame, text="Проксі (необов’язково):", text_color="white", font=ctk.CTkFont(size=11)).grid(
            row=2, column=0, padx=5, pady=5, sticky="e")
        self.proxy_entry = ctk.CTkEntry(input_frame, fg_color="#2a2a3d", text_color="white", width=200)
        self.proxy_entry.grid(row=2, column=1, padx=5, pady=5)
        ctk.CTkButton(input_frame, text="Вставити", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=lambda: self.insert_from_clipboard(self.proxy_entry)).grid(row=2, column=2, padx=5,
                                                                                         pady=5)

        ctk.CTkLabel(input_frame, text="2FA URL:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=3, column=0,
                                                                                                       padx=5, pady=5,
                                                                                                       sticky="e")
        self.twofa_entry = ctk.CTkEntry(input_frame, fg_color="#2a2a3d", text_color="white", width=200)
        self.twofa_entry.grid(row=3, column=1, padx=5, pady=5)
        ctk.CTkButton(input_frame, text="Вставити", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=lambda: self.insert_from_clipboard(self.twofa_entry)).grid(row=3, column=2, padx=5,
                                                                                         pady=5)

        fingerprint_frame = ctk.CTkFrame(accounts_tab, fg_color="#2a2a3d")
        fingerprint_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(fingerprint_frame, text="Відбиток браузера", text_color="white",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=5, pady=5)

        self.fingerprint_label = ctk.CTkLabel(fingerprint_frame,
                                              text="Натисніть 'Генерувати', щоб створити відбиток\n\n\n\n",
                                              text_color="white", font=ctk.CTkFont(size=10), justify="left", anchor="w")
        self.fingerprint_label.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        ctk.CTkButton(fingerprint_frame, text="Генерувати", fg_color="#4a4a6d", hover_color="#6a6a8d",
                      text_color="white",
                      command=self.generate_fingerprint).grid(row=2, column=0, pady=5)

        self.accounts_tree = ttk.Treeview(accounts_tab, columns=("Login", "Proxy", "2FA", "Status"), show="headings",
                                          height=10, style="Treeview")
        self.accounts_tree.heading("Login", text="Логін")
        self.accounts_tree.heading("Proxy", text="Проксі")
        self.accounts_tree.heading("2FA", text="2FA")
        self.accounts_tree.heading("Status", text="Статус")
        self.accounts_tree.column("Login", width=300)
        self.accounts_tree.column("Proxy", width=300)
        self.accounts_tree.column("2FA", width=300)
        self.accounts_tree.column("Status", width=150)
        self.accounts_tree.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

        self.accounts_tree.bind("<Double-1>", self.toggle_account_select)

        button_frame = ctk.CTkFrame(accounts_tab, fg_color="#1e1e2f")
        button_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        ctk.CTkButton(button_frame, text="Додати акаунт", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=self.add_account).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Редагувати", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=self.edit_account).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Видалити", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=self.delete_account).pack(side="left", padx=5)
        self.manual_add_btn = ctk.CTkButton(button_frame, text="Додати вручну/Аккаунт валідний", fg_color="#4a4a6d",
                                            hover_color="#6a6a8d", text_color="white",
                                            command=self.manual_add_account, state="disabled")
        self.manual_add_btn.pack(side="left", padx=5)

        accounts_tab.grid_columnconfigure(0, weight=1)
        accounts_tab.grid_columnconfigure(1, weight=1)
        accounts_tab.grid_rowconfigure(1, weight=1)

        self.update_accounts_tree()

    def generate_fingerprint(self):
        if not self.current_login.get().strip():
            self.log_text.insert("end", "Помилка: Введіть логін перед генерацією відбитка\n")
            self.log_scroll_to_end()
            return

        login = self.current_login.get().strip()
        self.current_fingerprint = generate_browser_fingerprint(login)
        self.log_text.insert("end", f"Новий відбиток для {login}:\n")
        self.log_text.insert("end", f"  User-Agent: {self.current_fingerprint['user_agent']}\n")
        self.log_text.insert("end",
                             f"  Viewport: {self.current_fingerprint['viewport']['width']}x{self.current_fingerprint['viewport']['height']}\n")

        try:
            languages_flat = [lang for sublist in self.current_fingerprint['languages'] for lang in sublist]
            languages_display = ', '.join(languages_flat)
        except (TypeError, AttributeError) as e:
            languages_display = f"Помилка відображення мов: {str(e)}"
            self.log_text.insert("end", f"  Languages: {languages_display}\n")
            self.log_scroll_to_end()
            return

        self.log_text.insert("end", f"  Languages: {languages_display}\n")
        self.log_text.insert("end", f"  Platform: {self.current_fingerprint['platform']}\n")
        self.log_text.insert("end", f"  Timezone Offset: {self.current_fingerprint['timezone_offset']}\n")
        self.log_scroll_to_end()

        fingerprint_text = f"User-Agent: {self.current_fingerprint['user_agent']}\n" \
                           f"Viewport: {self.current_fingerprint['viewport']['width']}x{self.current_fingerprint['viewport']['height']}\n" \
                           f"Languages: {languages_display}\n" \
                           f"Platform: {self.current_fingerprint['platform']}\n" \
                           f"Timezone Offset: {self.current_fingerprint['timezone_offset']}"
        self.fingerprint_label.configure(text=fingerprint_text)

    def setup_warmup_tab(self):
        warmup_tab = self.tabs["Прогрів"]

        self.warmup_accounts_tree = ttk.Treeview(warmup_tab, columns=(
            "Login", "Select", "Days", "PostsViewed", "LikesMade", "Status", "Action"), show="headings", height=10,
                                                 style="Treeview")
        self.warmup_accounts_tree.heading("Login", text="Логін")
        self.warmup_accounts_tree.heading("Select", text="Вибрати")
        self.warmup_accounts_tree.heading("Days", text="Дні")
        self.warmup_accounts_tree.heading("PostsViewed", text="Переглянуто постів")
        self.warmup_accounts_tree.heading("LikesMade", text="Лайків")
        self.warmup_accounts_tree.heading("Status", text="Статус")
        self.warmup_accounts_tree.heading("Action", text="Дія")
        self.warmup_accounts_tree.column("Login", width=200)
        self.warmup_accounts_tree.column("Select", width=100)
        self.warmup_accounts_tree.column("Days", width=100)
        self.warmup_accounts_tree.column("PostsViewed", width=150)
        self.warmup_accounts_tree.column("LikesMade", width=100)
        self.warmup_accounts_tree.column("Status", width=150)
        self.warmup_accounts_tree.column("Action", width=150)
        self.warmup_accounts_tree.grid(row=0, column=0, columnspan=5, padx=10, pady=10, sticky="nsew")

        # Bind left-click to show context menu
        self.warmup_accounts_tree.bind("<Button-1>", self.show_warmup_context_menu)

        ctk.CTkLabel(warmup_tab, text="Мін. тредів:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=1,
                                                                                                          column=1,
                                                                                                          padx=5,
                                                                                                          pady=5)
        self.scroll_min_entry = ctk.CTkEntry(warmup_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.scroll_min_entry.insert(0, self.data["warmup_settings"].get("scroll_min", 10))
        self.scroll_min_entry.grid(row=1, column=2, padx=5, pady=5)

        ctk.CTkLabel(warmup_tab, text="Макс. тредів:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=2,
                                                                                                           column=1,
                                                                                                           padx=5,
                                                                                                           pady=5)
        self.scroll_max_entry = ctk.CTkEntry(warmup_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.scroll_max_entry.insert(0, self.data["warmup_settings"].get("scroll_max", 20))
        self.scroll_max_entry.grid(row=2, column=2, padx=5, pady=5)

        ctk.CTkLabel(warmup_tab, text="Ймовірність лайка (0-1):", text_color="white", font=ctk.CTkFont(size=11)).grid(
            row=3, column=1, padx=5, pady=5)
        self.like_prob_entry = ctk.CTkEntry(warmup_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.like_prob_entry.insert(0, self.data["warmup_settings"].get("like_prob", 0.3))
        self.like_prob_entry.grid(row=3, column=2, padx=5, pady=5)

        ctk.CTkLabel(warmup_tab, text="Днів прогріву:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=4,
                                                                                                            column=1,
                                                                                                            padx=5,
                                                                                                            pady=5)
        self.days_entry = ctk.CTkEntry(warmup_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.days_entry.insert(0, self.data["warmup_settings"].get("days", 3))
        self.days_entry.grid(row=4, column=2, padx=5, pady=5)

        ctk.CTkLabel(warmup_tab, text="Час роботи (хв):", text_color="white", font=ctk.CTkFont(size=11)).grid(row=5,
                                                                                                              column=1,
                                                                                                              padx=5,
                                                                                                              pady=5)
        self.work_interval_entry = ctk.CTkEntry(warmup_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.work_interval_entry.insert(0, self.data["warmup_settings"].get("work_interval", 60))
        self.work_interval_entry.grid(row=5, column=2, padx=5, pady=5)

        ctk.CTkLabel(warmup_tab, text="Час паузи (хв):", text_color="white", font=ctk.CTkFont(size=11)).grid(row=6,
                                                                                                             column=1,
                                                                                                             padx=5,
                                                                                                             pady=5)
        self.pause_interval_entry = ctk.CTkEntry(warmup_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.pause_interval_entry.insert(0, self.data["warmup_settings"].get("pause_interval", 60))
        self.pause_interval_entry.grid(row=6, column=2, padx=5, pady=5)

        self.warmup_accounts_tree.bind("<Double-1>", self.toggle_warmup_select)

        ctk.CTkButton(warmup_tab, text="Запустити прогрів", fg_color="#4a4a6d", hover_color="#6a6a8d",
                      text_color="white",
                      command=self.start_warmup).grid(row=7, column=1, pady=10)

        warmup_tab.grid_columnconfigure(0, weight=1)
        warmup_tab.grid_columnconfigure(4, weight=1)

        self.update_warmup_accounts()

    def update_warmup_accounts(self):
        for item in self.warmup_accounts_tree.get_children():
            self.warmup_accounts_tree.delete(item)

        for acc in self.data["accounts"]:
            stats = acc["warmup_stats"]
            days = f"{stats['days_completed']}/{stats['days_total']}"
            status = acc.get("status", "Готовий")
            action_text = "Дія" if status != "Готовий" else "Немає дії"
            self.warmup_accounts_tree.insert("", "end", values=(
                acc["login"],
                "☐",
                days,
                stats["posts_viewed"],
                stats["likes_made"],
                status,
                action_text
            ))

    def update_stats(self, login, day, days, posts_viewed, likes_made):
        """Update the GUI with the latest warmup statistics for the given account."""
        for item in self.warmup_accounts_tree.get_children():
            item_login = self.warmup_accounts_tree.item(item)["values"][0]
            if item_login == login:
                self.warmup_accounts_tree.item(item, values=(
                    login,
                    self.warmup_accounts_tree.item(item)["values"][1],  # Keep the select status
                    f"{day}/{days}",  # Update days
                    posts_viewed,
                    likes_made,
                    self.warmup_accounts_tree.item(item)["values"][5],  # Keep the status
                    self.warmup_accounts_tree.item(item)["values"][6]   # Keep the action
                ))
                break
        self.safe_log(login, f"Оновлено статистику: День {day}/{days}, Переглянуто {posts_viewed} постів, Лайків {likes_made}")

    def show_warmup_context_menu(self, event):
        """Show context menu for warmup actions when left-clicking the Action column."""
        item = self.warmup_accounts_tree.identify_row(event.y)
        column = self.warmup_accounts_tree.identify_column(event.x)
        if not item or column != "#7":  # Action column is #7
            return

        login = self.warmup_accounts_tree.item(item)["values"][0]
        status = self.warmup_accounts_tree.item(item)["values"][5]

        menu = tk.Menu(self.root, tearoff=0, bg="#2a2a3d", fg="white",
                       activebackground="#4a4a6d", activeforeground="white")
        if status == "В роботі":
            menu.add_command(label="Пауза", command=lambda: self.pause_account(login, "warmup"))
        elif status == "Пауза":
            menu.add_command(label="Відновити", command=lambda: self.resume_account(login, "warmup"))
        if status in ["В роботі", "Пауза"]:
            menu.add_command(label="Завершити", command=lambda: self.stop_account(login, "warmup"))

        if menu.index("end") is not None:
            menu.post(event.x_root, event.y_root)

    def pause_account(self, login, task_type):
        if login in self.running_threads:
            _, _, pause_event, _, _ = self.running_threads[login]
            with threading.Lock():
                if not pause_event.is_set():
                    print(f"Pausing {login} at {time.time()}")
                    pause_event.set()
                    for acc in self.data["accounts"]:
                        if acc["login"] == login:
                            acc["status"] = "Пауза"
                            break
                    self.update_warmup_accounts()

    def resume_account(self, login, task_type):
        if login in self.running_threads:
            _, _, pause_event, _, _ = self.running_threads[login]
            with threading.Lock():
                if pause_event.is_set():
                    print(f"Resuming {login} at {time.time()}")
                    pause_event.clear()
                    for acc in self.data["accounts"]:
                        if acc["login"] == login:
                            acc["status"] = "В роботі"
                            break
                    self.update_warmup_accounts()

    def toggle_warmup_select(self, event):
        item = self.warmup_accounts_tree.identify_row(event.y)
        if item:
            login = self.warmup_accounts_tree.item(item)["values"][0]
            current = self.warmup_accounts_tree.item(item)["values"][1]
            self.warmup_accounts_tree.item(item, values=(
                login,
                "☑" if current == "☐" else "☐",
                self.warmup_accounts_tree.item(item)["values"][2],
                self.warmup_accounts_tree.item(item)["values"][3],
                self.warmup_accounts_tree.item(item)["values"][4],
                self.warmup_accounts_tree.item(item)["values"][5],
                self.warmup_accounts_tree.item(item)["values"][6]
            ))

    def start_warmup(self):
        selected = [self.warmup_accounts_tree.item(item)["values"][0] for item in
                    self.warmup_accounts_tree.get_children() if
                    self.warmup_accounts_tree.item(item)["values"][1] == "☑"]
        if not selected:
            messagebox.showwarning("Попередження", "Виберіть хоча б один акаунт!")
            return

        try:
            scroll_min = int(self.scroll_min_entry.get())
            scroll_max = int(self.scroll_max_entry.get())
            like_prob = float(self.like_prob_entry.get())
            days = int(self.days_entry.get())
            work_interval = int(self.work_interval_entry.get())
            pause_interval = int(self.pause_interval_entry.get())

            if scroll_min < 0 or scroll_max < scroll_min or like_prob < 0 or like_prob > 1 or days <= 0 or work_interval <= 0 or pause_interval <= 0:
                raise ValueError("Некоректні параметри прогріву!")
        except ValueError as e:
            messagebox.showerror("Помилка", f"Перевірте введені значення: {str(e)}")
            return

        self.stop_btn.configure(state="normal")
        for login in selected:
            if login in self.running_threads:
                continue
            account = next(acc for acc in self.data["accounts"] if acc["login"] == login)
            if account["warmup_stats"]["days_total"] != days:
                account["warmup_stats"]["days_total"] = days
            account["status"] = "В роботі"
            stop_event = threading.Event()
            pause_event = threading.Event()
            thread = threading.Thread(target=warmup_account, args=(account, stop_event, pause_event,
                                                                   scroll_min,
                                                                   scroll_max,
                                                                   like_prob,
                                                                   days,
                                                                   self.log_text,
                                                                   self.show_browser.get(),
                                                                   self,
                                                                   work_interval,
                                                                   pause_interval), daemon=True)
            self.running_threads[login] = (thread, stop_event, pause_event, "warmup", None)
            thread.start()
            self.safe_log(login, "Запущено прогрів.")
            self.update_warmup_accounts()

    def setup_commenting_tab(self):
        comment_tab = self.tabs["Коментування"]

        self.comment_accounts_tree = ttk.Treeview(comment_tab,
                                                  columns=("Login", "Select", "CommentsMade", "Status", "Action"),
                                                  show="headings", height=10, style="Treeview")
        self.comment_accounts_tree.heading("Login", text="Логін")
        self.comment_accounts_tree.heading("Select", text="Вибрати")
        self.comment_accounts_tree.heading("CommentsMade", text="Коментарів")
        self.comment_accounts_tree.heading("Status", text="Статус")
        self.comment_accounts_tree.heading("Action", text="Дія")
        self.comment_accounts_tree.column("Login", width=200)
        self.comment_accounts_tree.column("Select", width=100)
        self.comment_accounts_tree.column("CommentsMade", width=150)
        self.comment_accounts_tree.column("Status", width=150)
        self.comment_accounts_tree.column("Action", width=100)
        self.comment_accounts_tree.grid(row=0, column=0, columnspan=5, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(comment_tab, text="Мін. лайків:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=1,
                                                                                                           column=1,
                                                                                                           padx=5,
                                                                                                           pady=5)
        self.min_likes_entry = ctk.CTkEntry(comment_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.min_likes_entry.insert(0, self.data["comment_settings"].get("min_likes", 10))
        self.min_likes_entry.grid(row=1, column=2, padx=5, pady=5)

        ctk.CTkLabel(comment_tab, text="Макс. лайків:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=2,
                                                                                                            column=1,
                                                                                                            padx=5,
                                                                                                            pady=5)
        self.max_likes_entry = ctk.CTkEntry(comment_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.max_likes_entry.insert(0, self.data["comment_settings"].get("max_likes", 100))
        self.max_likes_entry.grid(row=2, column=2, padx=5, pady=5)

        ctk.CTkLabel(comment_tab, text="Макс. коментарів:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=3,
                                                                                                                column=1,
                                                                                                                padx=5,
                                                                                                                pady=5)
        self.max_comments_entry = ctk.CTkEntry(comment_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.max_comments_entry.insert(0, self.data["comment_settings"].get("max_comments", 5))
        self.max_comments_entry.grid(row=3, column=2, padx=5, pady=5)

        ctk.CTkLabel(comment_tab, text="Макс. коментарів на день:", text_color="white", font=ctk.CTkFont(size=11)).grid(
            row=4, column=1, padx=5, pady=5)
        self.max_comments_per_day_entry = ctk.CTkEntry(comment_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.max_comments_per_day_entry.insert(0, self.data["comment_settings"].get("max_comments_per_day", 50))
        self.max_comments_per_day_entry.grid(row=4, column=2, padx=5, pady=5)

        ctk.CTkLabel(comment_tab, text="Макс. коментарів на пост:", text_color="white", font=ctk.CTkFont(size=11)).grid(
            row=5, column=1, padx=5, pady=5)
        self.max_comments_per_post_entry = ctk.CTkEntry(comment_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.max_comments_per_post_entry.insert(0, self.data["comment_settings"].get("max_comments_per_post", 10))
        self.max_comments_per_post_entry.grid(row=5, column=2, padx=5, pady=5)

        ctk.CTkLabel(comment_tab, text="Коментарі:", text_color="white", font=ctk.CTkFont(size=11)).grid(row=6,
                                                                                                         column=1,
                                                                                                         padx=5, pady=5)
        self.comments_text = ctk.CTkTextbox(comment_tab, height=15, width=300, fg_color="#2a2a3d", text_color="white")
        self.comments_text.insert("end", "\n".join(self.data["comment_settings"].get("comments", ["Круто"])))
        self.comments_text.grid(row=6, column=2, padx=5, pady=5, columnspan=2)
        ctk.CTkButton(comment_tab, text="Вставити", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=lambda: self.insert_from_clipboard(self.comments_text)).grid(row=6, column=4, padx=5,
                                                                                           pady=5)

        ctk.CTkLabel(comment_tab, text="Інтенсивність (коментів/год):", text_color="white",
                     font=ctk.CTkFont(size=11)).grid(row=7, column=1, padx=5, pady=5)
        self.intensity_scale = ctk.CTkSlider(comment_tab, from_=1, to=30, width=200)
        self.intensity_scale.set(self.data["comment_settings"].get("intensity", 5))
        self.intensity_scale.grid(row=7, column=2, padx=5, pady=5)
        self.intensity_value = ctk.CTkLabel(comment_tab, text=f"{int(self.intensity_scale.get())}", text_color="white",
                                            font=ctk.CTkFont(size=11))
        self.intensity_value.grid(row=7, column=3, padx=5, pady=5)
        self.intensity_scale.bind("<Motion>",
                                  lambda e: self.intensity_value.configure(text=f"{int(self.intensity_scale.get())}"))

        ctk.CTkLabel(comment_tab, text="Час роботи (хв):", text_color="white", font=ctk.CTkFont(size=11)).grid(row=8,
                                                                                                               column=1,
                                                                                                               padx=5,
                                                                                                               pady=5)
        self.comment_work_interval_entry = ctk.CTkEntry(comment_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.comment_work_interval_entry.insert(0, self.data["comment_settings"].get("work_interval", 60))
        self.comment_work_interval_entry.grid(row=8, column=2, padx=5, pady=5)

        ctk.CTkLabel(comment_tab, text="Час паузи (хв):", text_color="white", font=ctk.CTkFont(size=11)).grid(row=9,
                                                                                                              column=1,
                                                                                                              padx=5,
                                                                                                              pady=5)
        self.comment_pause_interval_entry = ctk.CTkEntry(comment_tab, fg_color="#2a2a3d", text_color="white", width=100)
        self.comment_pause_interval_entry.insert(0, self.data["comment_settings"].get("pause_interval", 60))
        self.comment_pause_interval_entry.grid(row=9, column=2, padx=5, pady=5)

        ctk.CTkLabel(comment_tab, text="Фото для коментарів:", text_color="white", font=ctk.CTkFont(size=11)).grid(
            row=10, column=1, padx=5, pady=5)
        self.photo_paths_label = ctk.CTkLabel(comment_tab, text=", ".join(
            self.data["comment_settings"]["photo_paths"]) or "Не вибрано", text_color="white",
                                              font=ctk.CTkFont(size=11))
        self.photo_paths_label.grid(row=10, column=2, columnspan=2, padx=5, pady=5)

        ctk.CTkButton(comment_tab, text="Завантажити коментарі", fg_color="#4a4a6d", hover_color="#6a6a8d",
                      text_color="white",
                      command=self.load_comments_from_file).grid(row=11, column=1, pady=5)
        ctk.CTkButton(comment_tab, text="Вибрати фото", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=self.select_photos).grid(row=11, column=2, pady=5)
        ctk.CTkButton(comment_tab, text="Видалити фото", fg_color="#4a4a6d", hover_color="#6a6a8d", text_color="white",
                      command=self.remove_photo).grid(row=11, column=3, pady=5)

        self.comment_accounts_tree.bind("<Double-1>", self.toggle_comment_select)

        ctk.CTkButton(comment_tab, text="Запустити коментування", fg_color="#4a4a6d", hover_color="#6a6a8d",
                      text_color="white",
                      command=self.start_commenting).grid(row=12, column=1, pady=10)

        comment_tab.grid_columnconfigure(0, weight=1)
        comment_tab.grid_columnconfigure(4, weight=1)

        self.update_comment_accounts()

    def setup_settings_tab(self):
        settings_tab = self.tabs["Налаштування"]

        self.super_mode_var = ctk.BooleanVar(value=self.data["settings"].get("super_mode", False))
        ctk.CTkCheckBox(settings_tab, text="Супер пупер режим", variable=self.super_mode_var,
                        command=self.toggle_super_mode,
                        fg_color="#4a4a6d", text_color="white").grid(row=0, column=1, pady=10)

        ctk.CTkCheckBox(settings_tab, text="Відображати браузер", variable=self.show_browser, text_color="white",
                        fg_color="#4a4a6d", hover_color="#6a6a8d").grid(row=1, column=1, pady=10)

    def insert_from_clipboard(self, entry):
        try:
            clipboard_text = self.root.clipboard_get()
            if clipboard_text:
                if isinstance(entry, ctk.CTkTextbox):
                    entry.insert("end", clipboard_text)
                else:
                    entry.delete(0, "end")
                    entry.insert(0, clipboard_text)
            return "break"
        except Exception as e:
            self.safe_log("GUI", f"Помилка вставки: {str(e)}")
            return "break"

    def update_accounts_tree(self):
        for item in self.accounts_tree.get_children():
            self.accounts_tree.delete(item)
        for acc in self.data["accounts"]:
            status = "☑" if acc.get("validated", False) else "☐"
            self.accounts_tree.insert("", "end",
                                      values=(acc["login"], acc.get("proxy", "Ні"), acc.get("2fa_url", "Ні"), status))

    def toggle_account_select(self, event):
        item = self.accounts_tree.identify_row(event.y)
        if item:
            login = self.accounts_tree.item(item)["values"][0]
            current = self.accounts_tree.item(item)["values"][3]
            new_status = "☑" if current == "☐" else "☐"
            for acc in self.data["accounts"]:
                if acc["login"] == login:
                    acc["validated"] = (new_status == "☑")
                    break
            self.accounts_tree.item(item, values=(login, acc.get("proxy", "Ні"), acc.get("2fa_url", "Ні"), new_status))
            save_data(self.data)

    def add_account(self):
        login = self.login_entry.get().strip()
        password = self.password_entry.get().strip()
        proxy = self.proxy_entry.get().strip() or None
        twofa_url = self.twofa_entry.get().strip() or None

        if not login or not password:
            messagebox.showerror("Помилка", "Введіть логін і пароль!")
            return

        if not self.current_fingerprint:
            messagebox.showwarning("Попередження", "Спочатку згенеруйте відбиток браузера!")
            return

        self.safe_log(login, "Початок перевірки...")
        self.manual_add_btn.configure(state="disabled")  # Вимикаємо кнопку на початку

        def on_validation_complete(validated, driver=None):
            if validated:
                self.data["accounts"].append({
                    "login": login,
                    "password": password,
                    "proxy": proxy,
                    "2fa_url": twofa_url,
                    "validated": True,
                    "fingerprint": self.current_fingerprint,
                    "warmup_stats": {
                        "days_completed": 0,
                        "days_total": 0,
                        "posts_viewed": 0,
                        "likes_made": 0
                    },
                    "comment_stats": {
                        "comments_made": 0
                    },
                    "status": "Готовий"
                })
                save_data(self.data)
                self.update_accounts_tree()
                self.update_warmup_accounts()
                self.update_comment_accounts()
                self.safe_log(login, "Додано автоматично, валідність: Так")
                self.clear_entries()
                self.current_fingerprint = None
                self.fingerprint_label.configure(text="Натисніть 'Генерувати', щоб створити відбиток\n\n\n\n")
            else:
                self.safe_log(login, "Автоматична авторизація не вдалася. Ви можете завершити вручну.")
                self.pending_driver = driver  # Зберігаємо драйвер для ручного завершення
                self.manual_add_btn.configure(state="normal")  # Активуємо кнопку для ручного додавання

        validate_account_async(login, password, proxy, twofa_url, on_validation_complete, self.log_text, self.root)

    def manual_add_account(self):
        if not hasattr(self, 'pending_driver') or self.pending_driver is None:
            messagebox.showwarning("Попередження", "Немає активного браузера для ручного завершення!")
            return

        login = self.login_entry.get().strip()
        password = self.password_entry.get().strip()
        proxy = self.proxy_entry.get().strip() or None
        twofa_url = self.twofa_entry.get().strip() or None

        if not login or not password:
            messagebox.showerror("Помилка", "Введіть логін і пароль!")
            return

        try:
            # Зберігаємо кукі з браузера
            from auth import save_cookies
            save_cookies(self.pending_driver, login, self.log_text)
            self.data["accounts"].append({
                "login": login,
                "password": password,
                "proxy": proxy,
                "2fa_url": twofa_url,
                "validated": True,
                "fingerprint": self.current_fingerprint,
                "warmup_stats": {
                    "days_completed": 0,
                    "days_total": 0,
                    "posts_viewed": 0,
                    "likes_made": 0
                },
                "comment_stats": {
                    "comments_made": 0
                },
                "status": "Готовий"
            })
            save_data(self.data)
            self.update_accounts_tree()
            self.update_warmup_accounts()
            self.update_comment_accounts()
            self.safe_log(login, "Додано вручну, валідність: Так")
            self.pending_driver.quit()
            self.pending_driver = None
            self.manual_add_btn.configure(state="disabled")
            self.clear_entries()
            self.current_fingerprint = None
            self.fingerprint_label.configure(text="Натисніть 'Генерувати', щоб створити відбиток\n\n\n\n")
        except Exception as e:
            self.safe_log(login, f"Помилка при ручному додаванні: {str(e)}")
            messagebox.showerror("Помилка", f"Не вдалося додати акаунт вручну: {str(e)}")

    def edit_account(self):
        selected = self.accounts_tree.selection()
        if not selected:
            messagebox.showwarning("Попередження", "Виберіть акаунт для редагування!")
            return
        login = self.accounts_tree.item(selected[0])["values"][0]
        for acc in self.data["accounts"]:
            if acc["login"] == login:
                self.login_entry.delete(0, "end")
                self.login_entry.insert(0, acc["login"])
                self.password_entry.delete(0, "end")
                self.password_entry.insert(0, acc["password"])
                self.proxy_entry.delete(0, "end")
                if acc.get("proxy"):
                    self.proxy_entry.insert(0, acc["proxy"])
                self.twofa_entry.delete(0, "end")
                if acc.get("2fa_url"):
                    self.twofa_entry.insert(0, acc["2fa_url"])
                self.current_fingerprint = acc.get("fingerprint")
                if self.current_fingerprint:
                    languages_display = ', '.join([lang for sublist in self.current_fingerprint['languages'] for lang in sublist])
                    fingerprint_text = (f"User-Agent: {self.current_fingerprint['user_agent']}\n"
                                       f"Viewport: {self.current_fingerprint['viewport']['width']}x{self.current_fingerprint['viewport']['height']}\n"
                                       f"Languages: {languages_display}\n"
                                       f"Platform: {self.current_fingerprint['platform']}\n"
                                       f"Timezone Offset: {self.current_fingerprint['timezone_offset']}")
                    self.fingerprint_label.configure(text=fingerprint_text)
                self.data["accounts"].remove(acc)
                save_data(self.data)
                self.update_accounts_tree()
                break

    def delete_account(self):
        selected = self.accounts_tree.selection()
        if not selected:
            messagebox.showwarning("Попередження", "Виберіть акаунт для видалення!")
            return
        login = self.accounts_tree.item(selected[0])["values"][0]
        if login in self.running_threads:
            messagebox.showwarning("Попередження", "Зупиніть задачу для цього акаунта перед видаленням!")
            return
        if messagebox.askyesno("Підтвердження", f"Видалити акаунт {login}?"):
            delete_account(login, self.log_text)
            self.data["accounts"] = [acc for acc in self.data["accounts"] if acc["login"] != login]
            save_data(self.data)
            self.update_accounts_tree()
            self.update_warmup_accounts()
            self.update_comment_accounts()

    def clear_entries(self):
        self.login_entry.delete(0, "end")
        self.password_entry.delete(0, "end")
        self.proxy_entry.delete(0, "end")
        self.twofa_entry.delete(0, "end")

    def toggle_comment_select(self, event):
        item = self.comment_accounts_tree.identify_row(event.y)
        if item:
            login = self.comment_accounts_tree.item(item)["values"][0]
            current = self.comment_accounts_tree.item(item)["values"][1]
            self.comment_accounts_tree.item(item, values=(
                login,
                "☑" if current == "☐" else "☐",
                self.comment_accounts_tree.item(item)["values"][2],
                self.comment_accounts_tree.item(item)["values"][3],
                self.comment_accounts_tree.item(item)["values"][4]
            ))

    def update_comment_accounts(self):
        for item in self.comment_accounts_tree.get_children():
            self.comment_accounts_tree.delete(item)
        for acc in self.data["accounts"]:
            stats = acc["comment_stats"]
            status = acc.get("status", "Готовий")
            action_text = "Дія" if status != "Готовий" else "Немає дії"
            self.comment_accounts_tree.insert("", "end", values=(
                acc["login"],
                "☐",
                stats["comments_made"],
                status,
                action_text
            ))

    def load_comments_from_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    comments = [line.strip() for line in f if line.strip()]
                self.comments_text.delete("1.0", "end")
                self.comments_text.insert("end", "\n".join(comments))
                self.data["comment_settings"]["comments"] = comments
                save_data(self.data)
            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося завантажити коментарі: {str(e)}")

    def select_photos(self):
        files = filedialog.askopenfilenames(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if files:
            self.data["comment_settings"]["photo_paths"] = list(files)
            self.photo_paths_label.configure(text=", ".join(self.data["comment_settings"]["photo_paths"]))
            save_data(self.data)

    def remove_photo(self):
        self.data["comment_settings"]["photo_paths"] = []
        self.photo_paths_label.configure(text="Не вибрано")
        save_data(self.data)

    def start_commenting(self):
        selected = [self.comment_accounts_tree.item(item)["values"][0] for item in
                    self.comment_accounts_tree.get_children() if
                    self.comment_accounts_tree.item(item)["values"][1] == "☑"]
        if not selected:
            messagebox.showwarning("Попередження", "Виберіть хоча б один акаунт!")
            return

        try:
            min_likes = int(self.min_likes_entry.get())
            max_likes = int(self.max_likes_entry.get())
            max_comments = int(self.max_comments_entry.get())
            max_comments_per_day = int(self.max_comments_per_day_entry.get())
            max_comments_per_post = int(self.max_comments_per_post_entry.get())
            intensity = int(self.intensity_scale.get())
            work_interval = int(self.comment_work_interval_entry.get())
            pause_interval = int(self.comment_pause_interval_entry.get())
            comments = self.comments_text.get("1.0", "end").strip().split("\n")
            comments = [c.strip() for c in comments if c.strip()]

            if (min_likes < 0 or max_likes < min_likes or max_comments <= 0 or max_comments_per_day <= 0 or
                    max_comments_per_post <= 0 or intensity <= 0 or work_interval <= 0 or pause_interval <= 0):
                raise ValueError("Некоректні параметри коментування!")
            if not comments:
                raise ValueError("Введіть хоча б один коментар!")
        except ValueError as e:
            messagebox.showerror("Помилка", f"Перевірте введені значення: {str(e)}")
            return

        self.data["comment_settings"].update({
            "min_likes": min_likes,
            "max_likes": max_likes,
            "max_comments": max_comments,
            "max_comments_per_day": max_comments_per_day,
            "max_comments_per_post": max_comments_per_post,
            "intensity": intensity,
            "comments": comments,
            "work_interval": work_interval,
            "pause_interval": pause_interval
        })
        save_data(self.data)

        self.stop_btn.configure(state="normal")
        for login in selected:
            if login in self.running_threads:
                continue
            account = next(acc for acc in self.data["accounts"] if acc["login"] == login)
            account["status"] = "В роботі"
            stop_event = threading.Event()
            pause_event = threading.Event()
            thread = threading.Thread(target=comment_posts, args=(account, stop_event, pause_event,
                                                                  min_likes, max_likes,
                                                                  max_comments, max_comments_per_day,
                                                                  max_comments_per_post,
                                                                  intensity, comments,
                                                                  self.data["comment_settings"]["photo_paths"],
                                                                  self.log_text,
                                                                  self.show_browser.get(),
                                                                  self,
                                                                  work_interval,
                                                                  pause_interval), daemon=True)
            self.running_threads[login] = (thread, stop_event, pause_event, "commenting", None)
            thread.start()
            self.safe_log(login, "Запущено коментування.")
            self.update_comment_accounts()

    def stop_account(self, login, task_type):
        if login in self.running_threads:
            thread, stop_event, pause_event, running_task_type, driver = self.running_threads[login]
            if running_task_type == task_type:
                stop_event.set()
                pause_event.clear()
                thread.join(timeout=5)
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                del self.running_threads[login]
                for acc in self.data["accounts"]:
                    if acc["login"] == login:
                        acc["status"] = "Готовий"
                        break
                if task_type == "warmup":
                    self.update_warmup_accounts()
                elif task_type == "commenting":
                    self.update_comment_accounts()
                self.safe_log(login, f"Задача {task_type} зупинена.")
                if not self.running_threads:
                    self.stop_btn.configure(state="disabled")

    def stop_all(self):
        for login in list(self.running_threads.keys()):
            thread, stop_event, pause_event, task_type, driver = self.running_threads[login]
            stop_event.set()
            pause_event.clear()
            thread.join(timeout=5)
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            del self.running_threads[login]
            for acc in self.data["accounts"]:
                if acc["login"] == login:
                    acc["status"] = "Готовий"
                    break
            self.safe_log(login, f"Задача {task_type} зупинена.")
        self.update_warmup_accounts()
        self.update_comment_accounts()
        self.stop_btn.configure(state="disabled")

    def toggle_super_mode(self):
        self.data["settings"]["super_mode"] = self.super_mode_var.get()
        save_data(self.data)
        self.safe_log("Налаштування", f"Супер пупер режим: {self.data['settings']['super_mode']}")

    def safe_log(self, login, message):
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_interval:
            save_data(self.data)
            self.last_save_time = current_time
        self.log_text.insert("end", f"[{login}] {message}\n")
        self.log_scroll_to_end()

if __name__ == "__main__":
    root = ctk.CTk()
    app = ThreadsBotGUI(root)
    root.mainloop()