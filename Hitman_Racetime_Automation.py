import tkinter as tk
from tkinter import ttk, messagebox
import requests
import threading
import time
import re
from obswebsocket import obsws, requests as obs_requests
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
version = "4"
version_url = "https://raw.githubusercontent.com/Rekt05/hitman-racetime-automation/refs/heads/main/current_version.txt"
releases_url = "https://github.com/Rekt05/hitman-racetime-automation/releases/latest"

#config
obshost = "localhost"
obsport = 4455
filtername = "Toggle_Hook" #filter added to image sources in obs (1st-8th and dnf images)

#scene and source info
scene14 = "Streams 1-4"
scene58 = "Streams 5-8"
#image names
images = { 
    1: "1st.png", 2: "2nd.png", 3: "3rd.png", 4: "4th.png",
    5: "5th.png", 6: "6th.png", 7: "7th.png", 8: "8th.png",
    99: "dnf.png"
}

twitchlink = "https://player.twitch.tv/?channel={}&enableExtensions=true&muted=false&parent=twitch.tv&player=popout&quality=720p60&volume=0.7699999809265137"
twitchregex = re.compile(r'(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)')

class RacetimeAutomation:
    def __init__(self, root):
        self.root = root
        self.root.title("Hitman Racetime Automation")
        self.root.geometry("800x500") 
        
        self.ws = None
        self.is_monitoring = False
        self.slots = []
        self.scenemap = {} 
        self.blacklist = {} 
        self.lastrt = [] 

        #gui vars
        self.resultstoggle = tk.BooleanVar(value=False)
        self.urlvar = tk.StringVar()
        
        #password
        self.config = configparser.ConfigParser()
        config_file = get_external_path("config.ini")
        if os.path.exists(config_file):
            self.config.read(config_file)
            
        savedpw = self.config.get("Settings", "OBSPW", fallback = "")
        self.pwvar = tk.StringVar(value=savedpw)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close) 

        style = ttk.Style()
        style.configure("Racing.TLabel", foreground="green")
        style.configure("Done.TLabel", foreground="blue", font=('Helvetica', 9, 'bold'))
        style.configure("DNF.TLabel", foreground="red", font=('Helvetica', 9, 'bold'))
        style.configure("Small.TButton", font=('Helvetica', 7))

        #obs connection section
        obssection = ttk.LabelFrame(root, text="OBS Connection", padding=10)
        obssection.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(obssection, text="OBS Password:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Entry(obssection, textvariable=self.pwvar, width=30, show="*").grid(row=0, column=1, padx=5, sticky="ew")

        self.btn_connect = ttk.Button(obssection, text="Start", command=self.toggle_monitoring)
        self.btn_connect.grid(row=0, column=2, padx=5)
        
        #race config section
        racesection = ttk.LabelFrame(root, text="Race Configuration", padding=10)
        racesection.pack(fill="x", padx=10, pady=5)

        ttk.Label(racesection, text="Racetime URL:").grid(row=0, column=0, sticky="w")
        ttk.Entry(racesection, textvariable=self.urlvar, width=40).grid(row=0, column=1, padx=5, sticky="ew")

        ttk.Button(racesection, text="Find Current Race", command=self.get_current).grid(row=0, column=2, padx=5)
        
        ttk.Checkbutton(racesection, text="Show Placement Images", 
                        variable=self.resultstoggle, 
                        command=self.manual_results_toggle).grid(row=1, column=0, sticky="w", pady=5)

        #player section
        playersection = ttk.Frame(root)
        playersection.pack(fill="both", expand=True, padx=10, pady=5)

        #player slots
        slots_frame = ttk.LabelFrame(playersection, text="Player Slots", padding=10)
        slots_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        for i in range(1, 9):
            self.create_slot(slots_frame, i)

        #removed players blacklist
        self.blacklistsection = ttk.LabelFrame(playersection, text="Removed Players", padding=10)
        self.blacklistsection.pack(side="right", fill="y", padx=(5, 0))
        
        self.blacklist_container = ttk.Frame(self.blacklistsection)
        self.blacklist_container.pack(fill="both", expand=True)

        self.update_blacklist() 

        self.status_var = tk.StringVar(value="Enter an OBS password and click start")
        self.status_label = ttk.Label(root, textvariable=self.status_var, relief="sunken", style="TLabel")
        self.status_label.pack(side="bottom", fill="x")

        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def check_for_updates(self):
        ignored = self.config.get("Settings", "IgnoreVersion", fallback="")
        try:
            r = requests.get(version_url, timeout=5)
            if r.status_code == 200:
                latest = r.text.strip()
                if latest != version and latest != ignored:
                    self.root.after(0, lambda: self.show_update_dialog(latest))
        except:
            pass

    def show_update_dialog(self, latest_version):
        update_win = tk.Toplevel(self.root)
        update_win.title("Available Update")
        update_win.geometry("350x120")
        update_win.resizable(False, False)
        update_win.attributes("-topmost", True)
        
        ttk.Label(update_win, text=f"A new update (v{latest_version}) is now available for download", padding=10).pack()
        
        btn_frame = ttk.Frame(update_win)
        btn_frame.pack(pady=10)

        def open_link():
            import webbrowser
            webbrowser.open(releases_url)
            update_win.destroy()

        def ignore_perm():
            if 'Settings' not in self.config: self.config['Settings'] = {}
            self.config['Settings']['IgnoreVersion'] = latest_version
            self.save_config()
            update_win.destroy()

        ttk.Button(btn_frame, text="Go to Page", command=open_link).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Ignore Once", command=update_win.destroy).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Ignore Permanently", command=ignore_perm).grid(row=0, column=2, padx=5)

    def get_current(self):
        try:
            r = requests.get("https://racetime.gg/hitman-3/data", timeout=5) #change "hitman-3" to whatever game if needed
            if r.status_code == 200:
                data = r.json()
                active = data.get('current_races', [])
                openr = [race for race in active if race.get('status', {}).get('value') == 'open']
                
                #this gets the first open/active race, not a problem with the frequency of hitman races being only 1 every week, but should ideally be handled by user choice
                if openr:
                    target = openr[0].get('data_url')
                    name = openr[0].get('url')
                    roomurl = f"https://racetime.gg{target}"
                    self.urlvar.set(roomurl)
                    self.log(f"Race {name} was found.")
                elif active:
                    target = active[0].get('data_url')
                    name = active[0].get('url')
                    roomurl = f"https://racetime.gg{target}"
                    self.urlvar.set(roomurl)
                    self.log(f"No open races, active race {name} used instead.")
                else:
                    self.log("No active hitman-3 races found.")
            else:
                self.log("Racetime.gg did not respond.")
        except Exception as e:
            self.log(e)

    def save_config(self):
        if 'Settings' not in self.config:
            self.config['Settings'] = {}
        self.config['Settings']['OBSPW'] = self.pwvar.get()
        with open(get_external_path("config.ini"), 'w') as cfgfile:
            self.config.write(cfgfile)

    def on_close(self):
        self.save_config()
        self.is_monitoring = False
        
        if self.ws:
            self.reset_images() 
        
        self.root.destroy()
        
    def reset_images(self):
        if not self.ws: return
        self.ws.disconnect()
        self.log("OBS disconnected")

    def log(self, msg, iserror=False):
        self.status_var.set(msg)
        self.status_label.config(style="TLabel")
        print(msg)

    def get_name(self, streamlink):
        if not '/' in streamlink and not '.' in streamlink:
            return streamlink
        match = twitchregex.search(streamlink)
        return match.group(1) if match else ""
    
    def update_obs(self, slot, entrant):
        self.ws.call(obs_requests.SetInputSettings(inputName=slot['textsource'], inputSettings={"text": entrant['user']['name']}))
        
        if 'twitch_channel' in entrant['user']:
            channel_name = self.get_name(entrant['user']['twitch_channel']) 
            if channel_name:
                new_url = twitchlink.format(channel_name)
                self.ws.call(obs_requests.SetInputSettings(inputName=slot['browsersource'], inputSettings={"url": new_url}))

    def update_obs_name(self, slot, newname):
        if self.ws:
            self.ws.call(obs_requests.SetInputSettings(
                inputName = slot['textsource'], 
                inputSettings = {"text": newname}
            ))
            self.update_obs_images(slot, None, None) 
    
    #gui setup
    def create_slot(self, parent, i):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)
        
        slot_data = {
            "index": i,
            "namevar": tk.StringVar(),
            "statuslbl": ttk.Label(frame, text="Empty", width=15),
            "laststatus": None,
            "scene": scene14 if 1 <= i <= 4 else scene58,
            "suffix": "" if i == 1 else f" ({i})", 
            "streamnumber": i, 
            "foldersource": f"Stream #{i}",
            "textsource": f"Streamer Name {i}",
            "browsersource": f"Stream {i}"
        }

        #buttons
        upbtn = ttk.Button(frame, text="▲", width=2, style="Small.TButton", command=lambda idx=i-1: self.shift_player(idx, "up"))
        upbtn.pack(side="left")
        downbtn = ttk.Button(frame, text="▼", width=2, style="Small.TButton", command=lambda idx=i-1: self.shift_player(idx, "down"))
        downbtn.pack(side="left")
        trashbtn = ttk.Button(frame, text="🗑️", width=2, style="Trash.TButton", command=lambda idx=i-1: self.remove_player(idx))
        trashbtn.pack(side="left", padx=(5, 5)) 

        ttk.Label(frame, text=f"Slot {i}:", width=12).pack(side="left", padx=(5, 0))
        ttk.Entry(frame, textvariable=slot_data['namevar'], width=15).pack(side="left", padx=5)
        slot_data['statuslbl'].pack(side="left", padx=5)
        
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
            
            ttk.Label(player_section, text=original_name, width=20, anchor="w").pack(side="left", padx=5)

    def remove_player(self, index_to_remove):
        playername = self.slots[index_to_remove]['namevar'].get()
        if not playername: return

        lowername = playername.lower()
        if lowername not in self.blacklist:
            self.blacklist[lowername] = playername
            self.update_blacklist()
        
        currentnames = [slot['namevar'].get() for slot in self.slots]
        nameshift = [name for i, name in enumerate(currentnames) if i > index_to_remove and name]
        newnames = currentnames[:index_to_remove] + nameshift + [""]
        
        self.new_slot_order(newnames)
        self.log(f"'{playername}' removed")

    def readd_player(self, playername):
        emptyslots = next((i for i, slot in enumerate(self.slots) if not slot['namevar'].get()), None)
        
        if emptyslots is None:
            self.log("slots full")
            return

        self.slots[emptyslots]['namevar'].set(playername)
        
        self.update_shift(self.slots[emptyslots], playername)

        self.manage_folder_visibility(slot_index=emptyslots) 

        del self.blacklist[playername.lower()]
        self.update_blacklist()
        self.log(f"'{playername}' added to Slot {emptyslots + 1}")

    def shift_player(self, index, direction):
        if not self.slots[index]['namevar'].get(): return 

        targets = index + (1 if direction == "down" else -1)
        if not (0 <= targets < len(self.slots)): return

        currentnames = [slot['namevar'].get() for slot in self.slots]
        currentnames[index], currentnames[targets] = currentnames[targets], currentnames[index]
        
        self.new_slot_order(currentnames)
        self.log(f"Shifted from slot {index + 1} to {targets + 1}")

    def new_slot_order(self, newnames):
        for i, newname in enumerate(newnames):
            oldname = self.slots[i]['namevar'].get()
            
            if oldname != newname:
                self.slots[i]['namevar'].set(newname)
                
                if newname:
                    self.update_shift(self.slots[i], newname)
                else:
                    self.update_obs_name(self.slots[i], "")

                self.manage_folder_visibility(slot_index=i) 
    
    def update_shift(self, slot, playername):
        if not self.ws: return
        
        entrant = next((e for e in self.lastrt if e['user']['name'].lower() == playername.lower()), None)
        
        if entrant:
            self.update_obs(slot, entrant)
            self.log(f"Stream data updated for '{playername}'")
        else:
            self.update_obs_name(slot, playername)

    def toggle_monitoring(self):
        if not self.is_monitoring:
            obspassword = self.pwvar.get()
            try:
                self.ws = obsws(obshost, obsport, obspassword)
                self.ws.connect()
                self.log("OBS connected")
                
                self.cache_scene_items() 
                self.manage_folder_visibility(initialize=True) 
                
                self.is_monitoring = True
                self.btn_connect.config(text="Stop")
                threading.Thread(target=self.monitor_loop).start() 
            except ConnectionRefusedError:
                messagebox.showerror("Connection Error", "Could not connect to OBS, make sure that the password is correct and obs is open")
                self.ws = None
            except Exception as e:
                messagebox.showerror("Connection Error", f"{e}")
                self.ws = None
        else:
            self.is_monitoring = False
            if self.ws:
                self.reset_images() 
            self.btn_connect.config(text="Start")
            self.log("Stopped")

    def monitor_loop(self):
        while self.is_monitoring:
            url = self.urlvar.get().strip()
            if not url:
                time.sleep(1)
                continue
            
            if not url.startswith("https://"): url = "https://" + url
            if not url.endswith("/data"): url += "/data"
            try:
                data = requests.get(url, timeout=4).json()
            except Exception as e:
                self.log(f"Error fetching racetime: {e}", iserror=True)
                time.sleep(5)
                continue

            entrants = data.get('entrants', [])
            self.lastrt = entrants
            
            if not self.is_monitoring:
                break 

            nameslower = {s['namevar'].get().lower() for s in self.slots if s['namevar'].get()}
            blacklistednameslower = set(self.blacklist.keys())
            
            for entrant in entrants:
                pname = entrant['user']['name']
                pnamelower = pname.lower()
                    
                if pnamelower not in nameslower and pnamelower not in blacklistednameslower:
                    for slot in self.slots:
                        if not slot['namevar'].get():
                            slot['namevar'].set(pname)
                            self.update_obs(slot, entrant)
                            self.manage_folder_visibility()
                            nameslower.add(pnamelower) 
                            break
            
            self.manage_folder_visibility() 

            for slot in self.slots:
                playername = slot['namevar'].get()
                if not playername:
                    slot['statuslbl'].config(text="Empty", style="TLabel")
                    self.update_obs_images(slot, None, None) 
                    continue

                entrant = next((e for e in entrants if e['user']['name'].lower() == playername.lower()), None)
                
                if entrant:
                    status = entrant['status']['value']
                    place = entrant.get('place')
                    
                    if status == "done":
                        txt = f"Finished: {place}"
                        slot['statuslbl'].config(text=txt, style="Done.TLabel")
                    elif status == "dnf":
                        slot['statuslbl'].config(text="DNF", style="DNF.TLabel")
                    else:
                        slot['statuslbl'].config(text="Racing", style="Racing.TLabel")
                    
                    self.update_obs_images(slot, status, place)
                else:
                    slot['statuslbl'].config(text="Not Found", style="TLabel")
                    self.update_obs_images(slot, None, None)

            self.log(f"Synced at {time.strftime('%H:%M:%S')}")
            time.sleep(5)

    def cache_scene_items(self):
        self.scenemap = {}
        allscenes = [scene14, scene58]
        
        for scene in allscenes:
            self.scenemap[scene] = {}
            sceneitems = self.ws.call(obs_requests.GetSceneItemList(sceneName=scene)).getSceneItems()
            
            for item in sceneitems:
                sourcename = item.get('sourceName')
                itemid = item.get('sceneItemId')
                
                if sourcename and itemid:
                    self.scenemap[scene][sourcename] = itemid

    def get_item_id(self, scene, sourcename):
        return self.scenemap.get(scene, {}).get(sourcename)

    def manage_folder_visibility(self, initialize=False, slot_index=None):
        if not self.ws: return
        
        slotstocheck = [self.slots[slot_index]] if slot_index is not None else self.slots
        
        for slot in slotstocheck:
            isassigned = bool(slot['namevar'].get())
            
            if initialize and isassigned:
                continue
            
            iid = self.get_item_id(slot['scene'], slot['foldersource'])
            if iid:
                self.ws.call(obs_requests.SetSceneItemEnabled(
                    sceneName = slot['scene'], 
                    sceneItemId = iid, 
                    sceneItemEnabled = isassigned
                ))

    def manual_results_toggle(self):
        if self.is_monitoring:
            self.log(f"Results {'visible' if self.resultstoggle.get() else 'hidden'}")
            threading.Thread(target=self.run_single_update).start()
        
    def run_single_update(self):
        url = self.urlvar.get().strip()
        if not url: return
        
        if not url.endswith("/data"): url += "/data"
        
        try:
            data = requests.get(url).json()
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching racetime data for manual update: {e}", iserror=True)
            return

        entrants = data.get('entrants', [])
        
        for slot in self.slots:
            playername = slot['namevar'].get()
            if not playername: continue
            
            entrant = next((e for e in entrants if e['user']['name'].lower() == playername.lower()), None)
            
            if entrant:
                status = entrant['status']['value']
                place = entrant.get('place')
                self.update_obs_images(slot, status, place)

    def get_full_source_name(self, basename, suffix):
        if suffix: 
             return f"{basename}{suffix}"
        return basename

    def update_obs_images(self, slot, status, place):
        showresults = self.resultstoggle.get()
        targetimg = None
        
        if status == 'done' and place is not None:
            placeint = int(place) 
            
            if 1 <= placeint <= 8:
                base = images.get(placeint)
                if base: targetimg = self.get_full_source_name(base, slot['suffix'])
                
        elif status == 'dnf':
            base = images.get(99)
            if base: targetimg = self.get_full_source_name(base, slot['suffix'])
        
        def set_visible_via_filter(sourcename, visible):
            filterenabled = not visible 

            self.ws.call(obs_requests.SetSourceFilterEnabled(
                sourceName = sourcename, 
                filterName = filtername, 
                filterEnabled = filterenabled
            ))

        is_finished = status in ['done', 'dnf']
        
        for rnum, rbase in images.items():
            rfull = self.get_full_source_name(rbase, slot['suffix'])
            
            sbv = is_finished and showresults and (rfull == targetimg)
            
            set_visible_via_filter(rfull, sbv) 

if __name__ == "__main__":
    root = tk.Tk()
    app = RacetimeAutomation(root)
    root.mainloop()