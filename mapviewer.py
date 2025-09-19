import json
import os
import time
import math
import requests
import customtkinter as ctk
import tkintermapview


# =========================
# تنظیمات کلی
# =========================
APP_TITLE = "Advanced Map Viewer"
APP_ICON = "map.ico"
HISTORY_FILE = "history.json"

TILE_STYLES = {
    "map": {
        "name": "Map",
        "url": "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "dark": False
    },
    "terrain": {
        "name": "Terrain",
        "url": "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
        "dark": False
    },
    "paint": {
        "name": "Paint",
        "url": "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "dark": False
    },
    "dark": {
        "name": "Dark",
        "url": "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "dark": True
    },
    "satellite": {
        "name": "Satellite",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "dark": False
    },
    "topo": {
        "name": "Topo",
        "url": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
        "dark": False
    }
}

COLOR_RANGE = list("0123456789ABCDEF")


# =========================
# ابزارها و توابع کمکی
# =========================
def load_history():
    def _normalize_entry(h):
        # فقط دیکشنری‌های دارای lat/lon عددی
        if not isinstance(h, dict):
            return None
        lat = h.get("lat")
        lon = h.get("lon")
        if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
            return None
        address = h.get("address")
        label = h.get("label")
        if not label:
            if address:
                label = str(address).split(",")[0]
            else:
                label = f"{lat:.5f}, {lon:.5f}"
        if address is None:
            address = label
        ts = h.get("ts") or timestamp()
        return {"label": label, "address": address, "lat": float(lat), "lon": float(lon), "ts": ts}

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            normalized = []
            for item in data:
                n = _normalize_entry(item)
                if n:
                    normalized.append(n)
            return normalized
        except Exception:
            return []
    return []


def save_history(history_list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_list, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def timestamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


# =========================
# ویدجت‌های سفارشی
# =========================
class LocationEntry(ctk.CTkEntry):
    def __init__(self, parent, input_var, submit_callback):
        self.color_index = 15
        self.error = False
        super().__init__(
            master=parent,
            textvariable=input_var,
            corner_radius=8,
            border_width=3,
            fg_color="#FFFFFF",
            border_color="#CCCCCC",
            text_color="#000000",
            font=ctk.CTkFont(family="Tahoma", size=14),
            placeholder_text="نام مکان را وارد کنید و Enter بزنید"
        )
        self.bind("<Return>", submit_callback)
        input_var.trace_add("write", self.clean_error)

    def display_error(self):
        self.error = True
        if self.color_index > 0:
            self.color_index -= 1
            color = COLOR_RANGE[self.color_index]
            self.configure(border_color=f"#F{color}{color}", text_color=f"#{color}00")
            self.after(40, self.display_error)

    def clean_error(self, *args):
        if self.error:
            self.configure(border_color="#CCCCCC", text_color="#000000")
            self.color_index = 15
            self.error = False


class MapWidget(tkintermapview.TkinterMapView):
    def __init__(self, parent, on_left_click=None, on_mouse_move=None):
        super().__init__(master=parent)
        self.on_left_click = on_left_click
        self.on_mouse_move = on_mouse_move

        # کلیک چپ روی نقشه
        self.add_left_click_map_command(self._handle_left_click)

        # حرکت ماوس
        self.bind("<Motion>", self._handle_mouse_move)

    def map_view_style(self, style_key: str):
        style = TILE_STYLES.get(style_key, TILE_STYLES["map"])
        self.set_tile_server(style["url"])
        self.set_zoom(self.zoom)

    def _handle_left_click(self, coords_tuple):
        lat, lon = coords_tuple
        if self.on_left_click:
            self.on_left_click(lat, lon)

    def _handle_mouse_move(self, event):
        lat, lon = None, None
        # تبدیل مختصات پیکسل به جغرافیایی
        for attr_name in (
            "convert_canvas_coords_to_decimal_coords",
            "convert_canvas_coords_to_gps",
            "get_position_from_xy",
        ):
            if hasattr(self, attr_name):
                try:
                    func = getattr(self, attr_name)
                    result = func(event.x, event.y)
                    if isinstance(result, tuple) and len(result) == 2:
                        lat, lon = float(result[0]), float(result[1])
                    break
                except Exception:
                    pass
        if lat is None or lon is None:
            lat, lon = self.get_position()

        if self.on_mouse_move:
            self.on_mouse_move(lat, lon)

    def animate_to(self, target_lat, target_lon, duration_ms=350, steps=24):
        start_lat, start_lon = self.get_position()
        d_lat = target_lat - start_lat
        d_lon = target_lon - start_lon
        if steps <= 1:
            self.set_position(target_lat, target_lon)
            return
        interval = max(10, duration_ms // steps)

        def step(i=1):
            t = i / steps
            ease = (1 - math.cos(math.pi * t)) / 2  # ease in-out
            self.set_position(start_lat + d_lat * ease, start_lon + d_lon * ease)
            if i < steps:
                self.after(interval, lambda: step(i + 1))

        step()

    def clear_all_markers(self):
        try:
            self.delete_all_marker()
        except Exception:
            try:
                self.delete_all_markers()
            except Exception:
                pass


# =========================
# برنامه اصلی
# =========================
class MapApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x750")
        self.minsize(950, 640)
        try:
            self.iconbitmap(APP_ICON)
        except Exception:
            pass

        #  داخلی
        self.input_var = ctk.StringVar()
        self.history = load_history()  # [{label,address,lat,lon,ts}]
        self.current_style = "map"

        # ترسیم منطقه
        self.drawing_polygon = False
        self.polygon_points = []
        self.polygon_object = None

        #  مسیر‌یابی
        self.routing_mode = False
        self.route_start = None  # (lat, lon) یا None
        self.route_line = None   # شیء مسیر رسم‌شده
        self.route_start_marker = None
        self.route_end_marker = None

        #  تمام‌صفحه
        self.map = MapWidget(self, on_left_click=self.on_map_click, on_mouse_move=self.on_mouse_move)
        self.map.place(relx=0.5, rely=0.5, anchor="center", relwidth=1, relheight=1)
        self.map.map_view_style(self.current_style)
        self.map.set_position(35.6892, 51.3890)  # Tehran
        self.map.set_zoom(11)

        # پنل کناری
        self.side_panel = ctk.CTkFrame(self, width=300, height=600, corner_radius=16, fg_color="#F5F5F5")
        self.side_panel.place(relx=1.0, rely=0.5, x=-20, anchor="e")
        self.side_panel.pack_propagate(False)

        # کادر جست‌وجو
        self.location_entry = LocationEntry(self.side_panel, self.input_var, self.submit_location)
        self.location_entry.pack(fill="x", padx=10, pady=(10, 6))

        # ردیف کنترل‌ها (پاک‌سازی، پایان/لغو چندضلعی)
        controls = ctk.CTkFrame(self.side_panel, fg_color="transparent")
        controls.pack(fill="x", padx=10, pady=6)
        controls.grid_columnconfigure((0, 1, 2), weight=1, uniform="c")

        self.btn_clear = ctk.CTkButton(
            controls, text="پاک‌سازی نقشه", command=self.clear_all,
            fg_color="#E6E6E6", hover_color="#D6D6D6", text_color="#222"
        )
        self.btn_clear.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        self.btn_finish_poly = ctk.CTkButton(
            controls, text="ترسیم تایید", command=self.finish_polygon,
            fg_color="#E6F2FF", hover_color="#D6E8FF", text_color="#114"
        )
        self.btn_finish_poly.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        self.btn_cancel_poly = ctk.CTkButton(
            controls, text="ترسیم لغو", command=self.cancel_polygon,
            fg_color="#FFEFEF", hover_color="#FFE0E0", text_color="#811"
        )
        self.btn_cancel_poly.grid(row=0, column=2, sticky="ew", padx=4, pady=4)

        # دکمه فعال‌سازی ترسیم منطقه
        self.poly_toggle = ctk.CTkButton(
            self.side_panel, text="خاموش : ترسیم منطقه", command=self.toggle_polygon_mode,
            fg_color="#E6E6E6", hover_color="#D6D6D6", text_color="#222"
        )
        self.poly_toggle.pack(fill="x", padx=10, pady=(0, 8))

        # دکمه‌های استایل
        self.style_buttons_frame = ctk.CTkFrame(self.side_panel, fg_color="transparent")
        self.style_buttons_frame.pack(fill="x", padx=10, pady=6)
        self.style_buttons_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="s")

        # ساخت دکمه‌ها بر اساس TILE_STYLES
        self.style_buttons = {}
        row, col = 0, 0
        for key, info in TILE_STYLES.items():
            btn = ctk.CTkButton(
                self.style_buttons_frame,
                text=info["name"],
                command=lambda k=key: self.change_style(k),
                fg_color="#DBDBDB",
                hover_color="#C9C9C9",
                text_color="#111",
                height=36
            )
            btn.grid(row=row, column=col, sticky="ew", padx=4, pady=4)
            self.style_buttons[key] = btn
            col += 1
            if col > 2:
                col = 0
                row += 1

        # هایلایت استایل فعلی
        self.highlight_style_button(self.current_style)

        # کنترل‌های مسیر‌یابی
        routing_frame = ctk.CTkFrame(self.side_panel, fg_color="transparent")
        routing_frame.pack(fill="x", padx=10, pady=6)
        routing_frame.grid_columnconfigure((0, 1), weight=1, uniform="r")

        self.btn_route_toggle = ctk.CTkButton(
            routing_frame, text="خاموش : مسیریابی", command=self.toggle_routing_mode,
            fg_color="#E6E6E6", hover_color="#D6D6D6", text_color="#222"
        )
        self.btn_route_toggle.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        self.btn_route_clear = ctk.CTkButton(
            routing_frame, text="مسیر کردن پاک", command=self.clear_route,
            fg_color="#FFF4E5", hover_color="#FFE7CC", text_color="#663C00"
        )
        self.btn_route_clear.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        # لیست تاریخچه
        self.history_frame = ctk.CTkScrollableFrame(self.side_panel, fg_color="#FFFFFF", corner_radius=8)
        self.history_frame.pack(expand=True, fill="both", padx=10, pady=(6, 10))
        self.refresh_history_ui()

        # نوار وضعیت پایین
        self.status_bar = ctk.CTkFrame(self, height=34, fg_color="#F0F0F0")
        self.status_bar.place(relx=0.5, rely=1.0, anchor="s", relwidth=1.0, y=-4)

        self.status_label = ctk.CTkLabel(self.status_bar, text="Lat: ---, Lon: ---", anchor="w")
        self.status_label.pack(side="left", padx=12, pady=4)

        self.center_label = ctk.CTkLabel(self.status_bar, text="Center: ---, ---", anchor="e")
        self.center_label.pack(side="right", padx=12, pady=4)

        # به‌روزرسانی مرکز هنگام حرکت یا زوم
        self.map.bind("<ButtonRelease-1>", lambda e: self.update_center_status())
        self.map.bind("<MouseWheel>", lambda e: self.after(50, self.update_center_status()))
        self.update_center_status()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.mainloop()

    # =========================
    # جست‌وجوی مکان
    # =========================
    def get_location(self, query):
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 1, "addressdetails": 1}
        headers = {"User-Agent": "keyvan-map-app (contact: example@example.com)"}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=8)
            if response.status_code == 200:
                data = response.json()
                if data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    address = data[0]["display_name"]
                    return lat, lon, address
        except Exception:
            pass
        return None

    # =========================
    # رویدادها و منطق
    # =========================
    def submit_location(self, event=None):
        text = self.input_var.get().strip()
        if not text:
            self.location_entry.display_error()
            return

        result = self.get_location(text)
        if not result:
            self.location_entry.display_error()
            return

        lat, lon, address = result
        self.add_history_entry(address, lat, lon)
        self.input_var.set("")
        self.focus_map(lat, lon, zoom=14, smooth=True)
        self.add_marker(lat, lon, address)

    def on_map_click(self, lat, lon):
        if self.drawing_polygon:
            self.polygon_points.append((lat, lon))
            self.draw_polygon_preview()
            self.status_label.configure(text=f"Polygon points: {len(self.polygon_points)}")
            return

        if self.routing_mode:
            if self.route_start is None:
                self.route_start = (lat, lon)
                self._replace_route_start_marker(lat, lon)
                self.status_label.configure(text="مبدأ انتخاب شد. مقصد را کلیک کنید.")
            else:
                route_end = (lat, lon)
                self._replace_route_end_marker(lat, lon)

                # دریافت و رسم مسیر
                route = self.get_route(self.route_start[0], self.route_start[1], route_end[0], route_end[1])
                if route and route.get("points"):
                    self.draw_route(route["points"])
                    # گزارش کوتاه فاصله/زمان
                    dist_km = route["distance_m"] / 1000.0
                    dur_min = route["duration_s"] / 60.0
                    self.status_label.configure(
                        text=f"مسیر رسم شد - فاصله: {dist_km:.2f}km، زمان: {dur_min:.1f}min"
                    )
                    # فوکوس نرم روی مسیر: مرکز مسیر
                    mid_idx = len(route["points"]) // 2
                    self.focus_map(route["points"][mid_idx][0], route["points"][mid_idx][1], smooth=True)
                else:
                    self.status_label.configure(text="خطا در دریافت مسیر.")

                self.route_start = None
            return

        # افزودن مارکر و تاریخچه
        label = f"{lat:.5f}, {lon:.5f}"
        self.add_history_entry(label, lat, lon)
        self.add_marker(lat, lon, label)

    def on_mouse_move(self, lat, lon):
        self.status_label.configure(text=f"Lat: {lat:.5f}, Lon: {lon:.5f}")

    def update_center_status(self):
        clat, clon = self.map.get_position()
        self.center_label.configure(text=f"Center: {clat:.5f}, {clon:.5f}")

    # =========================
    # استایل‌ها
    # =========================
    def change_style(self, style_key):
        self.current_style = style_key
        self.map.map_view_style(style_key)
        self.highlight_style_button(style_key)

    def highlight_style_button(self, active_key):
        for key, btn in self.style_buttons.items():
            if key == active_key:
                btn.configure(fg_color="#4A90E2", text_color="#FFFFFF", hover_color="#357ABD")
            else:
                btn.configure(fg_color="#DBDBDB", text_color="#111", hover_color="#C9C9C9")

    # =========================
    # تاریخچه
    # =========================
    def add_history_entry(self, address, lat, lon):
        label = address.split(",")[0] if address else f"{lat:.5f}, {lon:.5f}"
        entry = {"label": label, "address": address, "lat": lat, "lon": lon, "ts": timestamp()}
        # جلوگیری از تکرار دقیق
        if not any(abs(h["lat"] - lat) < 1e-7 and abs(h["lon"] - lon) < 1e-7 for h in self.history):
            self.history.insert(0, entry)
            save_history(self.history)
            self.add_history_row(entry)
        else:
            self.refresh_history_ui()

    def add_history_row(self, entry):
        frame = ctk.CTkFrame(self.history_frame, fg_color="#FFFFFF", corner_radius=6)
        frame.pack(fill="x", pady=4, padx=6)

        def jump():
            self.focus_map(entry["lat"], entry["lon"], zoom=14, smooth=True)
            self.add_marker(entry["lat"], entry["lon"], entry["address"])

        btn = ctk.CTkButton(
            frame, text=entry["label"], command=jump,
            font=ctk.CTkFont(family="Tahoma", size=14),
            anchor="w", fg_color="transparent", hover_color="#ECECEC", text_color="#222"
        )
        btn.pack(side="left", fill="x", expand=True, padx=2, pady=2)

        del_btn = ctk.CTkButton(
            frame, text="✕", command=lambda: self.delete_history_entry(entry, frame),
            width=34, fg_color="transparent", hover_color="#F8D7DA", text_color="#900"
        )
        del_btn.pack(side="right", padx=2, pady=2)

    def refresh_history_ui(self):
        for child in self.history_frame.winfo_children():
            child.destroy()
        for entry in self.history:
            self.add_history_row(entry)

    def delete_history_entry(self, entry, frame_widget):
        try:
            self.history.remove(entry)
        except ValueError:
            pass
        save_history(self.history)
        try:
            frame_widget.destroy()
        except Exception:
            pass

    def clear_all(self):
        # پاک‌سازی مارکرها
        self.map.clear_all_markers()

        # پاک‌سازی تاریخچه
        self.history.clear()
        save_history(self.history)
        self.refresh_history_ui()

        # پاک‌سازی چندضلعی و مسیر
        self.cancel_polygon()
        self.clear_route()

    # =========================
    # مارکرها و فوکوس
    # =========================
    def add_marker(self, lat, lon, text=None):
        m = self.map.set_marker(
            lat, lon, text=text or f"{lat:.5f}, {lon:.5f}",
            command=lambda marker: self.show_marker_info(marker, lat, lon, text)
        )
        return m

    def show_marker_info(self, marker, lat, lon, text):
        info = f"{text or '-'}\n{lat:.6f}, {lon:.6f}"
        self.status_label.configure(text=info)

    def focus_map(self, lat, lon, zoom=None, smooth=True):
        if zoom is not None:
            self.map.set_zoom(zoom)
        if smooth:
            self.map.animate_to(lat, lon, duration_ms=400, steps=24)
        else:
            self.map.set_position(lat, lon)
        self.update_center_status()

    # =========================
    # ترسیم منطقه (Polygon)
    # =========================
    def toggle_polygon_mode(self):
        # خاموش کردن حالت مسیر‌یابی هنگام ورود به حالت چندضلعی
        if not self.drawing_polygon and self.routing_mode:
            self.toggle_routing_mode(force_off=True)

        self.drawing_polygon = not self.drawing_polygon
        if self.drawing_polygon:
            self.polygon_points.clear()
            self.poly_toggle.configure(text="روشن : ترسیم منطقه", fg_color="#DFF0D8", text_color="#063")
            self.status_label.configure(text="Polygon mode: click to add points. Finish/Cancel to complete.")
        else:
            self.poly_toggle.configure(text="خاموش : ترسیم منطقه", fg_color="#E6E6E6", text_color="#222")
            self.status_label.configure(text="Lat: ---, Lon: ---")

    def draw_polygon_preview(self):
        if self.polygon_object:
            try:
                self.map.delete(self.polygon_object)
            except Exception:
                pass
            self.polygon_object = None

        if len(self.polygon_points) >= 2:
            self.polygon_object = self.map.set_polygon(
                self.polygon_points,
                outline_color="#FF9900",
                fill_color="",
                border_width=2
            )

    def finish_polygon(self):
        if self.drawing_polygon and len(self.polygon_points) >= 3:
            if self.polygon_object:
                try:
                    self.map.delete(self.polygon_object)
                except Exception:
                    pass
                self.polygon_object = None

            self.polygon_object = self.map.set_polygon(
                self.polygon_points,
                outline_color="#FF9900",
                fill_color="#FFD07A",
                border_width=2
            )

            self.status_label.configure(text=f"Polygon completed with {len(self.polygon_points)} points.")
            self.drawing_polygon = False
            self.poly_toggle.configure(text="خاموش : ترسیم منطقه", fg_color="#E6E6E6", text_color="#222")
        else:
            self.status_label.configure(text="Polygon needs at least 3 points to finish.")

    def cancel_polygon(self):
        self.drawing_polygon = False
        self.polygon_points.clear()
        if self.polygon_object:
            try:
                self.map.delete(self.polygon_object)
            except Exception:
                pass
            self.polygon_object = None
        self.poly_toggle.configure(text="خاموش : ترسیم منطقه", fg_color="#E6E6E6", text_color="#222")

    # =========================
    # مسیر‌یابی
    # =========================
    def toggle_routing_mode(self, force_off=False):
        if force_off:
            self.routing_mode = True  # تا در ادامه سوییچ کند
        self.routing_mode = not self.routing_mode

        if self.routing_mode:
            # خاموش کردن حالت چندضلعی برای جلوگیری از تداخل
            if self.drawing_polygon:
                self.toggle_polygon_mode()

            self.btn_route_toggle.configure(text="روشن : مسیریابی", fg_color="#DFF0D8", text_color="#063")
            self.status_label.configure(text="حالت مسیر یابی فعال است. ابتدا مبتدا و سپی مقصد را انتخاب نمایید")
            self.route_start = None
        else:
            self.btn_route_toggle.configure(text="خاموش : مسیریابی", fg_color="#E6E6E6", text_color="#222")
            self.status_label.configure(text="Lat: ---, Lon: ---")
            self.route_start = None

    def clear_route(self):
        # حذف خط مسیر
        if self.route_line:
            try:
                self.map.delete(self.route_line)
            except Exception:
                pass
            self.route_line = None

        if self.route_start_marker:
            try:
                self.map.delete(self.route_start_marker)
            except Exception:
                pass
            self.route_start_marker = None

        if self.route_end_marker:
            try:
                self.map.delete(self.route_end_marker)
            except Exception:
                pass
            self.route_end_marker = None

        self.route_start = None

    def _replace_route_start_marker(self, lat, lon):
        if self.route_start_marker:
            try:
                self.map.delete(self.route_start_marker)
            except Exception:
                pass
            self.route_start_marker = None
        try:
            self.route_start_marker = self.map.set_marker(lat, lon, text="مبدأ")
        except Exception:
            self.route_start_marker = None

    def _replace_route_end_marker(self, lat, lon):
        if self.route_end_marker:
            try:
                self.map.delete(self.route_end_marker)
            except Exception:
                pass
            self.route_end_marker = None
        try:
            self.route_end_marker = self.map.set_marker(lat, lon, text="مقصد")
        except Exception:
            self.route_end_marker = None

    def get_route(self, start_lat, start_lon, end_lat, end_lon):
        url = f"https://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
        params = {"overview": "full", "geometries": "geojson"}
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if not data.get("routes"):
                    return None
                route0 = data["routes"][0]
                coords = route0["geometry"]["coordinates"]
                points = [(lat, lon) for lon, lat in coords]
                distance_m = float(route0.get("distance", 0.0))
                duration_s = float(route0.get("duration", 0.0))
                return {"points": points, "distance_m": distance_m, "duration_s": duration_s}
        except Exception:
            pass
        return None

    def draw_route(self, points):
        # حذف مسیر قبلی
        if self.route_line:
            try:
                self.map.delete(self.route_line)
            except Exception:
                pass
            self.route_line = None

        if not points:
            return

        try:
            self.route_line = self.map.set_path(points, color="#FF3333", width=3)
            return
        except Exception:
            self.route_line = None

        try:
            self.route_line = self.map.set_polygon(points, outline_color="#FF3333", fill_color="", border_width=3)
        except Exception:
            self.route_line = None

    # =========================
    # پایان برنامه
    # =========================
    def on_close(self):
        save_history(self.history)
        self.destroy()


if __name__ == "__main__":
    MapApp()