import json
import os
import subprocess
import time
import urllib.request
import sys
import threading
import zipfile

VIDEO_URL = "https://github.com/OpexDevelop/EpicGandalfSax/raw/refs/heads/main/EpicSaxGandalf.mp4"
VIDEO_DURATION_SEC = 117.59
LOOP_COUNT = 5

LOCAL_VIDEO_PATH = os.path.join(os.getenv("TEMP", "C:\\temp"), "EpicSaxGandalf.mp4")

# MPV installation and path
MPV_DIR = os.path.join(os.getenv("TEMP", "C:\\temp"), "mpv-x86_64")
MPV_PATH = os.path.join(MPV_DIR, "mpv.exe")

# Если mpv нет — VLC, потом WMP
VLC_PATHS = [
    "vlc",
    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
]
WMP_PATH = r"C:\Program Files\Windows Media Player\wmplayer.exe"

def kill_process_tree(pid):
    subprocess.call(['taskkill', '/F', '/PID', str(pid), '/T'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_utc_offset():
    try:
        with urllib.request.urlopen("http://worldtimeapi.org/api/timezone/Etc/UTC", timeout=4) as resp:
            data = json.loads(resp.read().decode())
            return float(data["unixtime"]) - time.time()
    except:
        return 0

def download_video():
    if os.path.exists(LOCAL_VIDEO_PATH):
        return
    try:
        print("Скачиваем видео...")
        urllib.request.urlretrieve(VIDEO_URL, LOCAL_VIDEO_PATH)
    except:
        sys.exit(1)

def install_mpv():
    if os.path.exists(MPV_PATH):
        return True
    try:
        os.makedirs(MPV_DIR, exist_ok=True)
        zip_url = "https://nightly.link/mpv-player/mpv/workflows/build/master/mpv-x86_64-w64-mingw32.zip"
        zip_path = os.path.join(os.getenv("TEMP", "C:\\temp"), "mpv.zip")
        print("Скачиваем mpv...")
        urllib.request.urlretrieve(zip_url, zip_path)
        print("Распаковываем mpv...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(MPV_DIR)
        os.remove(zip_path)
        if not os.path.exists(MPV_PATH):
            for root, dirs, files in os.walk(MPV_DIR):
                if "mpv.exe" in files:
                    new_mpv_path = os.path.join(root, "mpv.exe")
                    print(f"Найден mpv.exe в {new_mpv_path}")
                    global MPV_PATH
                    MPV_PATH = new_mpv_path
                    return True
            raise Exception("mpv.exe не найден после распаковки")
        return True
    except Exception as e:
        print(f"Ошибка установки mpv: {e}")
        return False

def find_best_player():
    if install_mpv():
        return MPV_PATH, "mpv"
    for path in VLC_PATHS:
        if os.path.exists(path) or subprocess.run([path, "--version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True).returncode == 0:
            return path, "vlc"
    return WMP_PATH, "wmp"

def launch_mpv():
    return subprocess.Popen([
        MPV_PATH,
        LOCAL_VIDEO_PATH,
        "--fs", "--loop=no", "--really-quiet",
        f"--length={VIDEO_DURATION_SEC}",
        "--input-ipc-server=\\\\.\\pipe\\mpv-gandalf"
    ], creationflags=subprocess.CREATE_NO_WINDOW)

def launch_vlc():
    return subprocess.Popen([
        player_path,
        LOCAL_VIDEO_PATH,
        "--fullscreen", "--play-and-exit", "--no-video-title-show", "--quiet"
    ])

def launch_wmp():
    return subprocess.Popen([
        player_path, "/play", "/fullscreen", "/close", LOCAL_VIDEO_PATH
    ])

# =============== ОСНОВНОЙ ЦИКЛ ===============
download_video()
player_path, player_type = find_best_player()
offset = get_utc_offset()

print(f"Запускаем через {player_type.upper() if player_type != 'mpv' else 'MPV'}")

true_time = lambda: time.time() + offset
launched = 0
early_exit = False

def monitor_proc(proc, start_time, duration):
    global early_exit
    time.sleep(1)
    while proc.poll() is None:
        if time.time() - start_time > duration - 1:
            break
        time.sleep(0.5)
    if proc.poll() is not None and time.time() - start_time < duration - 1:
        print("Плеер закрыт вручную — завершаем скрипт")
        early_exit = True

for _ in range(LOOP_COUNT * 3):
    if early_exit:
        break

    now = true_time()
    to_next = VIDEO_DURATION_SEC - (now % VIDEO_DURATION_SEC)

    slept = 0
    while slept < to_next and not early_exit:
        chunk = min(0.2, to_next - slept)
        time.sleep(chunk)
        slept += chunk
        if int(time.time()) % 10 == 0:
            offset = get_utc_offset()

    if early_exit:
        break

    start_exact = true_time()

    if player_type == "mpv":
        subprocess.call(['taskkill', '/IM', 'mpv.exe', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    launch_func = {"mpv": launch_mpv, "vlc": launch_vlc, "wmp": launch_wmp}[player_type]
    proc = launch_func()

    launched += 1
    print(f"[{launched}] Запущено в {time.strftime('%H:%M:%S', time.gmtime(start_exact))} UTC "
          f"(отклонение {start_exact % VIDEO_DURATION_SEC:.3f}s)")

    threading.Thread(target=monitor_proc, args=(proc, time.time(), VIDEO_DURATION_SEC), daemon=True).start()

    def killer():
        time.sleep(VIDEO_DURATION_SEC + 0.5)
        kill_process_tree(proc.pid)
    threading.Thread(target=killer, daemon=True).start()

    time.sleep(1.5 if player_type == "wmp" else 0.8)

    if launched >= LOOP_COUNT:
        break

# Чистка
time.sleep(2)
for name in ["mpv.exe", "vlc.exe", "wmplayer.exe"]:
    subprocess.call(['taskkill', '/IM', name, '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

try:
    os.remove(LOCAL_VIDEO_PATH)
except:
    pass