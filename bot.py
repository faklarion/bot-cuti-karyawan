import os
import json
import requests
import re
import gspread
from flask import Flask, request
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import calendar

app = Flask(__name__)

# ============ KONFIGURASI ============
TOKEN = "8620563805:AAGQNY5h3rXTKj6DpI04vcXcHKC4axTwT0A"
SPREADSHEET_ID = "1eBI6Dor4DiNczYOrpXQDiN6sXaRyAZg_ahCVV_1d_HE"
DIALOGFLOW_PROJECT_ID = "newagent-enoo"

SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "newagent-enoo",
    "private_key_id": "b35527546aa124f6ed34b0b9c14f61e1a55362db",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDHSQYbXXTT13Ha\nls5oQh+fvHOGlH1OEVc7bkbEW3kRND2Q08kYwlgtimxmzPbl7nUrfgzNprHlk8XQ\n1yPRtcOrUiDj7W11G9C/G9SRgdChAO1DEVGZwtsGvmGW4CzylR4DecvgSvXFhwkJ\nY3MaziH8VBzCsnQalUnf3tJHwWnhH7WkKse8XwOwY6WHW3w2gCY3WDjqGkvuPtsZ\nQZQ6wiVDuHoJk6Vuel+hQ9qDVg9r7Ne07WqvLGoR5Zcz8cEZEklcV8r+moinIddi\nWgJvfDrGOfeUUHc+vo8Td2lktCInqaVl+mBzGr5mpHJshYBUKwHbqcZsWOA1lq3k\nW912n+GfAgMBAAECggEAByBJ2x2m6VJZbGcbH2hJ6DTdbrENoAaHt4TUe/4HYMGc\n9/pSxRNiAtLh2HU42PUDdJgvzgTJdLuphbPDwKJ+yjgIHA5n7RmfB85vdfqN4sv9\nL/pFEDoDCgUxySrgAJareZVX4H/dtQAEpzTKr2kylurNEns+Ips3Bo3ZuB4m8plW\n6u34JVPtpXT1MMa/RofRxXzHi4gRQAI+MU4bdLma/4vQiqlyyG7V6rKnFtnrgKIa\nBoR9v/uag/NkUqj6W7wf/SfBgRvMlxhtE/jZO+90zLKrEqC7jKFT8kMlY0j2j1xR\nVrttdvo09gBaXg80w4Ib2bwNayF0whGQ8lXOwlNPvQKBgQD9joiswvDPhxi/inbd\nM5LkvCoXTuOM54Qi3MKatI7InbX9i+PpcjJRKAVoutKLOorRcpvnzM4Kw5ulyryj\nZG19eVJCUimJAKZEoHzPaG+JJTRELGrhbcbOEjlYWYrvruh0cfka6OoJaHvXLNME\nH9JzdBHq7/oeNqPSADt7ubmn8wKBgQDJNJ1YY3AsQQpghxYZtdlJbAuNxdvwOtY5\nyaddRvHnXVUBmbUJ1Kts2hN7gUoSsEB4kF4LYV/K5k3Yf7t6JxKccl7Dn1qxOo2w\nGVE+FY63Zts7bgkRfTIGMo2vVmNGNV4zE+2WVPjylJmguGXDu27bN2AFFesWKUw2\n18E5lAlWpQKBgBaIVB0GNeA7YTekVmvR6XvqPNNVb2NWL6fpdmHJKecqHMIrbFWS\nkGYl6FUmRQ+aZDu4s6Il0SmjuHFDUwAyLIi5/1Vld8t1A1GV8YF9Bmxpofts9xKR\nbtlhRTdUvcQPBxlSB5Ecoa+0WU0F7rqvGUSpS+5U5SVKNcSzwJV+K8GBAoGAUywX\nutjoHrMIKhzNSvV8C7jJEeLvZt+7fInaUFmqV5yiLhYu2xB5iHahRRWN3CnVjMEI\nzyWCZqpLFaq/geAy9k7k03LFF6v/tALTLZnVtASlrWxv/TXGfv9YyFkqknQvK2ga\nd2FKw2QgGWsATiflzGKYo6GK209Y/Pa1HisOrS0CgYAqie0eosnV6z3YgVZMjh0V\n0N168U4x3lFyytutmwmXnBM6aoC7K/zGEGxKFmXr1eSaDOAytAnsJgpDU864ukLD\navXLXZRp1lCF7SzAUEgf4Fr1XeD8LlllDvk9zQMqbcO7KFx6XD8fKd2LSWUpyXX5\n1vNoiOGpQbaW/xvBX9tGGA==\n-----END PRIVATE KEY-----\n",
    "client_email": "bottelegram@newagent-enoo.iam.gserviceaccount.com",
    "client_id": "105834349553821759425",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
}

# Mapping bulan Indonesia
BULAN_MAP = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'agustus': 8, 'september': 9, 'oktober': 10, 'november': 11, 'desember': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'agu': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'des': 12
}

# ============ GOOGLE SHEETS ============
def get_sheet(sheet_name):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    return spreadsheet.worksheet(sheet_name)

def get_karyawan(chat_id):
    try:
        sheet = get_sheet("Karyawan")
        data = sheet.get_all_values()
        chat_id_str = str(chat_id)
        
        for i, row in enumerate(data[1:]):
            if len(row) >= 6 and str(row[5]).strip() == chat_id_str:
                return {
                    "nama": row[2],
                    "jabatan": row[3],
                    "divisi": row[4],
                    "sisa_cuti": int(row[8]) if row[8] and row[8].isdigit() else 12,
                    "atasan": row[9] if len(row) > 9 else "-"
                }
        return None
    except Exception as e:
        print(f"Error get_karyawan: {e}")
        return None

# ============ PARSING TANGGAL ============
def parse_tanggal_indonesia(text):
    """Mengekstrak tanggal dari teks bahasa Indonesia"""
    pattern = r'(\d{1,2})\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|jan|feb|mar|apr|jun|jul|agu|sep|okt|nov|des)\s+(\d{4})'
    matches = re.findall(pattern, text.lower())
    
    if matches:
        for match in matches:
            hari = int(match[0])
            bulan = BULAN_MAP.get(match[1])
            tahun = int(match[2])
            if 1 <= hari <= 31 and 1 <= bulan <= 12 and tahun > 2000:
                return f"{tahun}-{bulan:02d}-{hari:02d}"
    
    pattern2 = r'(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})'
    matches2 = re.findall(pattern2, text)
    
    if matches2:
        for match in matches2:
            hari = int(match[0])
            bulan = int(match[1])
            tahun = int(match[2])
            if 1 <= hari <= 31 and 1 <= bulan <= 12:
                return f"{tahun}-{bulan:02d}-{hari:02d}"
    
    pattern3 = r'(\d{4})-(\d{2})-(\d{2})'
    matches3 = re.findall(pattern3, text)
    
    if matches3:
        for match in matches3:
            tahun = int(match[0])
            bulan = int(match[1])
            hari = int(match[2])
            if 1 <= hari <= 31 and 1 <= bulan <= 12:
                return f"{tahun}-{bulan:02d}-{hari:02d}"
    
    return None

def extract_two_dates(text):
    """Ekstrak dua tanggal dari teks (mulai dan selesai)"""
    pattern = r'dari\s+(.+?)\s+sampai\s+(.+)'
    match = re.search(pattern, text.lower())
    
    if match:
        tgl1_str = match.group(1).strip()
        tgl2_str = match.group(2).strip()
        
        tgl1 = parse_tanggal_indonesia(tgl1_str)
        tgl2 = parse_tanggal_indonesia(tgl2_str)
        
        if tgl1 and tgl2:
            return tgl1, tgl2
    
    semua_tanggal = []
    for word in text.split():
        parsed = parse_tanggal_indonesia(word)
        if parsed:
            semua_tanggal.append(parsed)
    
    if not semua_tanggal:
        pattern_tanggal = r'(\d{1,2}\s+\w+\s+\d{4})'
        tanggals = re.findall(pattern_tanggal, text, re.IGNORECASE)
        for t in tanggals:
            parsed = parse_tanggal_indonesia(t)
            if parsed:
                semua_tanggal.append(parsed)
    
    if len(semua_tanggal) >= 2:
        return semua_tanggal[0], semua_tanggal[1]
    elif len(semua_tanggal) == 1:
        return semua_tanggal[0], semua_tanggal[0]
    
    return None, None

# ============ DIALOGFLOW ============
def detect_intent(chat_id, text):
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
        
        import google.auth.transport.requests
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        token = creds.token

        url = f"https://dialogflow.googleapis.com/v2/projects/{DIALOGFLOW_PROJECT_ID}/agent/sessions/{chat_id}:detectIntent"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "queryInput": {
                "text": {
                    "text": text,
                    "languageCode": "id"
                }
            }
        }
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()

        intent = result.get("queryResult", {}).get("intent", {}).get("displayName", "Default Fallback Intent")
        params = result.get("queryResult", {}).get("parameters", {})
        
        parsed_params = {}
        for key, value in params.items():
            if isinstance(value, dict):
                if "stringValue" in value:
                    parsed_params[key] = value["stringValue"]
                elif "numberValue" in value:
                    parsed_params[key] = value["numberValue"]
                else:
                    parsed_params[key] = value.get("value", value)
            else:
                parsed_params[key] = value
        
        fulfillment = result.get("queryResult", {}).get("fulfillmentText", "")
        return intent, parsed_params, fulfillment

    except Exception as e:
        print(f"Error detect_intent: {e}")
        return "Default Fallback Intent", {}, "Maaf, terjadi kesalahan."

# ============ TELEGRAM ============
def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat_id, 
            "text": text,
            "parse_mode": "Markdown"
        })
    except Exception as e:
        print(f"Error send_telegram: {e}")

# ============ PROSES CUTI DENGAN VALIDASI ============
def proses_ajukan_cuti(chat_id, karyawan, mulai, selesai):
    try:
        if not mulai or not selesai:
            return ("❌ Mohon berikan tanggal mulai dan selesai cuti.\n\n"
                    "Contoh: *saya mau cuti dari 1 Desember 2026 sampai 5 Desember 2026*")

        # DEBUG: Cetak nilai asli
        print(f"DEBUG: Raw mulai = {mulai}, type = {type(mulai)}")
        print(f"DEBUG: Raw selesai = {selesai}, type = {type(selesai)}")

        # Pastikan format tanggal benar
        if isinstance(mulai, dict):
            # Coba ambil dari berbagai kemungkinan key
            mulai = mulai.get("startDate") or mulai.get("stringValue") or mulai.get("date") or str(mulai)
        if isinstance(selesai, dict):
            selesai = selesai.get("endDate") or selesai.get("stringValue") or selesai.get("date") or str(selesai)
        
        # Konversi ke string
        mulai_str = str(mulai)
        selesai_str = str(selesai)
        
        print(f"DEBUG: After dict check - mulai_str = {mulai_str}")
        print(f"DEBUG: After dict check - selesai_str = {selesai_str}")
        
        # Ekstrak tahun dari string menggunakan regex
        import re
        
        # Cari tahun 4 digit (2024, 2025, 2026, dll)
        tahun_mulai_match = re.search(r'(202\d|203\d)', mulai_str)
        tahun_selesai_match = re.search(r'(202\d|203\d)', selesai_str)
        
        if tahun_mulai_match:
            tahun_mulai = tahun_mulai_match.group(1)
            print(f"DEBUG: Found tahun mulai = {tahun_mulai}")
        else:
            tahun_mulai = None
            
        if tahun_selesai_match:
            tahun_selesai = tahun_selesai_match.group(1)
            print(f"DEBUG: Found tahun selesai = {tahun_selesai}")
        else:
            tahun_selesai = None
        
        # Bersihkan string tanggal (hapus teks yang tidak perlu)
        # Format dari Dialogflow biasanya: "2026-12-01T00:00:00+07:00" atau "2026-12-01"
        if 'T' in mulai_str:
            mulai_str = mulai_str.split('T')[0]
        if 'T' in selesai_str:
            selesai_str = selesai_str.split('T')[0]
        
        # Jika mulai_str masih panjang, ekstrak YYYY-MM-DD
        match_mulai = re.search(r'(\d{4})-(\d{2})-(\d{2})', mulai_str)
        match_selesai = re.search(r'(\d{4})-(\d{2})-(\d{2})', selesai_str)
        
        if match_mulai:
            tahun = int(match_mulai.group(1))
            bulan = int(match_mulai.group(2))
            hari = int(match_mulai.group(3))
            tgl_mulai = datetime(tahun, bulan, hari)
            print(f"DEBUG: Parsed mulai = {tgl_mulai}")
        else:
            # Fallback ke parsing biasa
            tgl_mulai = datetime.strptime(mulai_str[:10], "%Y-%m-%d")
            
        if match_selesai:
            tahun = int(match_selesai.group(1))
            bulan = int(match_selesai.group(2))
            hari = int(match_selesai.group(3))
            tgl_selesai = datetime(tahun, bulan, hari)
            print(f"DEBUG: Parsed selesai = {tgl_selesai}")
        else:
            tgl_selesai = datetime.strptime(selesai_str[:10], "%Y-%m-%d")
        
        # Jika tahun masih 2024 tapi user minta 2026, gunakan tahun dari text asli
        # (Ini untuk handle kasus Dialogflow kasih default 2024)
        if tahun_mulai and tgl_mulai.year == 2024 and tahun_mulai != '2024':
            tgl_mulai = tgl_mulai.replace(year=int(tahun_mulai))
            print(f"DEBUG: Corrected tahun mulai to {tahun_mulai}")
        
        if tahun_selesai and tgl_selesai.year == 2024 and tahun_selesai != '2024':
            tgl_selesai = tgl_selesai.replace(year=int(tahun_selesai))
            print(f"DEBUG: Corrected tahun selesai to {tahun_selesai}")

        print(f"DEBUG: Final tgl_mulai = {tgl_mulai}")
        print(f"DEBUG: Final tgl_selesai = {tgl_selesai}")

        # ============ VALIDASI TANGGAL ============
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tgl_mulai_tanpa_waktu = tgl_mulai.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Validasi 1: Tanggal tidak boleh lewat
        if tgl_mulai_tanpa_waktu < today:
            return f"❌ Tanggal mulai cuti *{tgl_mulai.strftime('%d %B %Y')}* sudah lewat.\n\n📌 Cuti harus diajukan minimal H-1 (satu hari sebelum tanggal cuti)."
        
        # Validasi 2: Tanggal tidak boleh hari ini
        if tgl_mulai_tanpa_waktu == today:
            return f"❌ Tanggal mulai cuti *{tgl_mulai.strftime('%d %B %Y')}* adalah hari ini.\n\n📌 Pengajuan cuti harus dilakukan *minimal 1 hari sebelum* tanggal cuti dimulai."
        
        # Validasi 3: Tanggal selesai harus setelah tanggal mulai
        if tgl_selesai < tgl_mulai:
            return "❌ Tanggal selesai harus *setelah* tanggal mulai."

        # Validasi 4: Maksimal 1 tahun ke depan
        max_date = today.replace(year=today.year + 1)
        if tgl_mulai > max_date:
            return f"❌ Tanggal mulai cuti *{tgl_mulai.strftime('%d %B %Y')}* terlalu jauh.\n\n📌 Maksimal pengajuan cuti adalah 1 tahun ke depan."

        # Validasi 5: Durasi cuti maksimal 14 hari
        MAX_HARI_CUTI_BERTURUT = 14
        jumlah_hari = (tgl_selesai - tgl_mulai).days + 1
        
        if jumlah_hari > MAX_HARI_CUTI_BERTURUT:
            return f"❌ Durasi cuti *{jumlah_hari} hari* melebihi batas maksimal *{MAX_HARI_CUTI_BERTURUT} hari* berturut-turut."

        # Validasi 6: Sisa cuti mencukupi
        if jumlah_hari > karyawan["sisa_cuti"]:
            return f"❌ Maaf, sisa cuti Anda hanya *{karyawan['sisa_cuti']} hari*, tidak cukup untuk *{jumlah_hari} hari*."

        # Validasi 7: Cek bentrok dengan pengajuan cuti lain
        sheet_pengajuan = get_sheet("PengajuanCuti")
        data_pengajuan = sheet_pengajuan.get_all_values()
        
        for row in data_pengajuan[1:]:
            if len(row) >= 5 and str(row[1]) == str(chat_id):
                try:
                    existing_mulai = datetime.strptime(row[3], "%Y-%m-%d")
                    existing_selesai = datetime.strptime(row[4], "%Y-%m-%d")
                    
                    if (tgl_mulai <= existing_selesai and tgl_selesai >= existing_mulai):
                        return (f"❌ *Bentrok dengan pengajuan cuti sebelumnya!*\n\n"
                                f"Anda sudah mengajukan cuti pada:\n"
                                f"📅 {existing_mulai.strftime('%d %B %Y')} → {existing_selesai.strftime('%d %B %Y')}\n\n"
                                f"Silakan ajukan cuti di luar periode tersebut.")
                except:
                    pass

        # SEMUA VALIDASI LOLOS
        sheet_pengajuan.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(chat_id),
            karyawan["nama"],
            tgl_mulai.strftime("%Y-%m-%d"),
            tgl_selesai.strftime("%Y-%m-%d"),
            jumlah_hari,
            "Menunggu Persetujuan"
        ])

        return (f"✅ *Pengajuan cuti berhasil!*\n\n"
                f"👤 Nama: {karyawan['nama']}\n"
                f"📅 Mulai: {tgl_mulai.strftime('%d %B %Y')}\n"
                f"📅 Selesai: {tgl_selesai.strftime('%d %B %Y')}\n"
                f"📊 Jumlah: {jumlah_hari} hari\n"
                f"⏳ Status: Menunggu Persetujuan")

    except Exception as e:
        import traceback
        print(f"Error ajukan cuti: {e}")
        print(traceback.format_exc())
        return f"❌ Terjadi kesalahan: {str(e)}"

def proses_status_cuti(chat_id):
    try:
        sheet = get_sheet("PengajuanCuti")
        data = sheet.get_all_values()
        pesan = "*📋 Status Pengajuan Cuti*\n\n"
        ada = False
        count = 0

        for row in reversed(data[1:]):
            if count >= 5:
                break
            if len(row) >= 7 and str(row[1]) == str(chat_id):
                ada = True
                count += 1
                status = row[6] if len(row) > 6 else "Menunggu"
                emoji = "✅" if status == "Disetujui" else ("❌" if status == "Ditolak" else "⏳")
                pesan += f"{emoji} *{status}*\n"
                pesan += f"📅 {row[3]} → {row[4]}\n"
                pesan += f"📊 {row[5]} hari\n\n"

        return pesan if ada else "📋 Belum ada pengajuan cuti."

    except Exception as e:
        print(f"Error status cuti: {e}")
        return "❌ Terjadi kesalahan saat mengecek status cuti."

def process_intent(chat_id, intent, params, fulfillment, original_text=""):
    karyawan = get_karyawan(chat_id)

    if not karyawan:
        return f"❌ Data karyawan tidak ditemukan.\nTelegram ID Anda: {chat_id}"

    print(f"Processing intent: {intent}")
    print(f"Params: {params}")

    if intent == "cek_saldo_cuti":
        return f"👋 Halo {karyawan['nama']}!\n\n📊 *Sisa cuti Anda: {karyawan['sisa_cuti']} hari*"

    elif intent == "ajukan_cuti":
        mulai = params.get("tanggal_mulai") or params.get("date") or params.get("startDate")
        selesai = params.get("tanggal_selesai") or params.get("date-range") or params.get("endDate")
        
        if not mulai or not selesai:
            mulai, selesai = extract_two_dates(original_text)
            print(f"Extracted from text: mulai={mulai}, selesai={selesai}")
        
        return proses_ajukan_cuti(chat_id, karyawan, mulai, selesai)

    elif intent in ["cek_status_cuti", "riwayat_cuti"]:
        return proses_status_cuti(chat_id)

    elif intent == "info_profil":
        return (f"👤 *Profil Karyawan*\n\n"
                f"Nama: {karyawan['nama']}\n"
                f"Jabatan: {karyawan['jabatan']}\n"
                f"Divisi: {karyawan['divisi']}\n"
                f"Atasan: {karyawan['atasan']}\n"
                f"Sisa Cuti: {karyawan['sisa_cuti']} hari")

    else:
        return fulfillment or "❓ Maaf, saya tidak mengerti.\n\nKetik *bantuan* untuk melihat perintah yang tersedia."

# ============ WEBHOOK ============
@app.route("/", methods=["GET"])
def index():
    return "Bot Cuti Karyawan dengan Dialogflow - Aktif"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print(f"Data masuk: {json.dumps(data, indent=2)}")

        if not data.get("message") or not data["message"].get("text"):
            return "ok", 200

        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]

        if text == "/start":
            karyawan = get_karyawan(chat_id)
            if karyawan:
                send_telegram(chat_id,
                    f"👋 Halo {karyawan['nama']}! 👋\n\n"
                    f"Selamat datang di *Bot Cuti Karyawan*.\n"
                    f"Sisa cuti Anda: *{karyawan['sisa_cuti']} hari*\n\n"
                    f"*Yang bisa saya bantu:*\n"
                    f"• Cek sisa cuti: *sisa cuti saya*\n"
                    f"• Ajukan cuti: *saya mau cuti dari 1 Desember 2024 sampai 5 Desember 2024*\n"
                    f"• Cek status: *status cuti saya*\n"
                    f"• Lihat profil: *profil saya*"
                )
            else:
                send_telegram(chat_id, f"❌ Data karyawan tidak ditemukan.\n\nTelegram ID Anda: `{chat_id}`\n\nSilakan hubungi admin untuk mendaftarkan ID ini.")
            return "ok", 200

        if text.lower() in ["bantuan", "help", "/help"]:
            send_telegram(chat_id,
                "🤖 *Bantuan Bot Cuti*\n\n"
                "*Perintah yang bisa digunakan:*\n\n"
                "1️⃣ *Cek Sisa Cuti*\n"
                "• `sisa cuti saya`\n"
                "• `cek cuti`\n\n"
                "2️⃣ *Ajukan Cuti*\n"
                "• `saya mau cuti dari 1 Desember 2024 sampai 5 Desember 2024`\n"
                "• `cuti 10-12-2024 sampai 15-12-2024`\n\n"
                "3️⃣ *Cek Status*\n"
                "• `status cuti saya`\n"
                "• `riwayat cuti`\n\n"
                "4️⃣ *Lihat Profil*\n"
                "• `profil saya`\n"
                "• `info saya`"
            )
            return "ok", 200

        intent, params, fulfillment = detect_intent(chat_id, text)
        print(f"Intent: {intent}")
        print(f"Params: {params}")

        response_text = process_intent(chat_id, intent, params, fulfillment, text)
        print(f"Response: {response_text}")
        send_telegram(chat_id, response_text)

        return "ok", 200

    except Exception as e:
        import traceback
        print(f"Error webhook: {e}")
        print(traceback.format_exc())
        return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
