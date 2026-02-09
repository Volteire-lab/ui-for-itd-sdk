import customtkinter as ctk
from threading import Thread
from uuid import UUID
from tkinter import filedialog
import warnings
from PIL import Image, ImageSequence, ImageTk
import os

# Костыль потому что у меня 3.12
if not hasattr(warnings, "deprecated"):
    warnings.deprecated = lambda *args, **kwargs: (lambda f: f)

# буквально client.py под ctk, а чо вы мне сделаете
from itd.client import Client
from itd.enums import PostsTab

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class ITDApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ITD.com — клиент (refresh через cookies)")
        self.geometry("1050x680")

        # сайдбар
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")

        ctk.CTkLabel(
            self.sidebar,
            text="Вход через cookies (refresh)",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            self.sidebar,
            text="Вставь строку cookies из браузера (DevTools → Application → Cookies)",
            wraplength=260,
        ).pack(padx=15, pady=(0, 10))

        # Поле для cookies
        self.cookies_box = ctk.CTkTextbox(self.sidebar, height=120)
        self.cookies_box.pack(padx=15, pady=8, fill="x")
        self.cookies_box.insert(
            "1.0",
            "пример: session=...; refreshToken=...; csrftoken=...",
        )

        self.login_btn = ctk.CTkButton(self.sidebar, text="Подключиться", command=self.connect)
        self.login_btn.pack(padx=15, pady=12, fill="x")

        self.status_label = ctk.CTkLabel(self.sidebar, text="Не подключён", text_color="gray")
        self.status_label.pack(pady=6)

        # Кнопки действий
        self.refresh_btn = ctk.CTkButton(
            self.sidebar, text="🔄 Обновить ленту", command=self.load_feed, state="disabled"
        )
        self.refresh_btn.pack(padx=15, pady=6, fill="x")

        self.new_post_btn = ctk.CTkButton(
            self.sidebar, text="➕ Новый пост", command=self.open_post_window, state="disabled"
        )
        self.new_post_btn.pack(padx=15, pady=6, fill="x")

        self.me_btn = ctk.CTkButton(
            self.sidebar, text="👤 Профиль (me)", command=self.load_me, state="disabled"
        )
        self.me_btn.pack(padx=15, pady=6, fill="x")

        # баннер
        self.banner_btn = ctk.CTkButton(
            self.sidebar,
            text="🖼️ Заменить баннер (с превью + GIF)",
            command=self.change_banner,
            state="disabled",
        )
        self.banner_btn.pack(padx=15, pady=6, fill="x")

        # мейн
        self.main = ctk.CTkFrame(self)
        self.main.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        top_bar = ctk.CTkFrame(self.main)
        top_bar.pack(fill="x", pady=(0, 8))

        self.tab_var = ctk.StringVar(value="POPULAR")
        ctk.CTkRadioButton(
            top_bar, text="Популярное", variable=self.tab_var, value="POPULAR", command=self.load_feed
        ).pack(side="left", padx=6)
        ctk.CTkRadioButton(
            top_bar, text="Подписки", variable=self.tab_var, value="SUBSCRIPTIONS", command=self.load_feed
        ).pack(side="left", padx=6)

        self.feed = ctk.CTkTextbox(self.main, wrap="word")
        self.feed.pack(fill="both", expand=True)
        self.feed.insert("end", "Подключись через cookies, чтобы увидеть ленту.\n")

        self.client: Client | None = None

        # Для гифочек
        self._gif_frames = []
        self._gif_label = None

    # авторизация
    def connect(self):
        cookies = self.cookies_box.get("1.0", "end").strip()
        if not cookies or len(cookies) < 20:
            self.status_label.configure(text="Вставь корректные cookies", text_color="red")
            return

        self.status_label.configure(text="Подключаюсь...", text_color="orange")
        self.login_btn.configure(state="disabled")

        def worker():
            try:
                self.client = Client(cookies=cookies)
                me = self.client.get_me()
                ok = True
                username = me.username
            except Exception as e:
                ok = False
                err = str(e)

            def finish():
                self.login_btn.configure(state="normal")
                if ok:
                    self.status_label.configure(
                        text=f"Подключён как @{username}", text_color="green"
                    )
                    self.refresh_btn.configure(state="normal")
                    self.new_post_btn.configure(state="normal")
                    self.me_btn.configure(state="normal")
                    self.banner_btn.configure(state="normal")
                    self.load_feed()
                else:
                    self.status_label.configure(text=f"Ошибка: {err}", text_color="red")

            self.after(0, finish)

        Thread(target=worker, daemon=True).start()

    # новостная лента (пока текст, я хз, чет придумаю с картиночками)
    def load_feed(self):
        if not self.client:
            return

        self.feed.delete("1.0", "end")
        self.feed.insert("end", "Загружаю ленту...\n\n")

        tab = PostsTab.POPULAR if self.tab_var.get() == "POPULAR" else PostsTab.SUBSCRIPTIONS

        def worker():
            try:
                posts, _ = self.client.get_posts(cursor=0, tab=tab)
                lines = []
                for p in posts:
                    text = (p.content or "").replace("\n", " ")
                    preview = text[:220] + ("..." if len(text) > 220 else "")
                    lines.append(
                        f"[{p.id}] @{p.author.username} — {p.author.display_name}\n"
                        f"{preview}\n"
                        f"❤️ {p.likes_count}   💬 {p.comments_count}\n"
                        f"{'-'*70}\n"
                    )
                out = "\n".join(lines) if lines else "(постов нет)"
            except Exception as e:
                out = f"Ошибка загрузки: {e}"

            def finish():
                self.feed.delete("1.0", "end")
                self.feed.insert("end", out)

            self.after(0, finish)

        Thread(target=worker, daemon=True).start()

    # профиль
    def load_me(self):
        if not self.client:
            return

        def worker():
            try:
                me = self.client.get_me()
                txt = (
                    f"ПРОФИЛЬ:\n"
                    f"Username: @{me.username}\n"
                    f"Name: {me.display_name}\n"
                    f"Bio: {me.bio or ''}\n"
                    f"Followers: {me.followers_count}\n"
                    f"Following: {me.following_count}\n"
                )
            except Exception as e:
                txt = f"Ошибка: {e}"

            def finish():
                self.feed.delete("1.0", "end")
                self.feed.insert("end", txt)

            self.after(0, finish)

        Thread(target=worker, daemon=True).start()

    # првьею и гиф
    def change_banner(self):
        if not self.client:
            return

        path = filedialog.askopenfilename(
            title="Выбери изображение баннера",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.gif")],
        )
        if not path:
            return

        # Окно превью
        win = ctk.CTkToplevel(self)
        win.title("Превью баннера")
        win.geometry("700x350")

        preview_frame = ctk.CTkFrame(win)
        preview_frame.pack(fill="both", expand=True, padx=10, pady=10)

        lbl = ctk.CTkLabel(preview_frame, text="")
        lbl.pack(expand=True)
        self._gif_label = lbl

        info = ctk.CTkLabel(win, text=os.path.basename(path))
        info.pack(pady=4)

        # Загрузка изображения
        img = Image.open(path)

        # Подгоняем под баннер-формат для превью
        img = img.resize((640, 180), Image.LANCZOS)

        # Если GIF — готовим анимацию
        if path.lower().endswith(".gif"):
            self._gif_frames = []
            for frame in ImageSequence.Iterator(img):
                frame = frame.convert("RGBA")
                self._gif_frames.append(ImageTk.PhotoImage(frame))

            def animate(idx=0):
                if not self._gif_frames:
                    return
                lbl.configure(image=self._gif_frames[idx])
                win.after(80, animate, (idx + 1) % len(self._gif_frames))

            animate()
        else:
            photo = ImageTk.PhotoImage(img)
            lbl.configure(image=photo)
            lbl.image = photo  # держим ссылку

        btn_frame = ctk.CTkFrame(win)
        btn_frame.pack(pady=8)

        def cancel():
            win.destroy()

        def confirm():
            win.destroy()
            self._upload_banner(path)

        ctk.CTkButton(btn_frame, text="Отмена", command=cancel).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Загрузить этот баннер", command=confirm).pack(side="left", padx=10)

    def _upload_banner(self, path: str):
        self.status_label.configure(text="Загружаю баннер...", text_color="orange")

        def worker():
            try:
                uploaded = self.client.upload_file(os.path.basename(path), open(path, "rb"))
                file_id = uploaded.id
                self.client.update_profile(banner_id=file_id)
                ok = True
            except Exception as e:
                ok = False
                err = str(e)

            def finish():
                if ok:
                    self.status_label.configure(text="Баннер обновлён ✅", text_color="green")
                else:
                    self.status_label.configure(text=f"Ошибка баннера: {err}", text_color="red")

            self.after(0, finish)

        Thread(target=worker, daemon=True).start()

    # новый пост
    def open_post_window(self):
        if not self.client:
            return

        win = ctk.CTkToplevel(self)
        win.title("Новый пост")
        win.geometry("600x450")

        text = ctk.CTkTextbox(win, height=300)
        text.pack(fill="both", expand=True, padx=10, pady=10)

        status = ctk.CTkLabel(win, text="", text_color="gray")
        status.pack(pady=4)

        def send():
            content = text.get("1.0", "end").strip()
            if not content:
                status.configure(text="Текст не может быть пустым", text_color="red")
                return

            status.configure(text="Отправляю...", text_color="orange")

            def worker():
                try:
                    self.client.create_post(content)
                    ok = True
                except Exception as e:
                    ok = False
                    msg = str(e)

                def finish():
                    if ok:
                        win.destroy()
                        self.load_feed()
                    else:
                        status.configure(text=f"Ошибка: {msg}", text_color="red")

                self.after(0, finish)

            Thread(target=worker, daemon=True).start()

        ctk.CTkButton(win, text="Опубликовать", command=send).pack(pady=10)


if __name__ == "__main__":
    app = ITDApp()
    app.mainloop()
