import customtkinter as ctk
import os
from tkinter import filedialog, Label, Canvas
from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageColor
import colorsys


class ColorChangerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()

        # 背景画像の読み込み（複数候補 + フォールバック）
        bg_candidates = [
            os.path.join("UI_Image", "tail.png"),
            os.path.join("Ui_image", "tail.png"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "UI_Image", "tail.png"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "Ui_image", "tail.png"),
        ]
        self.bg_photo = None
        for p in bg_candidates:
            if os.path.exists(p):
                try:
                    self.bg_image = Image.open(p).resize((2880, 1620))
                    self.bg_photo = ImageTk.PhotoImage(self.bg_image)
                    break
                except Exception:
                    pass
        if self.bg_photo is not None:
            self.bg_label = Label(self, image=self.bg_photo)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        else:
            # 画像がない場合は単色背景
            self.configure(bg="#f0f0f0")

        # アプリエリア生成
        self.title("画像編集アプリ")
        self.geometry(f"{w}x{h}+0+0")
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")
        # 高DPI環境でも座標ズレしないようスケーリングを固定
        try:
            ctk.set_widget_scaling(1.0)
            ctk.set_window_scaling(1.0)
        except Exception:
            pass

        self.image = None
        self.original_image = None
        self.tk_image = None
        self.current_color = None
        self.current_intensity = 1.0
        self.current_hue_value = 0.0
        self.instructions_window = None  # 機能説明ウィンドウの参照
        
        # 塗りつぶし用
        self.fill_mode_active = False
        self.fill_color = (255, 0, 0) # デフォルト赤
        self.displayed_size = (0, 0)
        self.last_display_resized = None  # 表示用縮小画像の保持（デバッグ用）
        # 全体用の履歴（Undo/Redo）
        self.history = []  # 過去の画像（戻る用）
        self.future = []   # 先の画像（進む用）

        # --- デコレーション（ステッカー）関連 ---
        # main_frame 生成前のため一旦 None にしておく
        self.decoration_section_frame = None
        self.decoration_visible = False
        self.decoration_mode_active = False
        # キャンバス上に配置したステッカー管理
        # 各要素: {"pil": PIL.Image, "photo": ImageTk.PhotoImage, "id": int, "x_ratio": float, "y_ratio": float, "size_ratio": float}
        self.canvas_stickers = []
        # 現在選択中のステッカー（ドラッグ準備用）
        self.active_sticker_pil = None
        # プレビュー（ドラッグ中）用キャンバスアイテムID
        self.drag_preview_id = None
        # ステッカーサイズ（表示画像幅に対する割合）
        self.sticker_size_ratio = 0.18
        # ステッカー用履歴
        self.sticker_history = []
        self.sticker_future = []

        # --- メインフレーム ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=(280, 70), padx=10, fill="both", expand=True)
        # main_frame 生成後にデコレーションセクションフレームを作成
        self.decoration_section_frame = ctk.CTkFrame(self.main_frame)

        # --- 画像表示領域（tkinter.Canvas） ---
        self.canvas = Canvas(self.main_frame, width=500, height=500, bg="#f0f0f0", highlightthickness=0)
        self.canvas.pack(pady=10)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        # デコレーションのドラッグ用（塗りモードとは独立して判定）
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas_image_id = None

        # --- メインボタン ---
        self.btn_frame = ctk.CTkFrame(self.main_frame)
        self.btn_frame.pack(pady=10)

        ctk.CTkButton(self.btn_frame, text="機能説明", command=self.show_instructions).pack(side="left", padx=5)
        ctk.CTkButton(self.btn_frame, text="画像を開く", command=self.open_image).pack(side="left", padx=5)
        ctk.CTkButton(self.btn_frame, text="カラーフィルター ▼", command=self.toggle_color_buttons).pack(side="left", padx=5)
        ctk.CTkButton(self.btn_frame, text="塗りつぶし ▼", command=self.toggle_fill_options).pack(side="left", padx=5)
        ctk.CTkButton(self.btn_frame, text="ふち取り", command=self.frame_outline).pack(side="left", padx=5)
        ctk.CTkButton(self.btn_frame, text="デコレーション", command=self.cover_decoration).pack(side="left", padx=5)
        ctk.CTkButton(self.btn_frame, text="戻る", command=self.undo).pack(side="left", padx=5)
        ctk.CTkButton(self.btn_frame, text="進む", command=self.redo).pack(side="left", padx=5)
        ctk.CTkButton(self.btn_frame, text="リセット", command=self.reset_colors).pack(side="left", padx=5)
        ctk.CTkButton(self.btn_frame, text="保存", command=self.save_image).pack(side="left", padx=5)

        # --- カラーセクション（色ボタン＋スライダー） ---
        self.color_section_frame = ctk.CTkFrame(self.main_frame)
        self.color_btn_frame = ctk.CTkFrame(self.color_section_frame)
        self.slider_frame = ctk.CTkFrame(self.color_section_frame)

        self.color_btn_visible = False

        self.add_color_buttons()
        self.add_color_slider()       # ★ 追加：色相スライダー
        self.add_intensity_slider()   # 強度スライダー
        
        # --- 塗りつぶしセクション ---
        self.fill_section_frame = ctk.CTkFrame(self.main_frame)
        self.fill_options_visible = False
        self.add_fill_ui()

        # ショートカットキー（Ctrl+Z / Ctrl+Y）
        try:
            self.bind_all("<Control-z>", lambda e: self.undo())
            self.bind_all("<Control-y>", lambda e: self.redo())
        except Exception:
            pass

    def show_instructions(self):
        # ウィンドウが既に開いている場合は閉じる（トグル動作）
        if self.instructions_window is not None and self.instructions_window.winfo_exists():
            self.instructions_window.destroy()
            self.instructions_window = None
            return

        # 他セクションを閉じて重複表示を防止
        self.close_all_sections()

        # 新しいウィンドウを作成
        self.instructions_window = ctk.CTkToplevel(self)
        self.instructions_window.title("機能説明")
        self.instructions_window.geometry("500x400+160+310")
        self.instructions_window.attributes("-topmost", True) # 最前面に表示

        # ウィンドウが閉じられたときの処理
        def on_close():
            self.instructions_window.destroy()
            self.instructions_window = None
        
        self.instructions_window.protocol("WM_DELETE_WINDOW", on_close)

        instructions = (
            "【機能説明】\n"
            "1. 『画像を開く』ボタンで編集したい画像を選択します。\n"
            "2. 『カラーフィルター ▼』ボタンを押して、色変更セクションを表示します。\n"
            "3. 色ボタンをクリックして、特定の色を強調します。\n"
            "4. 色相スライダーで任意の色相に調整できます。\n"
            "5. 強さスライダーで色の強度を調整します。\n"
            "6. 『塗りつぶし ▼』ボタンで塗りつぶしオプションを表示します。\n"
            "7. 『ふち取り』ボタンで黒い部分を抽出します。\n"
            "8. 『デコレーション』ボタンでステッカーを画像上に追加します。\n"
            "9. 『進む』で作業を1つ前の状態に、『戻る』で1つ後ろの状態にできます。\n"
            "10. 『リセット』ボタンで元の画像に戻せます。\n"
            "11. 『保存』ボタンで編集した画像を保存します。\n\n"
            "【注意事項】\n"
            "※ 生成した画像は個人利用の範囲にとどめてください。\n"
            "※ 外枠の線が太いイラストをおすすめします。\n"
            "※ 画像の解像度が高いものを使用してください\n"
            
        )
        
        ctk.CTkLabel(
            self.instructions_window, 
            text=instructions, 
            text_color="lightgray",
            justify="left",
            padx=20,
            pady=20,
            font=("Meiryo", 14)
        ).pack(expand=True, fill="both")

    # -----------------------------------------
    # セクション一括クローズ（相互排他表示のため）
    # -----------------------------------------
    def close_all_sections(self, exclude: str | None = None):
        # 機能説明
        if exclude != "instructions":
            if self.instructions_window is not None and self.instructions_window.winfo_exists():
                self.instructions_window.destroy()
                self.instructions_window = None
        # 色変更セクション
        if exclude != "color":
            if self.color_btn_visible:
                self.color_section_frame.pack_forget()
                self.color_btn_visible = False
        # 塗りつぶしセクション
        if exclude != "fill":
            if self.fill_options_visible:
                self.fill_section_frame.pack_forget()
                self.fill_options_visible = False
                self.fill_mode_active = False
        # デコレーションセクション
        if exclude != "decoration":
            if self.decoration_visible:
                self.decoration_section_frame.pack_forget()
                self.decoration_visible = False
                self.decoration_mode_active = False
                self.active_sticker_pil = None
                # プレビューを消す
                if self.drag_preview_id is not None:
                    try:
                        self.canvas.delete(self.drag_preview_id)
                    except Exception:
                        pass
                    self.drag_preview_id = None

    # -----------------------------------------
    # カ ラ ー ボ タ ン
    # -----------------------------------------
    def add_color_buttons(self):
        # 画像加工アプリ.py と同じスタイルの色付きボタンを作成
        color_buttons = [
            ("赤", "#ff0000", "red"),
            ("青", "#0000ff", "blue"),
            ("緑", "#00a000", "green"),
            ("黄", "#ffff00", "yellow"),
            ("紫", "#800080", "purple"),
            ("橙", "#ffa500", "orange"),
            ("白", "#ffffff", "white"),
            ("桃", "#ff69b4", "pink"),
        ]

        for text, color, key in color_buttons:
            hover = (
                "#ff7f7f" if color == "#ff0000" else
                "#7fbfff" if color == "#0000ff" else
                "#bfff7f" if color == "#00a000" else
                "#ffff7f" if color == "#ffff00" else
                "#bf7fff" if color == "#800080" else
                "#ffcc80" if color == "#ffa500" else
                "#c0c0c0" if color == "#ffffff" else
                "#ffc0cb"
            )
            ctk.CTkButton(
                self.color_btn_frame,
                text=text,
                fg_color=color,
                text_color="black" if color in ("#ffff00", "#ffffff") else "white",
                hover_color=hover,
                command=lambda c=key: self.select_color(c),
                width=60,
            ).pack(side="left", padx=4, pady=5)

    def load_button_image(self, filename: str, size=(140, 48)):
        """ボタン用画像を複数候補パスから検索して読み込む。見つからなければ None。
        優先パス: Ui_image/buttons, Ui_image, UI_Image/buttons, UI_Image
        """
        base_dir = os.path.dirname(os.path.dirname(__file__))
        candidates = [
            os.path.join(base_dir, "Ui_image", "buttons", filename),
            os.path.join(base_dir, "Ui_image", filename),
            os.path.join(base_dir, "UI_Image", "buttons", filename),
            os.path.join(base_dir, "UI_Image", filename),
            os.path.join("Ui_image", "buttons", filename),
            os.path.join("Ui_image", filename),
            os.path.join("UI_Image", "buttons", filename),
            os.path.join("UI_Image", filename),
        ]
        for path in candidates:
            if os.path.exists(path):
                img = Image.open(path)
                return ctk.CTkImage(light_image=img.resize(size), dark_image=img.resize(size), size=size)
        return None

    # -----------------------------------------
    # ★ 色 相 ス ラ イ ダ ー
    # -----------------------------------------
    def add_color_slider(self):
        ctk.CTkLabel(self.slider_frame, text="色相（Hue）", text_color="lightgray")\
            .pack(side="left", padx=5)

        self.hue_slider = ctk.CTkSlider(
            self.slider_frame,
            from_=0,
            to=360,
            number_of_steps=360,
            command=self.update_hue
        )
        self.hue_slider.set(0)
        self.hue_slider.pack(side="left", padx=10, fill="x", expand=True)

    def update_hue(self, value):
        self.current_color = "custom_hue"
        self.current_hue_value = float(value)
        self.apply_color_change()

    # -----------------------------------------
    # 強 度 ス ラ イ ダ ー
    # -----------------------------------------
    def add_intensity_slider(self):
        ctk.CTkLabel(self.slider_frame, text="強さ（×）", text_color="lightgray")\
            .pack(side="left", padx=5)

        self.intensity_slider = ctk.CTkSlider(
            self.slider_frame,
            from_=0.5,
            to=5.0,
            number_of_steps=45,
            command=self.update_intensity
        )
        self.intensity_slider.set(1.0)
        self.intensity_slider.pack(side="left", padx=10, fill="x", expand=True)

    def update_intensity(self, value):
        self.current_intensity = float(value)
        if self.current_color:
            self.apply_color_change()

    # -----------------------------------------
    # セクション表示切替
    # -----------------------------------------
    def toggle_color_buttons(self):
        if self.color_btn_visible:
            # 開いていれば閉じる
            self.color_section_frame.pack_forget()
            self.color_btn_visible = False
        else:
            # 他セクションを閉じてから開く
            self.close_all_sections(exclude="color")
            self.color_section_frame.pack(pady=5)
            self.color_btn_frame.pack()
            self.slider_frame.pack(pady=5, fill="x")
            self.color_btn_visible = True

    # -----------------------------------------
    # 色選択（ボタン）
    # -----------------------------------------
    def select_color(self, color_name):
        self.current_color = color_name
        self.apply_color_change()

    # -----------------------------------------
    # 色変換のメイン処理
    # -----------------------------------------
    def apply_color_change(self):
        if not self.image:
            return

        # ★ カスタム色：色相スライダーで変換 ★
        if self.current_color == "custom_hue":
            hue = self.current_hue_value
            intensity = self.current_intensity

            # HSV → RGB
            r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 1.0, 1.0)

            r_mul = r * 3 * intensity
            g_mul = g * 3 * intensity
            b_mul = b * 3 * intensity

            self.enhance_color(r_mul, g_mul, b_mul)
            return

        # 既存のプリセット色
        factors = {
            "red": (self.current_intensity * 3, 1, 1),
            "blue": (1, 1, self.current_intensity * 3),
            "green": (1, self.current_intensity * 3, 1),
            "yellow": (self.current_intensity * 2.6, self.current_intensity * 2.6, 1),
            "purple": (self.current_intensity * 3, 1, self.current_intensity * 3),
            "orange": (self.current_intensity * 3.6, self.current_intensity * 2.2, 1),
            "pink": (self.current_intensity * 3.6, self.current_intensity * 1.6, self.current_intensity * 2.2),
            "white": (self.current_intensity * 3, self.current_intensity * 3, self.current_intensity * 3),
        }

        r_mul, g_mul, b_mul = factors[self.current_color]
        self.enhance_color(r_mul, g_mul, b_mul)

    # -----------------------------------------
    # 共通画像処理
    # -----------------------------------------
    def open_image(self):
        # 画像選択時は他セクションを閉じる & 塗り履歴クリア
        self.close_all_sections()
        file_path = filedialog.askopenfilename(filetypes=[("画像ファイル", "*.jpg *.png *.jpeg *.bmp")])
        if file_path:
            self.image = Image.open(file_path).convert("RGB")
            self.original_image = self.image.copy()
            self.history.clear()
            self.future.clear()
            # ステッカーもクリア
            try:
                for st in self.canvas_stickers:
                    try:
                        self.canvas.delete(st.get("id"))
                    except Exception:
                        pass
                self.canvas_stickers.clear()
                self.sticker_history.clear()
                self.sticker_future.clear()
                self.active_sticker_pil = None
                if self.drag_preview_id is not None:
                    try:
                        self.canvas.delete(self.drag_preview_id)
                    except Exception:
                        pass
                    self.drag_preview_id = None
            except Exception:
                pass
            self.display_image()

    def display_image(self):
        resized = self.image.copy()
        resized.thumbnail((500, 500))
        self.tk_image = ImageTk.PhotoImage(resized)
        # 表示サイズを記録
        w_disp, h_disp = resized.size
        self.displayed_size = (w_disp, h_disp)
        # Canvas サイズを画像に合わせる
        self.canvas.configure(width=w_disp, height=h_disp)
        # 初回はアイテムを作成、2回目以降は更新
        if self.canvas_image_id is None:
            self.canvas_image_id = self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        else:
            self.canvas.itemconfig(self.canvas_image_id, image=self.tk_image)
        # デバッグ用に表示画像も保持（クリック位置のマーカー描画に使う）
        self.last_display_resized = resized.copy()
        # ステッカーを現在の表示サイズに合わせて再配置
        self.update_stickers_for_new_display()

    def show_click_marker(self, x_disp: int, y_disp: int, color=(255, 0, 0)):
        """表示中の縮小画像上にクリック位置のマーカー（小さな円）を描画し、キャンバスに反映する。"""
        if self.last_display_resized is None:
            return
        img_dbg = self.last_display_resized.copy()
        draw = ImageDraw.Draw(img_dbg)
        r = 6
        # 円の枠線を描画（視認性のため白縁＋赤枠）
        draw.ellipse((x_disp - r - 1, y_disp - r - 1, x_disp + r + 1, y_disp + r + 1), outline=(255, 255, 255), width=2)
        draw.ellipse((x_disp - r, y_disp - r, x_disp + r, y_disp + r), outline=color, width=2)
        # 更新（Canvas の画像アイテムを書き換え）
        self.tk_image = ImageTk.PhotoImage(img_dbg)
        if self.canvas_image_id is None:
            self.canvas_image_id = self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        else:
            self.canvas.itemconfig(self.canvas_image_id, image=self.tk_image)

    def reset_colors(self):
        # 実行時は他セクションを閉じる & 塗り履歴クリア
        self.close_all_sections()
        if self.original_image:
            # 戻れるように履歴を積む
            self.push_history()
            self.image = self.original_image.copy()
            self.display_image()
            self.current_color = None
            self.intensity_slider.set(1.0)
            self.hue_slider.set(0)
            # ステッカーもリセットに反映（全削除）
            try:
                for st in self.canvas_stickers:
                    try:
                        self.canvas.delete(st.get("id"))
                    except Exception:
                        pass
                self.canvas_stickers.clear()
                # ステッカー履歴もクリア
                if hasattr(self, "sticker_history"):
                    self.sticker_history.clear()
                if hasattr(self, "sticker_future"):
                    self.sticker_future.clear()
                # ドラッグプレビューも消去
                if self.drag_preview_id is not None:
                    try:
                        self.canvas.delete(self.drag_preview_id)
                    except Exception:
                        pass
                    self.drag_preview_id = None
                self.active_sticker_pil = None
            except Exception:
                pass


    def save_image(self):
        # 実行時は他セクションを閉じる
        self.close_all_sections()
        if self.image:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG画像", "*.png"), ("JPEG画像", "*.jpg")]
            )
            if file_path:
                # ステッカーを合成して保存
                composed = self.compose_with_stickers()
                composed.save(file_path)
                ctk.CTkLabel(self.main_frame, text=f"✅ 保存しました: {file_path}", text_color="lightgreen").pack()

    # -----------------------------------------
    # 黒抽出（ふち取り）
    # -----------------------------------------
    def frame_outline(self):
        # 実行時は他セクションを閉じる
        self.close_all_sections()
        if self.image:
            # 履歴に積む
            self.push_history()
            pixels = self.image.load()
            width, height = self.image.size

            def is_black_range(r, g, b):
                return r <= 70 and g <= 70 and b <= 70

            for x in range(width):
                for y in range(height):
                    r, g, b = pixels[x, y]
                    if not is_black_range(r, g, b):
                        pixels[x, y] = (255, 255, 255)

            self.display_image()

    # -----------------------------------------
    # 透明化処理
    # -----------------------------------------
    def flood_transparent(self):
        if not self.image:
            return
        self.push_history()
        self.image = self.image.convert("RGBA")
        pixels = self.image.load()
        width, height = self.image.size

        for x in range(width):
            for y in range(height):
                r, g, b, a = pixels[x, y]
                if r >= 240 and g >= 240 and b >= 240:
                    pixels[x, y] = (r, g, b, 0)

        self.display_image()

    # -----------------------------------------
    # 塗りつぶし機能
    # -----------------------------------------
    def add_fill_ui(self):
        # 塗りつぶし用UI
        ctk.CTkLabel(self.fill_section_frame, text="塗りつぶし色を選択:", text_color="lightgray").pack(side="top", pady=5)
        
        # プリセット色ボタン
        preset_frame = ctk.CTkFrame(self.fill_section_frame)
        preset_frame.pack(pady=5)
        
        # 画像加工アプリ.py と同じスタイルの色付きボタン
        colors = [
            ("赤", "#ff0000"), ("青", "#0000ff"), ("緑", "#00a000"),
            ("黄", "#ffff00"), ("紫", "#800080"), ("橙", "#ffa500"),
            ("白", "#ffffff"), ("桃", "#ff69b4")
        ]

        # 画像参照を保持してGCを防ぐ
        if not hasattr(self, "_fill_icons"):
            self._fill_icons = {}

        for text, color in colors:
            hover = (
                "#ff7f7f" if color == "#ff0000" else
                "#7fbfff" if color == "#0000ff" else
                "#bfff7f" if color == "#00a000" else
                "#ffff7f" if color == "#ffff00" else
                "#bf7fff" if color == "#800080" else
                "#ffcc80" if color == "#ffa500" else
                "#c0c0c0" if color == "#ffffff" else
                "#ffc0cb"
            )
            ctk.CTkButton(
                preset_frame,
                text=text,
                width=60,
                fg_color=color,
                text_color="black" if color in ("#ffff00", "#ffffff") else "white",
                hover_color=hover,
                command=lambda c=color: self.set_fill_color(c)
            ).pack(side="left", padx=4, pady=5)

        # カラーコード入力
        input_frame = ctk.CTkFrame(self.fill_section_frame)
        input_frame.pack(pady=5)
        
        ctk.CTkLabel(input_frame, text="カラーコード(#RRGGBB):").pack(side="left", padx=5)
        self.color_entry = ctk.CTkEntry(input_frame, width=100)
        self.color_entry.pack(side="left", padx=5)
        apply_icon = self.load_button_image("fill_apply.png", size=(100, 36))
        if apply_icon is not None:
            self._fill_icons["fill_apply.png"] = apply_icon
            ctk.CTkButton(
                input_frame,
                text="",
                image=apply_icon,
                fg_color="transparent",
                hover_color="#444444",
                width=100,
                height=36,
                command=self.apply_custom_fill_color,
            ).pack(side="left", padx=5)
        else:
            ctk.CTkButton(input_frame, text="適用", width=50, command=self.apply_custom_fill_color).pack(side="left", padx=5)

        # Undo/Redo ボタン行
        history_frame = ctk.CTkFrame(self.fill_section_frame)
        history_frame.pack(pady=5)
        ctk.CTkButton(
            history_frame,
            text="戻る",
            width=80,
            fg_color="#666666",
            text_color="white",
            hover_color="#888888",
            command=self.undo,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            history_frame,
            text="進む",
            width=80,
            fg_color="#666666",
            text_color="white",
            hover_color="#888888",
            command=self.redo,
        ).pack(side="left", padx=5)
        
        self.fill_status_label = ctk.CTkLabel(self.fill_section_frame, text="現在: 赤 (クリックで塗りつぶし)", text_color="red")
        self.fill_status_label.pack(pady=5)

    def toggle_fill_options(self):
        if self.fill_options_visible:
            # 開いていれば閉じる
            self.fill_section_frame.pack_forget()
            self.fill_options_visible = False
            self.fill_mode_active = False
        else:
            # 他セクションを閉じてから開く
            self.close_all_sections(exclude="fill")
            self.fill_section_frame.pack(pady=5)
            self.fill_options_visible = True
            self.fill_mode_active = True
            self.set_fill_color(self.fill_color) # ステータス更新

    def set_fill_color(self, color_code):
        if isinstance(color_code, str):
            try:
                self.fill_color = ImageColor.getrgb(color_code)
                self.fill_status_label.configure(text=f"現在: {color_code}", text_color=color_code)
            except:
                pass
        else:
            self.fill_color = color_code
            self.fill_status_label.configure(text=f"現在: {color_code}", text_color="white")

    def apply_custom_fill_color(self):
        code = self.color_entry.get()
        if code.startswith("#") and len(code) == 7:
            self.set_fill_color(code)

    def on_canvas_click(self, event):
        # デコレーションモードが優先（ステッカー選択/ドラッグ）
        if self.decoration_mode_active and self.active_sticker_pil is not None:
            self.start_drag_preview(event.x, event.y)
            return
        # 以降は塗りモード
        if not self.fill_mode_active or not self.image:
            return
        
        # Canvas は (0,0) に画像を貼り付け（anchor="nw"）しているため、座標はそのまま使える
        if hasattr(self, 'tk_image') and self.tk_image is not None:
            w_img = int(self.tk_image.width())
            h_img = int(self.tk_image.height())
        else:
            w_img, h_img = self.displayed_size

        if w_img == 0 or h_img == 0:
            return

        x = event.x
        y = event.y

        if 0 <= x < w_img and 0 <= y < h_img:

            # 元画像上の座標に変換
            orig_w, orig_h = self.image.size
            real_x = int(x * (orig_w / w_img))
            real_y = int(y * (orig_h / h_img))
            
            self.apply_flood_fill(real_x, real_y)

    # --- ステッカードラッグ処理 ---
    def start_drag_preview(self, x, y):
        if self.active_sticker_pil is None or self.displayed_size == (0, 0):
            return
        w_disp, h_disp = self.displayed_size
        # 表示幅に対する割合でサイズ決定
        target_w = max(8, int(w_disp * float(self.sticker_size_ratio)))
        # アスペクト維持でリサイズ
        pil = self.active_sticker_pil
        ratio = target_w / pil.width
        target_h = max(8, int(pil.height * ratio))
        disp_sticker = pil.resize((target_w, target_h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(disp_sticker)

        # 既存プレビューを削除
        if self.drag_preview_id is not None:
            try:
                self.canvas.delete(self.drag_preview_id)
            except Exception:
                pass
            self.drag_preview_id = None
        # 新規プレビュー追加（中心合わせ）
        self.drag_preview_id = self.canvas.create_image(x, y, image=photo)
        # 参照保持（GC対策）
        self._drag_preview_image = photo

    def on_canvas_drag(self, event):
        if self.decoration_mode_active and self.drag_preview_id is not None:
            try:
                self.canvas.coords(self.drag_preview_id, event.x, event.y)
            except Exception:
                pass

    def on_canvas_release(self, event):
        if self.decoration_mode_active and self.drag_preview_id is not None and self.active_sticker_pil is not None:
            # 位置を確定してステッカーとして登録
            x, y = event.x, event.y
            w_disp, h_disp = self.displayed_size
            if w_disp == 0 or h_disp == 0:
                return
            # 履歴保存（ステッカー操作もUndo対象に）
            self.push_history()
            x_ratio = max(0.0, min(1.0, x / w_disp))
            y_ratio = max(0.0, min(1.0, y / h_disp))

            # プレビュー画像を最終ステッカーに差し替え（ID維持でOK）
            pil = self.active_sticker_pil
            target_w = max(8, int(w_disp * float(self.sticker_size_ratio)))
            ratio = target_w / pil.width
            target_h = max(8, int(pil.height * ratio))
            disp_sticker = pil.resize((target_w, target_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(disp_sticker)
            # キャンバスアイテムを再設定
            try:
                self.canvas.itemconfig(self.drag_preview_id, image=photo)
            except Exception:
                pass
            self._last_sticker_image = photo
            # リストへ登録
            self.canvas_stickers.append({
                "pil": pil.copy(),
                "photo": photo,
                "id": self.drag_preview_id,
                "x_ratio": x_ratio,
                "y_ratio": y_ratio,
                "size_ratio": float(self.sticker_size_ratio),
            })
            # 次のドラッグに備えプレビューIDをクリア
            self.drag_preview_id = None
            # 1回のドロップで選択解除したくない場合は保持、今回は解除しない
            # self.active_sticker_pil = None

    def apply_flood_fill(self, x, y):
        # クリックした画素と完全に同じ色の連結領域のみ塗りつぶす（しきい値 0 の厳密一致）
        try:
            # 画像モードに合わせて塗り色を用意
            mode = self.image.mode  # 'RGB' or 'RGBA' など
            pixels = self.image.load()
            width, height = self.image.size

            if not (0 <= x < width and 0 <= y < height):
                return

            start_color = pixels[x, y]

            # 塗り色（RGBA の場合はアルファ 255 を付与）
            if mode == 'RGBA':
                fill_color = (self.fill_color[0], self.fill_color[1], self.fill_color[2], 255)
            elif mode == 'RGB':
                fill_color = self.fill_color
            else:
                # その他のモードは RGB に変換して処理
                self.image = self.image.convert('RGB')
                pixels = self.image.load()
                mode = 'RGB'
                start_color = pixels[x, y]
                fill_color = self.fill_color

            # すでに同色なら何もしない（履歴も積まない）
            if start_color == fill_color:
                return

            # 履歴に現在の画像を保存し、Redoはクリア（新しい枝）
            self.push_history()

            # 幅優先（スタック）で厳密一致の連結領域を塗る
            stack = [(x, y)]
            visited = set()

            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in visited:
                    continue
                if not (0 <= cx < width and 0 <= cy < height):
                    continue

                if pixels[cx, cy] == start_color:
                    pixels[cx, cy] = fill_color
                    visited.add((cx, cy))
                    # 4 近傍
                    stack.append((cx + 1, cy))
                    stack.append((cx - 1, cy))
                    stack.append((cx, cy + 1))
                    stack.append((cx, cy - 1))

            self.display_image()
        except Exception as e:
            print(f"Flood fill error: {e}")

    def undo(self):
        # 1段階戻る（履歴があれば）
        try:
            if self.history:
                # 現在の画像とステッカー状態を未来へ退避
                self.future.append(self.image.copy())
                self.sticker_future.append(self.snapshot_stickers())
                # 過去へ戻す
                self.image = self.history.pop()
                self.display_image()
                snap = self.sticker_history.pop() if self.sticker_history else []
                self.rebuild_canvas_stickers_from_snapshot(snap)
        except Exception as e:
            print(f"Undo error: {e}")

    def redo(self):
        # 1段階進む（未来があれば）
        try:
            if self.future:
                # 現在の状態を過去へ保存
                self.history.append(self.image.copy())
                self.sticker_history.append(self.snapshot_stickers())
                # 未来から進む
                self.image = self.future.pop()
                self.display_image()
                snap = self.sticker_future.pop() if self.sticker_future else []
                self.rebuild_canvas_stickers_from_snapshot(snap)
        except Exception as e:
            print(f"Redo error: {e}")

    # -----------------------------------------
    # 色を強調する共通処理
    # -----------------------------------------
    def enhance_color(self, r_mul=1.0, g_mul=1.0, b_mul=1.0):
        if self.image:
            # 色変更前の状態を履歴に積む
            self.push_history()
            # 元画像からグレースケールベースを作成
            base = ImageOps.grayscale(self.original_image).convert("RGB")
            r, g, b = base.split()
            r = r.point(lambda i: min(255, i * r_mul))
            g = g.point(lambda i: min(255, i * g_mul))
            b = b.point(lambda i: min(255, i * b_mul))
            colored = Image.merge("RGB", (r, g, b))

            # #FFFFFF〜#EEEEEE の領域は色変更対象外（元画像を保持）
            try:
                orig_rgb = self.original_image.convert("RGB")
                px_c = colored.load()
                px_o = orig_rgb.load()
                w, h = colored.size
                for x in range(w):
                    for y in range(h):
                        ro, go, bo = px_o[x, y]
                        if ro >= 238 and go >= 238 and bo >= 238:
                            px_c[x, y] = (ro, go, bo)
            except Exception:
                # 万一の例外時も処理は続行
                pass

            self.image = colored
            self.display_image()

    def push_history(self):
        """現在の画像を履歴に保存し、未来スタックをクリアする。"""
        try:
            if self.image is not None:
                self.history.append(self.image.copy())
                self.future.clear()
                # ステッカー状態も履歴へ
                self.sticker_history.append(self.snapshot_stickers())
                self.sticker_future.clear()
        except Exception:
            pass

    def snapshot_stickers(self):
        """現在のステッカー状態のスナップショットを返す。"""
        snap = []
        try:
            for st in self.canvas_stickers:
                pil = st.get("pil")
                data = {
                    "pil": pil.copy() if pil is not None else None,
                    "x_ratio": float(st.get("x_ratio", 0.5)),
                    "y_ratio": float(st.get("y_ratio", 0.5)),
                    "size_ratio": float(st.get("size_ratio", self.sticker_size_ratio)),
                }
                snap.append(data)
        except Exception:
            pass
        return snap

    def rebuild_canvas_stickers_from_snapshot(self, snapshot):
        """スナップショットからキャンバス上のステッカーを再構築する。"""
        try:
            # 既存を削除
            for st in self.canvas_stickers:
                try:
                    self.canvas.delete(st.get("id"))
                except Exception:
                    pass
            self.canvas_stickers.clear()

            if not snapshot:
                return

            w_disp, h_disp = self.displayed_size
            if w_disp == 0 or h_disp == 0:
                return

            for data in snapshot:
                pil = data.get("pil")
                if pil is None:
                    continue
                size_ratio = float(data.get("size_ratio", self.sticker_size_ratio))
                target_w = max(8, int(w_disp * size_ratio))
                ratio = target_w / pil.width
                target_h = max(8, int(pil.height * ratio))
                disp_sticker = pil.resize((target_w, target_h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(disp_sticker)
                x = int(float(data.get("x_ratio", 0.5)) * w_disp)
                y = int(float(data.get("y_ratio", 0.5)) * h_disp)
                item_id = self.canvas.create_image(x, y, image=photo)
                self.canvas_stickers.append({
                    "pil": pil.copy(),
                    "photo": photo,
                    "id": item_id,
                    "x_ratio": float(data.get("x_ratio", 0.5)),
                    "y_ratio": float(data.get("y_ratio", 0.5)),
                    "size_ratio": size_ratio,
                })
        except Exception:
            pass

    # -----------------------------------------
    # デコレーション UI とロジック
    # -----------------------------------------
    def cover_decoration(self):
        """デコレーションセクションの表示/非表示を切り替える。
        ステッカー選択→キャンバス上でドラッグ＆ドロップで配置。
        """
        if self.decoration_visible:
            # 閉じる
            self.decoration_section_frame.pack_forget()
            self.decoration_visible = False
            self.decoration_mode_active = False
            self.active_sticker_pil = None
            return

        # 他セクションを閉じてから開く
        self.close_all_sections(exclude="decoration")
        self.decoration_section_frame.pack(pady=5, fill="x")
        self.decoration_visible = True
        self.decoration_mode_active = True
        self.fill_mode_active = False

        # セクション内容をクリアして再構築
        for w in getattr(self.decoration_section_frame, "winfo_children", lambda: [])():
            try:
                w.destroy()
            except Exception:
                pass

        ctk.CTkLabel(self.decoration_section_frame, text="ステッカーを選択 → 画像上でドラッグして配置", text_color="lightgray")\
            .pack(side="top", pady=6)

        # サイズスライダー
        size_frame = ctk.CTkFrame(self.decoration_section_frame)
        size_frame.pack(pady=4, fill="x")
        ctk.CTkLabel(size_frame, text="サイズ", text_color="lightgray").pack(side="left", padx=6)
        size_slider = ctk.CTkSlider(
            size_frame,
            from_=0.06,
            to=0.4,
            number_of_steps=34,
            command=lambda v: setattr(self, "sticker_size_ratio", float(v))
        )
        size_slider.set(self.sticker_size_ratio)
        size_slider.pack(side="left", padx=10, fill="x", expand=True)

        # パレット
        palette = ctk.CTkFrame(self.decoration_section_frame)
        palette.pack(pady=6)
        stickers = self.find_sticker_images()
        if not stickers:
            ctk.CTkLabel(self.decoration_section_frame, text="ステッカー画像が見つかりません (deco_img/ など)", text_color="#ff6666").pack(pady=6)
        else:
            # 各ステッカーをボタン表示
            max_w = 110
            for p in stickers:
                try:
                    pil = Image.open(p).convert("RGBA")
                    # プレビュー用に縮小
                    ratio = min(1.0, max_w / pil.width)
                    preview = pil.resize((max(8, int(pil.width * ratio)), max(8, int(pil.height * ratio))), Image.LANCZOS)
                    img = ImageTk.PhotoImage(preview)
                    btn = ctk.CTkButton(
                        palette,
                        text=os.path.basename(p),
                        image=img,
                        compound="top",
                        width=max_w+12,
                        height=120,
                        fg_color="#333333",
                        hover_color="#444444",
                        command=lambda pil_img=pil: self.select_sticker(pil_img)
                    )
                    # 参照保持
                    if not hasattr(btn, "_photo"):
                        btn._photo = img
                    btn.pack(side="left", padx=6, pady=4)
                except Exception:
                    pass

        # 補足ヘルプ
        ctk.CTkLabel(self.decoration_section_frame, text="選択後、キャンバスをドラッグ→離すと配置されます。", text_color="lightgray").pack(pady=4)

    def select_sticker(self, pil_img: Image.Image):
        """ステッカーを選択し、キャンバス上でドラッグ可能にする。"""
        try:
            self.active_sticker_pil = pil_img.copy()
            self.decoration_mode_active = True
        except Exception:
            self.active_sticker_pil = None

    def find_sticker_images(self):
        """deco_img（このスクリプト直下）だけを探索して返す。"""
        file_dir = os.path.dirname(__file__)
        target_dir = os.path.join(file_dir, "deco_img")
        exts = (".png", ".jpg", ".jpeg", ".webp")
        files = []
        if os.path.exists(target_dir):
            for name in os.listdir(target_dir):
                if name.lower().endswith(exts):
                    files.append(os.path.join(target_dir, name))
        return files

    def update_stickers_for_new_display(self):
        """現在の表示サイズに合わせ、キャンバス上のステッカーを再配置・再スケールする。"""
        try:
            w_disp, h_disp = self.displayed_size
            if w_disp == 0 or h_disp == 0:
                return
            for st in self.canvas_stickers:
                pil = st["pil"]
                # サイズ再計算
                target_w = max(8, int(w_disp * float(st.get("size_ratio", self.sticker_size_ratio))))
                ratio = target_w / pil.width
                target_h = max(8, int(pil.height * ratio))
                disp_sticker = pil.resize((target_w, target_h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(disp_sticker)
                st["photo"] = photo
                # 画像を更新
                try:
                    self.canvas.itemconfig(st["id"], image=photo)
                except Exception:
                    pass
                # 位置再配置（中心合わせ）
                x = int(st["x_ratio"] * w_disp)
                y = int(st["y_ratio"] * h_disp)
                try:
                    self.canvas.coords(st["id"], x, y)
                except Exception:
                    pass
        except Exception:
            pass

    def compose_with_stickers(self) -> Image.Image:
        """現在の画像にステッカーを合成して返す（保存用）。"""
        try:
            base = self.image.convert("RGBA")
            w_disp, h_disp = self.displayed_size
            w_orig, h_orig = base.size
            if w_disp == 0 or h_disp == 0:
                return base
            for st in self.canvas_stickers:
                pil = st["pil"].convert("RGBA")
                # 表示幅比率をオリジナル幅へ変換
                target_w_orig = max(8, int(w_orig * float(st.get("size_ratio", self.sticker_size_ratio))))
                ratio = target_w_orig / pil.width
                target_h_orig = max(8, int(pil.height * ratio))
                sticker = pil.resize((target_w_orig, target_h_orig), Image.LANCZOS)
                # 表示座標比率→オリジナル座標
                x_orig = int(st["x_ratio"] * w_orig)
                y_orig = int(st["y_ratio"] * h_orig)
                # キャンバスでは中心座標。貼り付けは左上座標に変換
                x0 = x_orig - sticker.width // 2
                y0 = y_orig - sticker.height // 2
                try:
                    # 透明ありの場合はマスク合成
                    base.paste(sticker, (x0, y0), sticker)
                except Exception:
                    # 透明なしでも貼り付け可能
                    base.paste(sticker, (x0, y0))
            return base
        except Exception:
            return self.image


if __name__ == "__main__":
    app = ColorChangerApp()
    app.mainloop()