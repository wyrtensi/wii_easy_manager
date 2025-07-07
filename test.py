import os
import time
import shutil
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm

# === Настройки ===
GAME_URL = "https://vimm.net/vault/63642"
CANCEL_URL = "https://dl3.vimm.net/download/cancel.php"
DOWNLOAD_DIR = os.path.abspath("downloads")

# === Настройка Chrome ===
chrome_options = Options()
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
})
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

# === Подготовка ===
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
for f in os.listdir(DOWNLOAD_DIR):
    os.remove(os.path.join(DOWNLOAD_DIR, f))

driver = webdriver.Chrome(options=chrome_options)

def try_start_download():
    driver.get(GAME_URL)
    time.sleep(2)
    try:
        button = driver.find_element(By.XPATH, "//form[@id='dl_form']/button")
        button.click()
    except Exception:
        return False

    # Ждём начала загрузки до 10 секунд
    for _ in range(10):
        files = os.listdir(DOWNLOAD_DIR)
        if any(f.endswith(".crdownload") for f in files):
            return True
        time.sleep(1)
    return False

# === Цикл до успешной загрузки ===
print("🔁 Попытка начать загрузку...")
while not try_start_download():
    print("⚠️ Не удалось — сбрасываем и пробуем снова...")
    driver.get(CANCEL_URL)
    time.sleep(1)

# === Загрузка началась ===
filename = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith(".crdownload")][0]
filepath = os.path.join(DOWNLOAD_DIR, filename)
print(f"⬇️ Загрузка началась: {filename}")

# === Индикатор загрузки ===
def show_progress(filepath):
    last_size = 0
    pbar = tqdm(total=100, desc="Загрузка", unit="%")
    while os.path.exists(filepath):
        size = os.path.getsize(filepath)
        if size > last_size:
            diff = size - last_size
            pbar.update((diff / 1024 / 1024) * 100 / 4000)  # Примерно на 4 ГБ
            last_size = size
        time.sleep(1)
    pbar.close()

progress_thread = threading.Thread(target=show_progress, args=(filepath,))
progress_thread.start()

# Ждём, пока исчезнет .crdownload
final_name = ""
while True:
    files = os.listdir(DOWNLOAD_DIR)
    ready = [f for f in files if not f.endswith(".crdownload")]
    if ready:
        final_name = ready[0]
        break
    time.sleep(1)

driver.quit()
progress_thread.join()
print(f"\n✅ Скачано: {final_name}")
