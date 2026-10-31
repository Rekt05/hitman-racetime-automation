import tkinter as tk
from tkinter import ttk, messagebox
import requests
import threading
import time
import re
import webbrowser
from obswebsocket import obsws, requests as obs_requests, events as obs_events
import configparser
import os
import sys

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_external_path(filename):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)

#version config
version = "1.0"
version_url = "https://raw.githubusercontent.com/Rekt05/hitman-racetime-automation/refs/heads/main/current_version.txt"
releases_url = "https://github.com/Rekt05/hitman-racetime-automation/releases/latest"

#config
obshost = "localhost"
obsport = 4455

NAME_CORNERS = {
    "top_left": 5,
    "top_right": 6,
    "bottom_left": 9,
    "bottom_right": 10,
}

def fill_hole_names(names, index, slots_per_scene):
    names = list(names)
    if not (0 <= index < len(names)):
        return names
    next_page = ((index // slots_per_scene) + 1) * slots_per_scene
    later = [i for i in range(next_page, len(names)) if names[i]]
    if not later:
        names[index] = ""
    else:
        donor = later[-1]
        names[index] = names[donor]
        names[donor] = ""
    return names

#japanese 3017 things
NAME_FONT_ASCENT = 175
NAME_FONT_DESCENT = 25
NAME_FONT_LEADING = 95

def name_corner_pos(pos_key, sx, sy, sw, sh, padding, name_height):
    if pos_key == "top_right":
        return sx + sw - padding, sy + padding
    if pos_key in ("bottom_left", "bottom_right"):
        cell = NAME_FONT_ASCENT + NAME_FONT_DESCENT + NAME_FONT_LEADING
        empty_below = NAME_FONT_DESCENT + NAME_FONT_LEADING
        nudge = name_height * empty_below / cell
        y = sy + sh - padding + nudge
        if pos_key == "bottom_left":
            return sx + padding, y
        return sx + sw - padding, y
    return sx + padding, sy + padding

SCENE_PROFILES = {
    "snr": {
        "label": "SNR",
        "max_slots": 18,
        "scenes": ["Streams 1-6", "Streams 7-12", "Streams 13-18"],
        "slots_per_scene": 6,
        "visibility": "direct",
        "layout_controls": True,
        "layout_counts": [6, 4, 2, 1],
        "layout_map": {6: (3, 2), 4: (2, 2), 2: (2, 1), 1: (1, 1)},
        "layout_rules": [(5, 6), (3, 4), (2, 2), (1, 1)],
        "layout_max_height": 806,
        "layout_gap": 3,
        "layout_padding": 5,
        "name_positions": True,
        "default_name_position": "top_right",
        "fill_holes": True,
    },
    "snsaso": {
        "label": "SNSASO",
        "max_slots": 12,
        "scenes": ["Streams 1-4", "Streams 5-8", "Streams 9-12"],
        "slots_per_scene": 4,
        "visibility": "direct",
        "layout_controls": True,
        "layout_counts": [4, 2, 1],
        "layout_map": {4: (2, 2), 2: (2, 1), 1: (1, 1)},
        "layout_rules": [(3, 4), (2, 2), (1, 1)],
        "layout_max_height": 1080,
        "layout_gap": 12,
        "layout_padding": 8,
        "aspect_ratio": False,
        "layout_active_only": True,
        "name_positions": True,
        "default_name_position": "top_left",
        "fill_holes": True,
    },
}

twitchlink = "https://player.twitch.tv/?channel={}&enableExtensions=true&muted=false&parent=twitch.tv&player=popout&quality=720p60&volume=0.7699999809265137"
twitchregex = re.compile(r'(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)')
channelparam = re.compile(r'[?&]channel=([A-Za-z0-9_]+)', re.I)

def channel_from_url(url):
    if not url or url == "about:blank":
        return ""
    match = channelparam.search(url)
    return match.group(1).lower() if match else ""

def missing_profile_sources(profile):
    missing = []
    for i in range(1, profile["max_slots"] + 1):
        for name in (f"Stream {i}", f"Streamer Name {i}"):
            missing.append(name)
    return missing

def plan_source_assignment(slot_names, slot_channels, source_names, source_owner, source_channels):
    active = [name.strip() for name in slot_names]
    active_lower = {name.lower() for name in active if name}
    by_owner = {}
    by_channel = {}
    for src in source_names:
        owner = (source_owner.get(src) or "").strip()
        if owner and owner.lower() not in by_owner:
            by_owner[owner.lower()] = src
        channel = (source_channels.get(src) or "").lower()
        if channel and channel not in by_channel:
            by_channel[channel] = src

    used = set()
    assignment = [""] * len(active)
    reloads = {}

    for i, name in enumerate(active):
        if not name:
            continue
        channel = (slot_channels[i] or "").lower()
        src = by_owner.get(name.lower())
        if src is None and channel:
            src = by_channel.get(channel)
        if src and src not in used:
            assignment[i] = src
            used.add(src)

    blanks = []
    warm = []
    for src in source_names:
        if src in used:
            continue
        owner = (source_owner.get(src) or "").strip()
        channel = (source_channels.get(src) or "").lower()
        if owner and owner.lower() in active_lower:
            continue
        if not owner and not channel:
            blanks.append(src)
        else:
            warm.append(src)
    for i, name in enumerate(active):
        if not name or assignment[i]:
            continue
        home = source_names[i] if i < len(source_names) else ""
        if home and home in blanks:
            blanks.remove(home)
            assignment[i] = home
        elif blanks:
            assignment[i] = blanks.pop(0)
        elif home and home in warm:
            warm.remove(home)
            assignment[i] = home
        elif warm:
            assignment[i] = warm.pop(0)

    for i, name in enumerate(active):
        src = assignment[i]
        if not src or not name:
            continue
        channel = (slot_channels[i] or "").lower()
        loaded = (source_channels.get(src) or "").lower()
        if channel and channel != loaded:
            reloads[src] = channel

    owners = {src: "" for src in source_names}
    for i, src in enumerate(assignment):
        if src:
            owners[src] = active[i]
    for src in source_names:
        if owners[src]:
            continue
        old = (source_owner.get(src) or "").strip()
        if old and old.lower() not in active_lower:
            owners[src] = old
    return assignment, owners, reloads

def complete_slot_sources(assignment, source_names):
    full = list(assignment)
    used = {src for src in full if src}
    for i in range(len(full)):
        if not full[i] and i < len(source_names) and source_names[i] not in used:
            full[i] = source_names[i]
            used.add(source_names[i])
    remaining = [src for src in source_names if src not in used]
    for i in range(len(full)):
        if not full[i] and remaining:
            full[i] = remaining.pop(0)
    return full

def run_move_checks():
    sources = [f"Stream {i}" for i in range(1, 5)]
    owners = {"Stream 1": "A", "Stream 2": "B", "Stream 3": "", "Stream 4": ""}
    channels = {"Stream 1": "a", "Stream 2": "b", "Stream 3": "", "Stream 4": ""}
    assignment, new_owners, reloads = plan_source_assignment(
        ["B", "A", "", ""],
        ["b", "a", "", ""],
        sources, owners, channels
    )
    assert assignment == ["Stream 2", "Stream 1", "", ""], assignment
    assert reloads == {}, reloads
    assert new_owners["Stream 1"] == "A"
    assert new_owners["Stream 2"] == "B"

    assignment, new_owners, reloads = plan_source_assignment(
        ["", "", "A"],
        ["", "", "a"],
        sources, owners, channels
    )
    assert assignment[2] == "Stream 1", assignment
    assert reloads == {}

    assignment, _, reloads = plan_source_assignment(
        ["C"],
        ["c"],
        sources,
        {"Stream 1": "", "Stream 2": "B"},
        {"Stream 1": "", "Stream 2": "b"}
    )
    assert assignment == ["Stream 1"]
    assert reloads == {"Stream 1": "c"}

    full = complete_slot_sources(["Stream 2", "Stream 1", "", ""], sources)
    assert full == ["Stream 2", "Stream 1", "Stream 3", "Stream 4"], full
    full_hole = complete_slot_sources(["", "", "Stream 1", ""], sources)
    assert full_hole == ["Stream 3", "Stream 2", "Stream 1", "Stream 4"], full_hole

    snsaso = SCENE_PROFILES["snsaso"]
    needed = missing_profile_sources(snsaso)
    assert "Stream 12" in needed and "Streamer Name 12" in needed
    assert "Stream 1 BG" not in needed
    snr_needed = missing_profile_sources(SCENE_PROFILES["snr"])
    assert "Stream 18" in snr_needed

class RacetimeAutomation:
    def __init__(self, root):
        self.root = root
        self.root.title("Hitman Racetime Automation")
        self.root.geometry("1280x920")
        self.root.minsize(1100, 700)

        self.ws = None
        self.is_monitoring = False
        self.slots = []
        self.scenemap = {}
        self.blacklist = {}
        self.source_owner = {}
        self.source_channels = {}
        self.slot_targets = {}
        self.source_scene = {}
        self.audio_slots = set()
        self.multi_audio = False
        self.applying_audio = False
        self.lastrt = []
        self.active_race_url = ""
        self.current_layout_state = {}

        self.config = configparser.ConfigParser()
        config_file = get_external_path("config.ini")
        if os.path.exists(config_file):
            self.config.read(config_file)

        saved_profile = self.config.get("Settings", "SceneProfile", fallback="snsaso").lower()
        if saved_profile not in SCENE_PROFILES:
            saved_profile = "snsaso"
        self.profile_key = saved_profile
        self.profile = SCENE_PROFILES[self.profile_key]
        self.audio_slots = self.default_audio_slots()
        self.multi_audio = self.saved_bool("MultipleAudio")
        self._init_layout_state()

        saved_ratio = self.saved_choice("AspectRatio", ("16:9", "16:10"), "16:9")
        saved_pos = self.saved_choice(
            "NamePosition",
            tuple(NAME_CORNERS),
            self.profile.get("default_name_position", "top_left"),
        )
        saved_height = self.saved_int("NameHeight", 75, 0, 100)
        saved_timer = self.saved_int("FinishedTimer", 10, 0, 45)

        self.urlvar = tk.StringVar()
        self.ratio_var = tk.StringVar(value=saved_ratio)
        self.auto_remove_finished = tk.BooleanVar(value=self.saved_bool("AutoRemove"))
        self.btn_auto_remove = None
        self.auto_resize_active = tk.BooleanVar(value=self.saved_bool("AutoResize"))
        self.btn_auto_resize = None
        self.remove_delay_var = tk.StringVar(value=str(saved_timer))
        self.remove_delay_var.trace_add("write", lambda *args: self.update_button_text())
        self.remove_delay_var.trace_add("write", lambda *args: self.save_config())
        self.name_height_var = tk.StringVar(value=str(saved_height))
        self.name_height_var.trace_add("write", lambda *args: self.on_name_height_changed())
        self.name_pos_var = tk.StringVar(value=saved_pos)
        self.profile_var = tk.StringVar(value=self.profile_key)

        savedpw = self.config.get("Settings", "OBSPW", fallback="")
        self.pwvar = tk.StringVar(value=savedpw)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        style = ttk.Style()
        style.configure("Racing.TLabel", foreground="green")
        style.configure("Done.TLabel", foreground="blue", font=('Helvetica', 9, 'bold'))
        style.configure("DNF.TLabel", foreground="red", font=('Helvetica', 9, 'bold'))
        style.configure("Small.TButton", font=('Helvetica', 7))

        topbar = ttk.Frame(root, padding=(10, 8, 10, 2))
        topbar.pack(fill="x")

        scene_row = ttk.Frame(topbar)
        scene_row.pack(fill="x")
        ttk.Label(scene_row, text="Scene Collection:").pack(side="left", padx=(0, 6))
        self.profile_frame = ttk.Frame(scene_row)
        self.profile_frame.pack(side="left")
        self.profile_radios = []
        for key in ("snsaso", "snr"):
            pdata = SCENE_PROFILES[key]
            rb = ttk.Radiobutton(
                self.profile_frame,
                text=pdata["label"],
                variable=self.profile_var,
                value=key,
                command=self.on_profile_change
            )
            rb.pack(side="left", padx=(0, 12))
            self.profile_radios.append(rb)

        conn = ttk.Frame(topbar)
        conn.pack(fill="x", pady=(6, 0))
        ttk.Label(conn, text="OBS Password:").pack(side="left")
        ttk.Entry(conn, textvariable=self.pwvar, width=24, show="*").pack(side="left", padx=6)
        self.btn_connect = ttk.Button(conn, text="Start", command=self.toggle_monitoring)
        self.btn_connect.pack(side="left")

        race_row = ttk.Frame(topbar)
        race_row.pack(fill="x", pady=(6, 0))
        ttk.Label(race_row, text="Racetime URL:").pack(side="left")
        ttk.Entry(race_row, textvariable=self.urlvar, width=50).pack(side="left", padx=6)
        ttk.Button(race_row, text="Find Current Race", command=self.get_current).pack(side="left")

        options = ttk.Frame(topbar)
        options.pack(fill="x", pady=(6, 0))
        self.ratio_frame = ttk.Frame(options)
        self.ratio_frame.pack(side="left")
        ttk.Label(self.ratio_frame, text="Aspect Ratio:").pack(side="left", padx=(0, 4))
        self.btn_169 = ttk.Button(self.ratio_frame, text="16:9", command=lambda: self.set_global_ratio("16:9"))
        self.btn_169.pack(side="left", padx=2)
        self.btn_1610 = ttk.Button(self.ratio_frame, text="16:10", command=lambda: self.set_global_ratio("16:10"))
        self.btn_1610.pack(side="left", padx=(2, 12))
        self.refresh_ratio_buttons()

        self.height_label = ttk.Label(options, text="Name Height:")
        self.height_label.pack(side="left")
        vcmd_height = (self.root.register(self.validate_height), '%P')
        self.height_entry = ttk.Entry(options, textvariable=self.name_height_var, width=5, validate='key', validatecommand=vcmd_height)
        self.height_entry.pack(side="left", padx=4)
        ttk.Button(options, text="Reset All Positions", command=self.reset_stream_positions).pack(side="left", padx=4)
        resize_mark = "[X]" if self.auto_resize_active.get() else "[ ]"
        self.btn_auto_resize = ttk.Button(options, text=f"{resize_mark} Auto Resize Streams", command=self.toggle_auto_resize)
        self.btn_auto_resize.pack(side="left", padx=4)

        self.name_pos_frame = ttk.Frame(topbar)
        ttk.Label(self.name_pos_frame, text="Name Position:").pack(side="left", padx=(0, 4))
        self.name_pos_buttons = {}
        for key, label in (
            ("top_left", "Top Left"),
            ("top_right", "Top Right"),
            ("bottom_left", "Bottom Left"),
            ("bottom_right", "Bottom Right"),
        ):
            btn = ttk.Button(self.name_pos_frame, text=label, command=lambda k=key: self.set_name_position(k))
            btn.pack(side="left", padx=2)
            self.name_pos_buttons[key] = btn
        self.refresh_name_pos_buttons()

        self.timer_row = ttk.Frame(topbar)
        self.timer_row.pack(fill="x", pady=(6, 0))
        ttk.Label(self.timer_row, text="Finished Timer:").pack(side="left", padx=(0, 4))
        vcmd_timer = (self.root.register(self.validate_timer), '%P')
        self.delay_entry = ttk.Entry(self.timer_row, textvariable=self.remove_delay_var, width=5, validate='key', validatecommand=vcmd_timer)
        self.delay_entry.pack(side="left")
        self.btn_auto_remove = ttk.Button(self.timer_row, text="[ ] Auto Remove Finished", command=self.toggle_auto_remove)
        self.btn_auto_remove.pack(side="left", padx=4)
        self.update_button_text()
        ttk.Button(self.timer_row, text="Refresh All Streams", command=self.refresh_all_streams).pack(side="left", padx=4)
        self.btn_multi_audio = ttk.Button(self.timer_row, text="[ ] Multiple Audio", command=self.toggle_multi_audio)
        self.btn_multi_audio.pack(side="left", padx=4)
        self.refresh_multi_audio_button()

        self.playersection = ttk.Frame(root, padding=(10, 4, 10, 4))
        self.playersection.pack(fill="both", expand=True)
        self.playersection.columnconfigure(0, weight=1)
        self.playersection.columnconfigure(1, weight=0)
        self.playersection.rowconfigure(0, weight=1)

        slotpane = ttk.LabelFrame(self.playersection, text="Player Slots", padding=6)
        slotpane.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.slots_frame = ttk.Frame(slotpane)
        self.slots_frame.pack(fill="both", expand=True)

        self.sidepanel = ttk.Frame(self.playersection)
        self.sidepanel.grid(row=0, column=1, sticky="nsew")

        self.swapsection = ttk.LabelFrame(self.sidepanel, text="Swap Players", padding=8)
        self.swapsection.pack(fill="x", pady=(0, 8))
        self.swap_a = tk.StringVar()
        self.swap_b = tk.StringVar()
        ttk.Label(self.swapsection, text="Slot A:").pack(anchor="w")
        self.swap_a_box = ttk.Combobox(self.swapsection, textvariable=self.swap_a, state="readonly", width=18)
        self.swap_a_box.pack(fill="x", pady=(0, 4))
        ttk.Label(self.swapsection, text="Slot B:").pack(anchor="w")
        self.swap_b_box = ttk.Combobox(self.swapsection, textvariable=self.swap_b, state="readonly", width=18)
        self.swap_b_box.pack(fill="x", pady=(0, 6))
        ttk.Button(self.swapsection, text="Swap", command=self.swap_selected_slots).pack(fill="x")
        self.swap_a_box.bind("<Button-1>", lambda e: self.refresh_swap_choices())
        self.swap_b_box.bind("<Button-1>", lambda e: self.refresh_swap_choices())

        self.blacklistsection = ttk.LabelFrame(self.sidepanel, text="Removed Players", padding=10)
        self.blacklistsection.pack(fill="both", expand=True)

        self.blacklist_container = ttk.Frame(self.blacklistsection)
        self.blacklist_container.pack(fill="both", expand=True)

        self.rebuild_player_ui()
        self.update_config_section_visibility()

        self.status_var = tk.StringVar(value="Enter an OBS password and click start")
        self.status_label = ttk.Label(root, textvariable=self.status_var, relief="sunken", style="TLabel")
        self.status_label.pack(side="bottom", fill="x")
        self.fit_window_height()
        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def _init_layout_state(self):
        full = self.profile["slots_per_scene"]
        self.current_layout_state = {scene: full for scene in self.profile["scenes"]}
        self.scene_signatures = {scene: None for scene in self.profile["scenes"]}
        self.scenemap = {scene: {} for scene in self.profile["scenes"]}

    def on_profile_change(self):
        if self.is_monitoring:
            self.profile_var.set(self.profile_key)
            self.log("Disconnect from OBS before changing scene collection.")
            return

        new_key = self.profile_var.get()
        if new_key == self.profile_key:
            return

        self.profile_key = new_key
        self.profile = SCENE_PROFILES[new_key]
        self.blacklist = {}
        self.lastrt = []
        self.active_race_url = ""
        self.slots = []
        self.source_owner = {}
        self.source_channels = {}
        self.slot_targets = {}
        self.source_scene = {}
        self.audio_slots = self.default_audio_slots()
        self._init_layout_state()
        self.save_config()
        self.rebuild_player_ui()
        self.update_config_section_visibility()
        self.log(f"Scene collection: {self.profile['label']}")
        self.fit_window_height()

    def fit_window_height(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        if width < self.root.minsize()[0]:
            width = 1280
        self.root.geometry(f"{width}x{self.root.winfo_reqheight()}")

    def update_config_section_visibility(self):
        if self.profile.get("aspect_ratio", True):
            self.ratio_frame.pack(side="left", before=self.height_label)
        else:
            self.ratio_frame.pack_forget()
        self.name_pos_frame.pack(fill="x", pady=(6, 0), before=self.timer_row)

    def rebuild_player_ui(self):
        for widget in self.slots_frame.winfo_children():
            widget.destroy()
        self.slots = []

        max_slots = self.profile["max_slots"]
        slots_per_scene = self.profile["slots_per_scene"]
        scenes = self.profile["scenes"]

        for i in range(1, max_slots + 1):
            if self.profile["layout_controls"]:
                first_slot_of_scene = ((i - 1) // slots_per_scene) * slots_per_scene + 1
                if i == first_slot_of_scene:
                    scene_name = scenes[(i - 1) // slots_per_scene]
                    if i > 1:
                        ttk.Separator(self.slots_frame, orient="horizontal").pack(fill="x", pady=8)

                    ctrl_frame = ttk.Frame(self.slots_frame)
                    ctrl_frame.pack(fill="x", pady=(2, 4))
                    ttk.Label(ctrl_frame, text=f"{scene_name} Layout:", font=("Helvetica", 9, "bold")).pack(side="left", padx=(2, 6))
                    for count in self.profile.get("layout_counts", [6, 4, 2, 1]):
                        ttk.Button(
                            ctrl_frame,
                            text=f"{count}P",
                            width=4,
                            command=lambda s=scene_name, c=count: self.set_layout(s, c)
                        ).pack(side="left", padx=2)

            self.create_slot(self.slots_frame, i)

        self.update_blacklist()
        self.refresh_audio_buttons()
        self.refresh_swap_choices()

    def saved_bool(self, key, fallback=False):
        try:
            return self.config.getboolean("Settings", key, fallback=fallback)
        except Exception:
            return fallback

    def saved_choice(self, key, allowed, fallback):
        value = self.config.get("Settings", key, fallback=fallback) if self.config.has_section("Settings") else fallback
        return value if value in allowed else fallback

    def saved_int(self, key, fallback, low, high):
        try:
            value = self.config.getint("Settings", key, fallback=fallback)
        except Exception:
            return fallback
        if low <= value <= high:
            return value
        return fallback

    def validate_timer(self, P):
        if P == "": return True
        if P.isdigit():
            val = int(P)
            return 0 <= val <= 45
        return False

    def get_remove_delay(self):
        try:
            return int(self.remove_delay_var.get())
        except ValueError:
            return 10

    def validate_height(self, P):
        if P == "": return True
        if P.isdigit():
            val = int(P)
            return 0 <= val <= 100
        return False

    def get_name_height(self):
        try:
            return float(self.name_height_var.get())
        except ValueError:
            return 75.0

    def update_button_text(self):
        state = "[X]" if self.auto_remove_finished.get() else "[ ]"
        timer = self.remove_delay_var.get() or "0"
        self.btn_auto_remove.config(text=f"{state} Auto Remove Finished [{timer}s]")

    def on_name_height_changed(self):
        self.save_config()
        text = self.name_height_var.get()
        if text.isdigit() and 0 <= int(text) <= 100:
            self.apply_current_layouts()

    def apply_current_layouts(self):
        if not self.ws or not self.profile.get("layout_controls"):
            return
        for scene in self.profile["scenes"]:
            count = self.current_layout_state.get(scene) or self.profile["slots_per_scene"]
            self.set_layout(scene, count)

    def refresh_ratio_buttons(self):
        ratio = self.ratio_var.get()
        self.btn_169.config(text=("[X] " if ratio == "16:9" else "[ ] ") + "16:9")
        self.btn_1610.config(text=("[X] " if ratio == "16:10" else "[ ] ") + "16:10")

    def set_global_ratio(self, ratio):
        self.ratio_var.set(ratio)
        self.refresh_ratio_buttons()
        self.log(f"Global Aspect Ratio set to {ratio}")
        self.save_config()
        self.apply_current_layouts()

    def layout_for_count(self, active_count):
        for minimum, layout in self.profile.get("layout_rules", []):
            if active_count >= minimum:
                return layout
        return None

    def refresh_name_pos_buttons(self):
        current = self.name_pos_var.get()
        for key, btn in self.name_pos_buttons.items():
            label = btn.cget("text").replace("[X] ", "").replace("[ ] ", "")
            mark = "[X]" if key == current else "[ ]"
            btn.config(text=f"{mark} {label}")

    def set_name_position(self, pos):
        if pos not in NAME_CORNERS:
            return
        self.name_pos_var.set(pos)
        self.refresh_name_pos_buttons()
        self.save_config()
        self.apply_current_layouts()

    def set_layout(self, scene_name, player_count):
        if not self.profile["layout_controls"]:
            return
        if not self.ws:
            messagebox.showwarning("Connection Error", "Connect to OBS first.")
            return

        layout_map = self.profile.get("layout_map", {6: (3, 2), 4: (2, 2), 2: (2, 1), 1: (1, 1)})
        if player_count not in layout_map:
            return

        if self.profile.get("layout_active_only") and player_count < self.profile["slots_per_scene"]:
            self.compact_scene_to_front(scene_name)

        canvas_width = 1920
        max_height = self.profile.get("layout_max_height", 806)
        gap = self.profile.get("layout_gap", 3)
        padding = self.profile.get("layout_padding", 5)

        selected_ratio = self.ratio_var.get() if self.profile.get("aspect_ratio", True) else "16:9"
        ratio_w, ratio_h = (16, 10) if selected_ratio == "16:10" else (16, 9)

        cols, rows = layout_map[player_count]

        cell_width = (canvas_width - (gap * 2) - (gap * (cols - 1))) / cols
        cell_height = (max_height - (gap * 2) - (gap * (rows - 1))) / rows

        s_width = cell_width
        s_height = (s_width / ratio_w) * ratio_h

        if s_height > cell_height:
            s_height = cell_height
            s_width = (s_height / ratio_h) * ratio_w

        x_offset = (cell_width - s_width) / 2
        y_offset = (cell_height - s_height) / 2
        pos_key = self.name_pos_var.get() if self.profile.get("name_positions") else "top_right"
        align = NAME_CORNERS.get(pos_key, 6)
        name_height = self.get_name_height()

        try:
            resp = self.ws.call(obs_requests.GetSceneItemList(sceneName=scene_name))
            items = resp.getSceneItems()
            scene_slots = [s for s in self.slots if s['scene'] == scene_name]
            if self.profile.get("layout_active_only") and player_count < len(scene_slots):
                targets = [s for s in scene_slots if s['namevar'].get().strip()][:player_count]
                if not targets:
                    targets = scene_slots[:player_count]
            else:
                targets = scene_slots[:player_count]

            for idx, slot in enumerate(targets):
                col = idx % cols
                row = idx // cols
                sx = gap + (col * (cell_width + gap)) + x_offset
                sy = gap + (row * (cell_height + gap)) + y_offset
                stream_transform = {
                    "positionX": float(sx), "positionY": float(sy),
                    "boundsType": "OBS_BOUNDS_STRETCH",
                    "boundsWidth": float(s_width), "boundsHeight": float(s_height),
                    "alignment": 5
                }
                self.slot_targets[slot['index'] - 1] = {
                    "scene": scene_name,
                    "transform": dict(stream_transform),
                }

                source_name = slot.get("browsersource")
                if source_name:
                    sid = next((i['sceneItemId'] for i in items if i['sourceName'] == source_name), None)
                    if sid is not None:
                        self.ws.call(obs_requests.SetSceneItemTransform(
                            sceneName=scene_name, sceneItemId=sid,
                            sceneItemTransform=stream_transform
                        ))

                nid = next((i['sceneItemId'] for i in items if i['sourceName'] == slot['textsource']), None)
                if nid is not None:
                    px, py = name_corner_pos(pos_key, sx, sy, s_width, s_height, padding, name_height)
                    if self.profile.get("name_positions"):
                        text_align = "left" if pos_key.endswith("left") else "right"
                        self.ws.call(obs_requests.SetInputSettings(
                            inputName=slot['textsource'],
                            inputSettings={"align": text_align}
                        ))
                    self.ws.call(obs_requests.SetSceneItemTransform(
                        sceneName=scene_name,
                        sceneItemId=nid,
                        sceneItemTransform={
                            "positionX": float(px),
                            "positionY": float(py),
                            "alignment": align, "boundsAlignment": align,
                            "boundsType": "OBS_BOUNDS_SCALE_INNER",
                            "boundsWidth": float(s_width - (padding * 2)),
                            "boundsHeight": name_height,
                            "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0,
                            "scaleX": 1.0, "scaleY": 1.0
                        }
                    ))
            self.log(f"{scene_name} -> {player_count}P ({selected_ratio})")
        except Exception as e:
            self.log(f"Could not set the layout. {e}")

    def default_slot_targets(self):
        targets = {}
        player_count = self.profile["slots_per_scene"]
        layout_map = self.profile.get("layout_map", {6: (3, 2), 4: (2, 2), 2: (2, 1), 1: (1, 1)})
        cols, rows = layout_map[player_count]
        canvas_width = 1920
        max_height = self.profile.get("layout_max_height", 806)
        gap = self.profile.get("layout_gap", 3)
        selected_ratio = self.ratio_var.get() if self.profile.get("aspect_ratio", True) else "16:9"
        ratio_w, ratio_h = (16, 10) if selected_ratio == "16:10" else (16, 9)
        cell_width = (canvas_width - (gap * 2) - (gap * (cols - 1))) / cols
        cell_height = (max_height - (gap * 2) - (gap * (rows - 1))) / rows
        s_width = cell_width
        s_height = (s_width / ratio_w) * ratio_h
        if s_height > cell_height:
            s_height = cell_height
            s_width = (s_height / ratio_h) * ratio_w
        x_offset = (cell_width - s_width) / 2
        y_offset = (cell_height - s_height) / 2
        for slot in self.slots:
            index = slot["index"] - 1
            idx = index % player_count
            col = idx % cols
            row = idx // cols
            sx = gap + (col * (cell_width + gap)) + x_offset
            sy = gap + (row * (cell_height + gap)) + y_offset
            targets[index] = {
                "scene": slot["scene"],
                "transform": {
                    "positionX": float(sx),
                    "positionY": float(sy),
                    "boundsType": "OBS_BOUNDS_STRETCH",
                    "boundsWidth": float(s_width),
                    "boundsHeight": float(s_height),
                    "alignment": 5,
                },
            }
        return targets

    def reset_stream_positions(self):
        if not self.profile["layout_controls"]:
            return
        for scene in self.profile["scenes"]:
            self.set_layout(scene, self.profile["slots_per_scene"])
            self.order_scene_slots(scene)
            self.current_layout_state[scene] = self.profile["slots_per_scene"]

    def toggle_auto_resize(self):
        new_val = not self.auto_resize_active.get()
        self.auto_resize_active.set(new_val)
        state = "[X]" if new_val else "[ ]"
        self.btn_auto_resize.config(text=f"{state} Auto Resize Streams")
        self.log(f"Auto Resize: {'Enabled' if new_val else 'Disabled'}")
        self.save_config()
        if new_val:
            self.auto_adjust_layouts()

    def compact_scene_to_front(self, scene_name):
        scene_slots = [slot for slot in self.slots if slot['scene'] == scene_name]
        if not scene_slots:
            return
        start = scene_slots[0]['index'] - 1
        end = start + len(scene_slots)
        names = [slot['namevar'].get() for slot in self.slots]
        current = names[start:end]
        packed = [name for name in current if name.strip()]
        packed += [""] * (len(current) - len(packed))
        if current == packed:
            return
        names[start:end] = packed
        self.new_slot_order(names)

    def auto_adjust_layouts(self):
        if not self.profile["layout_controls"] or not self.auto_resize_active.get():
            return

        slots_per = self.profile["slots_per_scene"]
        for scene_name in self.profile["scenes"]:
            scene_slots = [slot for slot in self.slots if slot['scene'] == scene_name]
            signature = tuple(slot['namevar'].get().strip().lower() for slot in scene_slots)
            active_count = sum(1 for name in signature if name)
            layout = self.layout_for_count(active_count)
            prev_layout = self.current_layout_state.get(scene_name)
            prev_sig = self.scene_signatures.get(scene_name)
            shrunk = layout is not None and layout < slots_per
            if layout and (layout != prev_layout or (shrunk and signature != prev_sig)):
                self.set_layout(scene_name, layout)
                self.current_layout_state[scene_name] = layout
                signature = tuple(slot['namevar'].get().strip().lower() for slot in scene_slots)
            self.scene_signatures[scene_name] = signature

    def cache_scene_items(self):
        self.scenemap = {scene: {} for scene in self.profile["scenes"]}
        for scene in self.profile["scenes"]:
            try:
                resp = self.ws.call(obs_requests.GetSceneItemList(sceneName=scene))
                items = resp.getSceneItems()
                for item in items:
                    name = item.get('sourceName')
                    iid = item.get('sceneItemId')
                    self.scenemap[scene][name] = iid
            except Exception as e:
                self.log(f"Could not read the scene. {e}")

    def get_item_id(self, scene, sourcename):
        return self.scenemap.get(scene, {}).get(sourcename)

    def check_for_updates(self):
        ignored = self.config.get("Settings", "IgnoreVersion", fallback="")
        try:
            r = requests.get(version_url, timeout=5)
            if r.status_code == 200:
                latest = r.text.strip()
                if latest != version and latest != ignored:
                    self.root.after(0, lambda: self.show_update_dialog(latest))
        except Exception:
            pass

    def show_update_dialog(self, latest_version):
        update_win = tk.Toplevel(self.root)
        update_win.title("Available Update")
        update_win.geometry("400x130")
        update_win.resizable(False, False)
        update_win.attributes("-topmost", True)

        ttk.Label(update_win, text=f"A new update (v{latest_version}) is available.", padding=10).pack()

        btn_frame = ttk.Frame(update_win)
        btn_frame.pack(pady=10)

        def open_link():
            webbrowser.open(releases_url)
            update_win.destroy()

        def ignore_permanently():
            if 'Settings' not in self.config:
                self.config['Settings'] = {}
            self.config['Settings']['IgnoreVersion'] = latest_version
            self.save_config()
            self.log(f"Version {latest_version} will be ignored.")
            update_win.destroy()

        ttk.Button(btn_frame, text="Go to Page", command=open_link).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Ignore Once", command=update_win.destroy).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Ignore Permanently", command=ignore_permanently).grid(row=0, column=2, padx=5)

    def get_current(self):
        try:
            r = requests.get("https://racetime.gg/hitman-3/data", timeout=5)
            if r.status_code == 200:
                data = r.json()
                active = data.get('current_races', [])
                openr = [race for race in active if race.get('status', {}).get('value') == 'open']

                if openr:
                    target = openr[0].get('data_url')
                    self.urlvar.set(f"https://racetime.gg{target}")
                    self.log("Race found.")
                elif active:
                    target = active[0].get('data_url')
                    self.urlvar.set(f"https://racetime.gg{target}")
                    self.log("Active race used.")
                else:
                    self.log("No active hitman-3 races found.")
        except Exception as e:
            self.log(e)

    def save_config(self):
        if 'Settings' not in self.config:
            self.config['Settings'] = {}
        self.config['Settings']['OBSPW'] = self.pwvar.get()
        self.config['Settings']['SceneProfile'] = self.profile_key
        self.config['Settings']['AspectRatio'] = self.ratio_var.get()
        self.config['Settings']['NamePosition'] = self.name_pos_var.get()
        self.config['Settings']['NameHeight'] = self.name_height_var.get()
        self.config['Settings']['FinishedTimer'] = self.remove_delay_var.get()
        self.config['Settings']['AutoRemove'] = "true" if self.auto_remove_finished.get() else "false"
        self.config['Settings']['AutoResize'] = "true" if self.auto_resize_active.get() else "false"
        self.config['Settings']['MultipleAudio'] = "true" if self.multi_audio else "false"
        with open(get_external_path("config.ini"), 'w') as cfgfile:
            self.config.write(cfgfile)

    def on_close(self):
        self.save_config()
        self.is_monitoring = False
        if self.ws:
            self.shutdown_obs_check()
            self.ws.disconnect()
        self.root.destroy()

    def log(self, msg):
        self.status_var.set(msg)
        print(msg)

    def get_name(self, streamlink):
        if not isinstance(streamlink, str) or not streamlink:
            return ""
        if '/' not in streamlink and '.' not in streamlink:
            return streamlink
        match = twitchregex.search(streamlink)
        return match.group(1) if match else ""

    def entrant_user(self, entrant):
        user = entrant.get('user') if isinstance(entrant, dict) else None
        return user if isinstance(user, dict) else {}

    def update_obs(self, slot, entrant):
        self.sync_streams()
        self.log(f"{self.entrant_user(entrant).get('name', '')} is in slot {slot['index']}")

    def update_obs_name(self, slot, newname):
        if self.ws:
            self.ws.call(obs_requests.SetInputSettings(inputName=slot['textsource'], inputSettings={"text": newname}))

    def source_names(self):
        return [f"Stream {i}" for i in range(1, self.profile["max_slots"] + 1)]

    def slot_channel(self, name):
        if not name:
            return ""
        for entrant in self.lastrt or []:
            user = self.entrant_user(entrant)
            if user.get('name', '').lower() == name.lower():
                return self.get_name(user.get('twitch_channel')).lower()
        return ""

    def items_named(self, scene, source_name):
        try:
            resp = self.ws.call(obs_requests.GetSceneItemList(sceneName=scene))
            if not resp.status:
                return []
            return [item.get("sceneItemId") for item in resp.getSceneItems()
                    if item.get("sourceName") == source_name and item.get("sceneItemId") is not None]
        except Exception:
            return []

    def find_source_item(self, source_name):
        for scene in self.profile["scenes"]:
            ids = self.items_named(scene, source_name)
            if ids:
                self.source_scene[source_name] = scene
                return scene, ids[0]
        return None, None

    def startup_obs_check(self):
        try:
            listed = self.ws.call(obs_requests.GetInputList()).getInputs()
            present = {item.get("inputName") for item in listed}
        except Exception as e:
            self.log(f"Could not check OBS. {e}")
            return
        for index, source_name in enumerate(self.source_names()):
            bg_name = f"{source_name} BG"
            if bg_name in present:
                try:
                    self.ws.call(obs_requests.RemoveInput(inputName=bg_name))
                    present.discard(bg_name)
                except Exception:
                    pass
            tmp_name = f"__tmp_stream_{index + 1}__"
            if tmp_name in present:
                try:
                    if source_name not in present:
                        self.ws.call(obs_requests.SetInputName(inputName=tmp_name, newInputName=source_name))
                        present.discard(tmp_name)
                        present.add(source_name)
                    else:
                        self.ws.call(obs_requests.RemoveInput(inputName=tmp_name))
                        present.discard(tmp_name)
                except Exception:
                    pass
        missing = [name for name in missing_profile_sources(self.profile) if name not in present]
        if missing:
            self.log("Missing " + ", ".join(missing))
        else:
            self.log("OBS sources are there")

        has_active_players = any(slot['namevar'].get().strip() for slot in self.slots)
        self.slot_targets = self.default_slot_targets()
        for index, source_name in enumerate(self.source_names()):
            self.slots[index]['browsersource'] = source_name
            if not has_active_players:
                if source_name in present:
                    try:
                        self.ws.call(obs_requests.SetInputSettings(
                            inputName=source_name,
                            inputSettings={"url": "about:blank"}
                        ))
                    except Exception:
                        pass
                self.source_channels[source_name] = ""
                self.source_owner[source_name] = ""
            else:
                if source_name in present:
                    try:
                        settings = self.ws.call(obs_requests.GetInputSettings(inputName=source_name)).getInputSettings()
                        self.source_channels[source_name] = channel_from_url(settings.get("url", ""))
                    except Exception:
                        self.source_channels[source_name] = ""
                self.source_owner.setdefault(source_name, "")
            try:
                self.place_source(source_name, index)
                present.add(source_name)
            except Exception as e:
                self.log(f"Could not place {source_name}: {e}")
            if not has_active_players:
                self.place_name(index, "")

        self.reset_stream_positions()
        self.cache_scene_items()
        self.audio_slots = self.default_audio_slots()
        if not self.multi_audio:
            self.enforce_one_audio_per_scene()
        self.refresh_audio_buttons()
        loaded = sum(1 for channel in self.source_channels.values() if channel)
        self.log(f"{loaded} streams are already loaded")
        self.update_slot_visibility()
        self.apply_slot_audio()

    def reset_for_new_race(self):
        self.blacklist = {}
        self.lastrt = []
        self.source_owner = {src: "" for src in self.source_names()}
        self.source_channels = {src: "" for src in self.source_names()}
        self.audio_slots = self.default_audio_slots()
        if not self.multi_audio:
            self.enforce_one_audio_per_scene()
        self._init_layout_state()
        self.slot_targets = self.default_slot_targets()
        for index, slot in enumerate(self.slots):
            source_name = f"Stream {index + 1}"
            slot['browsersource'] = source_name
            slot['namevar'].set("")
            slot['finishtime'] = None
            self.refresh_slot_status(slot)
            if self.ws:
                try:
                    self.ws.call(obs_requests.SetInputSettings(
                        inputName=source_name,
                        inputSettings={"url": "about:blank"}
                    ))
                except Exception:
                    pass
                try:
                    self.place_source(source_name, index)
                except Exception:
                    pass
                self.place_name(index, "")
        if self.ws:
            self.reset_stream_positions()
            self.update_slot_visibility()
            self.apply_slot_audio()
        self.update_blacklist()
        self.refresh_audio_buttons()
        self.refresh_swap_choices()

    def shutdown_obs_check(self):
        try:
            listed = self.ws.call(obs_requests.GetInputList()).getInputs()
            present = {item.get("inputName") for item in listed}
            missing = [name for name in missing_profile_sources(self.profile) if name not in present]
            assigned = sum(1 for slot in self.slots if slot['namevar'].get().strip())
            loaded = sum(1 for channel in self.source_channels.values() if channel)
            self.log(f"Closing with {assigned} players and {loaded} loaded streams")
        except Exception as e:
            self.log(f"Could not check OBS before closing. {e}")

    def input_exists(self, source_name):
        try:
            resp = self.ws.call(obs_requests.GetInputSettings(inputName=source_name))
            return bool(resp.status)
        except Exception:
            return False

    def browser_settings(self, channel):
        return {
            "url": twitchlink.format(channel) if channel else "about:blank",
            "width": 1920,
            "height": 1080,
            "reroute_audio": True,
        }

    def create_browser_source(self, source_name, scene, channel):
        resp = self.ws.call(obs_requests.CreateInput(
            sceneName=scene,
            inputName=source_name,
            inputKind="browser_source",
            inputSettings=self.browser_settings(channel),
            sceneItemEnabled=True,
        ))
        if resp.status:
            self.source_channels[source_name] = (channel or "").lower()
            self.log(f"Created {source_name} on {scene}")
        return bool(resp.status)

    def place_source(self, source_name, slot_index, channel=""):
        target = self.slot_targets.get(slot_index)
        if not target:
            self.log(f"No position for slot {slot_index + 1}")
            return
        target_scene = target["scene"]
        target_ids = self.items_named(target_scene, source_name)
        if not target_ids:
            if not self.input_exists(source_name):
                if not self.create_browser_source(source_name, target_scene, channel):
                    raise RuntimeError(f"OBS did not create {source_name}")
            else:
                created = self.ws.call(obs_requests.CreateSceneItem(
                    sceneName=target_scene,
                    sourceName=source_name,
                    sceneItemEnabled=True
                ))
                if not created.status:
                    raise RuntimeError(f"OBS did not add {source_name} to {target_scene}")
            target_ids = self.items_named(target_scene, source_name)
        if not target_ids:
            raise RuntimeError(f"OBS did not add {source_name} to {target_scene}")
        item_id = target_ids[0]
        for extra_id in target_ids[1:]:
            self.ws.call(obs_requests.RemoveSceneItem(sceneName=target_scene, sceneItemId=extra_id))
        self.ws.call(obs_requests.SetSceneItemTransform(
            sceneName=target_scene,
            sceneItemId=item_id,
            sceneItemTransform=target["transform"]
        ))
        for other_scene in self.profile["scenes"]:
            if other_scene == target_scene:
                continue
            for old_id in self.items_named(other_scene, source_name):
                self.ws.call(obs_requests.RemoveSceneItem(sceneName=other_scene, sceneItemId=old_id))
        self.source_scene[source_name] = target_scene

    def order_scene_slots(self, scene_name):
        if not self.ws or self.profile["visibility"] == "folder":
            return
        scene_slots = [s for s in self.slots if s["scene"] == scene_name]
        if not scene_slots:
            return
        desired = []
        for slot in reversed(scene_slots):
            desired.append(f"Stream {slot['index']}")
            desired.append(slot["textsource"])
        desired_set = set(desired)
        try:
            items = self.ws.call(obs_requests.GetSceneItemList(sceneName=scene_name)).getSceneItems() or []
        except Exception:
            return
        present_indices = [idx for idx, item in enumerate(items) if item.get("sourceName") in desired_set]
        if not present_indices:
            return
        base_index = min(present_indices)
        order = [item.get("sourceName") for item in items]
        id_by_name = {
            item.get("sourceName"): item.get("sceneItemId")
            for item in items
            if item.get("sourceName") in desired_set and item.get("sceneItemId") is not None
        }
        target_pos = base_index
        for name in desired:
            item_id = id_by_name.get(name)
            if item_id is None or name not in order:
                continue
            cur_pos = order.index(name)
            if cur_pos != target_pos:
                try:
                    self.ws.call(obs_requests.SetSceneItemIndex(
                        sceneName=scene_name,
                        sceneItemId=item_id,
                        sceneItemIndex=target_pos
                    ))
                    order.pop(cur_pos)
                    order.insert(target_pos, name)
                except Exception:
                    pass
            target_pos += 1

    def name_item_transform(self, video_transform):
        sw = float(video_transform.get("boundsWidth") or 0)
        sh = float(video_transform.get("boundsHeight") or 0)
        if sw <= 1 or sh <= 1:
            return None
        sx = float(video_transform.get("positionX", 0))
        sy = float(video_transform.get("positionY", 0))
        padding = self.profile.get("layout_padding", 5)
        name_height = self.get_name_height()
        pos_key = self.name_pos_var.get() if self.profile.get("name_positions") else "top_right"
        align = NAME_CORNERS.get(pos_key, 6)
        px, py = name_corner_pos(pos_key, sx, sy, sw, sh, padding, name_height)
        return pos_key, {
            "positionX": float(px),
            "positionY": float(py),
            "alignment": align,
            "boundsAlignment": align,
            "boundsType": "OBS_BOUNDS_SCALE_INNER",
            "boundsWidth": float(max(1, sw - (padding * 2))),
            "boundsHeight": name_height,
            "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0,
            "scaleX": 1.0, "scaleY": 1.0,
        }

    def raise_source(self, scene, source_name):
        ids = self.items_named(scene, source_name)
        if not ids:
            return
        try:
            items = self.ws.call(obs_requests.GetSceneItemList(sceneName=scene)).getSceneItems() or []
            self.ws.call(obs_requests.SetSceneItemIndex(
                sceneName=scene,
                sceneItemId=ids[0],
                sceneItemIndex=max(0, len(items) - 1),
            ))
        except Exception:
            pass

    def place_name(self, slot_index, text):
        slot = self.slots[slot_index]
        self.update_obs_name(slot, text)
        target = self.slot_targets.get(slot_index)
        if not target:
            return
        scene = target["scene"]
        source_name = slot["textsource"]
        ids = self.items_named(scene, source_name)
        if not ids:
            return
        placed = self.name_item_transform(target["transform"])
        if placed:
            pos_key, transform = placed
            text_align = "left" if str(pos_key).endswith("left") else "right"
            self.ws.call(obs_requests.SetInputSettings(
                inputName=source_name,
                inputSettings={"align": text_align}
            ))
            self.ws.call(obs_requests.SetSceneItemTransform(
                sceneName=scene,
                sceneItemId=ids[0],
                sceneItemTransform=transform
            ))
        self.ws.call(obs_requests.SetSceneItemEnabled(
            sceneName=scene,
            sceneItemId=ids[0],
            sceneItemEnabled=bool(text)
        ))

    def rename_sources_for_slots(self, full_assignment):
        sources = self.source_names()
        renames = [
            (i, full_assignment[i], sources[i])
            for i in range(min(len(full_assignment), len(sources)))
            if full_assignment[i] and full_assignment[i] != sources[i]
        ]
        if not renames:
            return
        for i, old_src, _ in renames:
            tmp_name = f"__tmp_stream_{i + 1}__"
            self.ws.call(obs_requests.SetInputName(
                inputName=old_src,
                newInputName=tmp_name
            ))
        for i, _, target_src in renames:
            tmp_name = f"__tmp_stream_{i + 1}__"
            self.ws.call(obs_requests.SetInputName(
                inputName=tmp_name,
                newInputName=target_src
            ))

    def default_audio_slots(self):
        step = self.profile["slots_per_scene"]
        return set(range(0, self.profile["max_slots"], step))

    def toggle_multi_audio(self):
        self.multi_audio = not self.multi_audio
        if not self.multi_audio:
            self.enforce_one_audio_per_scene()
        self.refresh_multi_audio_button()
        self.refresh_audio_buttons()
        self.apply_slot_audio()
        self.log(f"Multiple Audio: {'On' if self.multi_audio else 'Off'}")
        self.save_config()

    def refresh_multi_audio_button(self):
        if not hasattr(self, "btn_multi_audio") or not self.btn_multi_audio:
            return
        state = "[X]" if self.multi_audio else "[ ]"
        self.btn_multi_audio.config(text=f"{state} Multiple Audio")

    def has_multiple_audio_in_scene(self):
        step = self.profile["slots_per_scene"]
        counts = {}
        for idx in self.audio_slots:
            scene_key = idx // step
            counts[scene_key] = counts.get(scene_key, 0) + 1
            if counts[scene_key] > 1:
                return True
        return False

    def on_obs_mute_changed(self, event):
        if self.applying_audio:
            return
        try:
            input_name = event.getInputName()
            muted = bool(event.getInputMuted())
        except Exception:
            return
        if not input_name or not input_name.startswith("Stream "):
            return
        suffix = input_name[7:]
        if not suffix.isdigit():
            return
        slot_index = int(suffix) - 1
        if not (0 <= slot_index < self.profile["max_slots"]):
            return
        self.root.after(0, lambda idx=slot_index, m=muted: self.handle_obs_mute_change(idx, m))

    def handle_obs_mute_change(self, slot_index, muted):
        if muted:
            if slot_index not in self.audio_slots:
                return
            self.audio_slots.discard(slot_index)
            self.refresh_audio_buttons()
            self.log(f"Slot {slot_index + 1} audio is off")
        else:
            if slot_index in self.audio_slots:
                return
            self.audio_slots.add(slot_index)
            if not self.multi_audio and self.has_multiple_audio_in_scene():
                self.multi_audio = True
                self.refresh_multi_audio_button()
            self.refresh_audio_buttons()
            self.log(f"Slot {slot_index + 1} audio is on")

    def enforce_one_audio_per_scene(self):
        step = self.profile["slots_per_scene"]
        kept = set()
        for index in sorted(self.audio_slots):
            scene_key = index // step
            if any(other // step == scene_key for other in kept):
                continue
            kept.add(index)
        self.audio_slots = kept

    def set_audio_slot(self, index):
        if index in self.audio_slots:
            self.audio_slots.discard(index)
            self.log(f"Audio off slot {index + 1}")
        else:
            if not self.multi_audio:
                step = self.profile["slots_per_scene"]
                scene_start = (index // step) * step
                for other in range(scene_start, scene_start + step):
                    self.audio_slots.discard(other)
            self.audio_slots.add(index)
            self.log(f"Audio on slot {index + 1}")
        self.refresh_audio_buttons()
        self.apply_slot_audio()

    def refresh_audio_buttons(self):
        for slot in self.slots:
            btn = slot.get("audiobtn")
            if not btn:
                continue
            if slot["index"] - 1 in self.audio_slots:
                btn.config(text="No Audio")
            else:
                btn.config(text="Audio")

    def apply_slot_audio(self):
        if not self.ws:
            return
        self.applying_audio = True
        try:
            for index, source_name in enumerate(self.source_names()):
                try:
                    self.ws.call(obs_requests.SetInputMute(
                        inputName=source_name,
                        inputMuted=index not in self.audio_slots
                    ))
                except Exception:
                    pass
        finally:
            self.applying_audio = False

    def set_source_enabled(self, source_name, enabled):
        scene, item_id = self.find_source_item(source_name)
        if item_id is None:
            return
        self.ws.call(obs_requests.SetSceneItemEnabled(
            sceneName=scene,
            sceneItemId=item_id,
            sceneItemEnabled=enabled
        ))

    def sync_streams(self):
        if not self.ws:
            return
        names = [slot['namevar'].get().strip() for slot in self.slots]
        channels = [self.slot_channel(name) for name in names]
        sources = self.source_names()
        for source_name in sources:
            self.source_owner.setdefault(source_name, "")
            self.source_channels.setdefault(source_name, "")
        assignment, owners, reloads = plan_source_assignment(
            names, channels, sources, self.source_owner, self.source_channels
        )
        full_assignment = complete_slot_sources(assignment, sources)
        try:
            self.rename_sources_for_slots(full_assignment)
        except Exception as e:
            self.log(f"Could not rename the streams. {e}")

        old_channels = dict(self.source_channels)
        self.source_owner = {
            sources[i]: owners.get(full_assignment[i], "")
            for i in range(len(sources))
        }
        self.source_channels = {
            sources[i]: old_channels.get(full_assignment[i], "")
            for i in range(len(sources))
        }
        new_reloads = {
            sources[i]: reloads[full_assignment[i]]
            for i in range(len(sources))
            if full_assignment[i] in reloads
        }

        for index, source_name in enumerate(sources):
            self.slots[index]['browsersource'] = source_name
            channel = new_reloads.get(source_name, "")
            if channel and self.input_exists(source_name):
                resp = self.ws.call(obs_requests.SetInputSettings(
                    inputName=source_name,
                    inputSettings={"url": twitchlink.format(channel)}
                ))
                if resp.status:
                    self.source_channels[source_name] = channel
                    self.log(f"Loaded {channel} on {source_name}")
            if names[index] or full_assignment[index] != source_name:
                try:
                    self.place_source(source_name, index, channel)
                except Exception as e:
                    self.log(f"Could not move {source_name}: {e}")
            self.place_name(index, names[index])
        for scene in self.profile["scenes"]:
            self.order_scene_slots(scene)
        self.update_slot_visibility()
        self.apply_slot_audio()
        self.refresh_swap_choices()

    def create_slot(self, parent, i):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)

        scene_index = (i - 1) // self.profile["slots_per_scene"]
        scene_name = self.profile["scenes"][scene_index]

        slot_data = {
            "index": i,
            "namevar": tk.StringVar(),
            "statuslbl": ttk.Label(frame, text="Empty", width=16),
            "scene": scene_name,
            "textsource": f"Streamer Name {i}",
            "browsersource": f"Stream {i}",
            "finishtime": None
        }

        if self.profile["visibility"] == "folder":
            slot_data["foldersource"] = f"Stream #{i}"

        ttk.Button(frame, text="Up", width=8, command=lambda idx=i-1: self.shift_player(idx, "up")).pack(side="left")
        ttk.Button(frame, text="Down", width=8, command=lambda idx=i-1: self.shift_player(idx, "down")).pack(side="left")
        ttk.Button(frame, text="Remove", width=8, command=lambda idx=i-1: self.remove_player(idx)).pack(side="left")
        ttk.Button(frame, text="Refresh", width=8, command=lambda idx=i-1: self.refresh_single_stream(idx)).pack(side="left")
        audiobtn = ttk.Button(frame, text="Audio", width=10, command=lambda idx=i-1: self.set_audio_slot(idx))
        audiobtn.pack(side="left")
        slot_data["audiobtn"] = audiobtn

        ttk.Label(frame, text=f"Slot {i}:", width=10).pack(side="left", padx=(6, 0))
        ttk.Entry(frame, textvariable=slot_data['namevar'], width=16).pack(side="left", padx=4)
        slot_data['statuslbl'].pack(side="left", padx=4)

        self.slots.append(slot_data)

    def update_blacklist(self):
        for widget in self.blacklist_container.winfo_children():
            widget.destroy()
        if not self.blacklist:
            ttk.Label(self.blacklist_container, text="No removed players").pack(pady=5, padx=5)
            return
        for lowername, original_name in self.blacklist.items():
            player_section = ttk.Frame(self.blacklist_container)
            player_section.pack(fill="x", pady=2)
            ttk.Button(player_section, text="+", width=2, command=lambda name=original_name: self.readd_player(name)).pack(side="left")
            ttk.Label(player_section, text=original_name, width=15, anchor="w").pack(side="left", padx=5)

    def remove_player(self, index_to_remove):
        playername = self.slots[index_to_remove]['namevar'].get()
        if not playername:
            return
        lowername = playername.lower()
        if lowername not in self.blacklist:
            self.blacklist[lowername] = playername
            self.update_blacklist()
        currentnames = [slot['namevar'].get() for slot in self.slots]
        newnames = fill_hole_names(currentnames, index_to_remove, self.profile["slots_per_scene"])
        self.new_slot_order(newnames)

    def remove_player_fill(self, index):
        playername = self.slots[index]['namevar'].get()
        if not playername:
            return
        lowername = playername.lower()
        if lowername not in self.blacklist:
            self.blacklist[lowername] = playername
            self.update_blacklist()
        currentnames = [slot['namevar'].get() for slot in self.slots]
        newnames = fill_hole_names(currentnames, index, self.profile["slots_per_scene"])
        self.new_slot_order(newnames)

    def readd_player(self, playername):
        emptyslots = next((i for i, slot in enumerate(self.slots) if not slot['namevar'].get()), None)
        if emptyslots is None:
            self.log("Slots full")
            return
        self.slots[emptyslots]['namevar'].set(playername)
        self.refresh_slot_status(self.slots[emptyslots])
        self.update_shift(self.slots[emptyslots], playername)
        self.update_slot_visibility(slot_index=emptyslots)
        del self.blacklist[playername.lower()]
        self.update_blacklist()

    def shift_player(self, index, direction):
        if not self.slots[index]['namevar'].get():
            return
        targets = index + (1 if direction == "down" else -1)
        if not (0 <= targets < len(self.slots)):
            return
        currentnames = [slot['namevar'].get() for slot in self.slots]
        currentnames[index], currentnames[targets] = currentnames[targets], currentnames[index]
        self.new_slot_order(currentnames)

    def new_slot_order(self, newnames):
        active_timers = {s['namevar'].get().lower(): s['finishtime']
                         for s in self.slots if s['namevar'].get()}
        changed = False

        for i, newname in enumerate(newnames):
            oldname = self.slots[i]['namevar'].get()

            if oldname != newname:
                self.slots[i]['namevar'].set(newname)
                if newname:
                    self.slots[i]['finishtime'] = active_timers.get(newname.lower())
                else:
                    self.slots[i]['finishtime'] = None
                self.refresh_slot_status(self.slots[i])
                changed = True
        if changed:
            self.sync_streams()
        self.refresh_swap_choices()

    def _finish_suffix(self, slot):
        if not slot['finishtime']:
            return ""
        remaining = max(0, self.get_remove_delay() - int(time.time() - slot['finishtime']))
        return f" ({remaining}s)"

    def refresh_slot_status(self, slot):
        playername = slot['namevar'].get().strip()
        if not playername:
            slot['statuslbl'].config(text="Empty", style="TLabel")
            return
        entrant = next((e for e in self.lastrt or [] if self.entrant_user(e).get('name', '').lower() == playername.lower()), None)
        if not entrant:
            slot['statuslbl'].config(text="Empty", style="TLabel")
            return
        status = (entrant.get('status') or {}).get('value')
        place = entrant.get('place')
        if status == "done":
            lbl = f"Finished: {place}"
            slot['statuslbl'].config(text=lbl + self._finish_suffix(slot), style="Done.TLabel")
        elif status == "dnf":
            lbl = "DNF"
            slot['statuslbl'].config(text=lbl + self._finish_suffix(slot), style="DNF.TLabel")
        else:
            slot['statuslbl'].config(text="Racing", style="Racing.TLabel")
            slot['finishtime'] = None

    def slot_choice_label(self, index):
        name = self.slots[index]['namevar'].get().strip()
        shown = name if name else "(empty)"
        return f"{index + 1}: {shown}"

    def refresh_swap_choices(self):
        if not self.slots or not hasattr(self, "swap_a_box"):
            return
        labels = [self.slot_choice_label(i) for i in range(len(self.slots))]
        self.swap_a_box["values"] = labels
        self.swap_b_box["values"] = labels
        self._keep_swap_selection(self.swap_a, labels)
        self._keep_swap_selection(self.swap_b, labels)

    def _keep_swap_selection(self, var, labels):
        current = var.get()
        slot_no = current.split(":", 1)[0] if current else ""
        for label in labels:
            if label.split(":", 1)[0] == slot_no:
                if var.get() != label:
                    var.set(label)
                return
        if labels and not current:
            return
        var.set("")

    def _swap_index(self, label):
        if not label or ":" not in label:
            return None
        slot_no = label.split(":", 1)[0]
        if not slot_no.isdigit():
            return None
        index = int(slot_no) - 1
        if not (0 <= index < len(self.slots)):
            return None
        return index

    def swap_selected_slots(self):
        a = self._swap_index(self.swap_a.get())
        b = self._swap_index(self.swap_b.get())
        if a is None or b is None:
            self.log("Select two slots to swap")
            return
        if a == b:
            self.log("Pick two different slots")
            return
        names = [slot['namevar'].get() for slot in self.slots]
        names[a], names[b] = names[b], names[a]
        self.new_slot_order(names)
        self.log(f"Swapped slot {a + 1} and slot {b + 1}")

    def update_shift(self, slot, playername):
        if not self.ws:
            return
        entrant = next((e for e in self.lastrt or [] if self.entrant_user(e).get('name', '').lower() == playername.lower()), None)
        if entrant:
            self.update_obs(slot, entrant)
        else:
            self.update_obs_name(slot, playername)

    def set_profile_controls_state(self, enabled):
        state = "normal" if enabled else "disabled"
        for rb in self.profile_radios:
            rb.config(state=state)

    def toggle_monitoring(self):
        if not self.is_monitoring:
            try:
                self.ws = obsws(obshost, obsport, self.pwvar.get())
                self.ws.register(self.on_obs_mute_changed, obs_events.InputMuteStateChanged)
                self.ws.connect()
                self.log("OBS connected")
                self.save_config()
                self.cache_scene_items()
                self.startup_obs_check()
                if self.profile["visibility"] == "folder":
                    self.manage_folder_visibility(initialize=True)
                else:
                    self.update_slot_visibility()
                self.is_monitoring = True
                self.btn_connect.config(text="Stop")
                self.set_profile_controls_state(False)
                threading.Thread(target=self.monitor_loop, daemon=True).start()
                self.root.after(1000, self.smooth_timer_loop)
            except Exception as e:
                messagebox.showerror("Connection Error", f"{e}")
        else:
            self.is_monitoring = False
            if self.ws:
                self.ws.disconnect()
            self.btn_connect.config(text="Start")
            self.set_profile_controls_state(True)
            self.log("Stopped")

    def toggle_auto_remove(self):
        new_val = not self.auto_remove_finished.get()
        self.auto_remove_finished.set(new_val)
        self.update_button_text()
        self.log(f"Auto Remove: {'Enabled' if new_val else 'Disabled'}")
        self.save_config()

    def remove_finished_players(self, entrants):
        if not self.auto_remove_finished.get():
            return

        for e in entrants or []:
            status = (e.get('status') or {}).get('value')
            if status in ['done', 'dnf']:
                pname = self.entrant_user(e).get('name')
                if not pname:
                    continue
                for slot in self.slots:
                    if slot['namevar'].get().lower() == pname.lower():
                        if slot['finishtime'] is None:
                            slot['finishtime'] = time.time()
                            self.log(f"Countdown started for {pname}")
                        break

    def monitor_loop(self):
        while self.is_monitoring:
            url = self.urlvar.get().strip()
            if not url:
                time.sleep(1)
                continue

            if not url.endswith("/data"):
                url += "/data"
            if self.active_race_url and self.active_race_url != url:
                self.active_race_url = url
                self.reset_for_new_race()
            elif not self.active_race_url:
                self.active_race_url = url
            try:
                r = requests.get(url, timeout=4)
                if r.status_code != 200:
                    self.log(f"Racetime returned {r.status_code}")
                    time.sleep(5)
                    continue

                data = r.json()
                entrants = data.get('entrants') or []
                self.lastrt = entrants

                self.remove_finished_players(entrants)

                nameslower = {s['namevar'].get().lower() for s in self.slots if s['namevar'].get()}
                blacklisted = set(self.blacklist.keys())

                for entrant in entrants:
                    pname = self.entrant_user(entrant).get('name')
                    if not pname:
                        continue
                    if pname.lower() not in nameslower and pname.lower() not in blacklisted:
                        for slot in self.slots:
                            if not slot['namevar'].get():
                                slot['namevar'].set(pname)
                                self.update_obs(slot, entrant)
                                nameslower.add(pname.lower())
                                break

                for slot in self.slots:
                    self.refresh_slot_status(slot)

                self.auto_adjust_layouts()
                self.update_slot_visibility()
                self.root.after(0, self.refresh_swap_choices)

                self.log(f"Synced at {time.strftime('%H:%M:%S')}")

            except Exception as e:
                self.log(f"Sync failed. {e}")

            time.sleep(5)

    def update_slot_visibility(self, slot_index=None, initialize=False):
        if not self.ws:
            return
        if self.profile["visibility"] == "folder":
            self.manage_folder_visibility(initialize=initialize, slot_index=slot_index)
        else:
            self.manage_visibility(slot_index=slot_index)

    def manage_visibility(self, slot_index=None):
        if not self.ws:
            return

        target_slots = [self.slots[slot_index]] if slot_index is not None else self.slots

        for slot in target_slots:
            scene_name = slot['scene']
            is_active = bool(slot['namevar'].get().strip())

            try:
                resp = self.ws.call(obs_requests.GetSceneItemList(sceneName=scene_name))
                items = resp.getSceneItems()

                source_keys = ['textsource']
                if slot.get('browsersource'):
                    source_keys.insert(0, 'browsersource')
                for key in source_keys:
                    target_source_name = slot[key]
                    if not target_source_name:
                        continue

                    iid = next((item['sceneItemId'] for item in items
                               if item['sourceName'] == target_source_name), None)

                    if iid is not None:
                        self.ws.call(obs_requests.SetSceneItemEnabled(
                            sceneName=scene_name,
                            sceneItemId=iid,
                            sceneItemEnabled=is_active
                        ))
            except Exception as e:
                print(f"Error toggling {slot['textsource']} in {scene_name}: {e}")

    def manage_folder_visibility(self, initialize=False, slot_index=None):
        if not self.ws:
            return

        slotstocheck = [self.slots[slot_index]] if slot_index is not None else self.slots

        for slot in slotstocheck:
            isassigned = bool(slot['namevar'].get())

            if initialize and isassigned:
                continue

            iid = self.get_item_id(slot['scene'], slot['foldersource'])
            if iid:
                self.ws.call(obs_requests.SetSceneItemEnabled(
                    sceneName=slot['scene'],
                    sceneItemId=iid,
                    sceneItemEnabled=isassigned
                ))

    def refresh_single_stream(self, index):
        if not self.ws:
            return

        slot = self.slots[index]
        source_name = slot['browsersource']

        try:
            resp = self.ws.call(obs_requests.GetInputSettings(inputName=source_name))
            current_settings = resp.getInputSettings()
            original_url = current_settings.get('url')

            if original_url:
                self.ws.call(obs_requests.SetInputSettings(
                    inputName=source_name,
                    inputSettings={'url': 'about:blank'}
                ))

                self.root.after(100, lambda: self.ws.call(obs_requests.SetInputSettings(
                    inputName=source_name,
                    inputSettings={'url': original_url}
                )))

                self.log(f"Refreshing: {slot['namevar'].get()}")
        except Exception as e:
            self.log(f"Could not refresh. {e}")

    def refresh_all_streams(self):
        if not self.ws:
            messagebox.showwarning("Connection Error", "Connect to OBS first.")
            return

        for i in range(len(self.slots)):
            if self.slots[i]['namevar'].get().strip():
                self.root.after(i * 150, lambda idx=i: self.refresh_single_stream(idx))

        self.log("Refreshing all streams.")

    def smooth_timer_loop(self):
        if not self.is_monitoring:
            return

        current_time = time.time()
        to_remove = []

        max_delay = self.get_remove_delay()

        for i, slot in enumerate(self.slots):
            pname = slot['namevar'].get().strip()
            if not pname or slot['finishtime'] is None:
                continue

            elapsed = current_time - slot['finishtime']
            remaining = max(0, max_delay - int(elapsed))

            current_text = slot['statuslbl'].cget("text")
            if "(" in current_text:
                base_text = current_text.split(" (")[0]
                slot['statuslbl'].config(text=f"{base_text} ({remaining}s)")
            elif "Finished" in current_text or "DNF" in current_text:
                slot['statuslbl'].config(text=f"{current_text} ({remaining}s)")

            if remaining <= 0:
                to_remove.append(i)

        if to_remove:
            remover = self.remove_player
            for index in sorted(to_remove, reverse=True):
                remover(index)
            self.auto_adjust_layouts()
            self.update_slot_visibility()

        self.root.after(1000, self.smooth_timer_loop)

if __name__ == "__main__":
    run_move_checks()
    print("move checks ok")
    root = tk.Tk()
    app = RacetimeAutomation(root)
    root.mainloop()
