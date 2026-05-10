import os
import json
import requests
import re
import gspread
from flask import Flask, request
from google.oauth2.service_account import Credentials
from datetime import datetime
from dateutil import parser
import calendar

app = Flask(__name__)

# ============ KONFIGURASI ============
TOKEN = "8620563805:AAGQNY5h3rXTKj6DpI04vcXcHKC4axTwT0A"
SPREADSHEET_ID = "1eBI6Dor4DiNczYOrpXQDiN6sXaRyAZg_ahCVV_1d_HE"
DIALOGFLOW_PROJECT_ID = "newagent-enoo"

# Service Account untuk Google Sheets & Dialogflow
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

# ============ PARSING TANGGAL (PERBAIKAN UTAMA) ============
def parse_tanggal_indonesia(text):
    """Mengekstrak tanggal dari teks bahasa Indonesia"""
    # Pola: 1 Desember 2024, 12 Januari 2025, dll
    pattern = r'(\d{1,2})\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|jan|feb|mar|apr|jun|jul|agu|sep|okt|nov|des)\s+(\d{4})'
    matches = re.findall(pattern, text.lower())
    
    if matches:
        for match in matches:
            hari = int(match[0])
            bulan = BULAN_MAP.get(match[1])
            tahun = int(match[2])
            if 1 <= hari <= 31 and 1 <= bulan <= 12 and tahun > 2000:
                return f"{tahun}-{bulan:02d}-{hari:02d}"
    
    # Pola: 12-01-2024, 12/01/2024, 12.01.2024
    pattern2 = r'(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})'
    matches2 = re.findall(pattern2, text)
    
    if matches2:
        for match in matches2:
            # Coba interpretasi sebagai DD-MM-YYYY
            hari = int(match[0])
            bulan = int(match[1])
            tahun = int(match[2])
            if 1 <= hari <= 31 and 1 <= bulan <= 12:
                return f"{tahun}-{bulan:02d}-{hari:02d}"
    
    # Pola: 2024-12-01 (ISO)
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
    # Cari pola "dari [tanggal] sampai [tanggal]"
    pattern = r'dari\s+(.+?)\s+sampai\s+(.+)'
    match = re.search(pattern, text.lower())
    
    if match:
        tgl1_str = match.group(1).strip()
        tgl2_str = match.group(2).strip()
        
        # Ekstrak tanggal dari masing-masing string
        tgl1 = parse_tanggal_indonesia(tgl1_str)
        tgl2 = parse_tanggal_indonesia(tgl2_str)
        
        if tgl1 and tgl2:
            return tgl1, tgl2
    
    # Cari semua tanggal dalam teks
    semua_tanggal = []
    for word in text.split():
        parsed = parse_tanggal_indonesia(word)
        if parsed:
            semua_tanggal.append(parsed)
    
    # Coba juga cari di seluruh teks
    if not semua_tanggal:
        # Cari pola tanggal dalam kalimat
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
        print(f"Dialogflow result: {json.dumps(result, indent=2)}")

        intent = result.get("queryResult", {}).get("intent", {}).get("displayName", "Default Fallback Intent")
        params = result.get("queryResult", {}).get("parameters", {})
        
        # Parse parameters dari Dialogflow
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
        import traceback
        print(f"Error detect_intent: {e}")
        print(traceback.format_exc())
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

# ============ PROSES INTENT ============
def proses_ajukan_cuti(chat_id, karyawan, mulai, selesai):
    try:
        if not mulai or not selesai:
            return ("❌ Mohon berikan tanggal mulai dan selesai cuti.\n\n"
                    "Contoh: *saya mau cuti dari 1 Desember 2024 sampai 5 Desember 2024*")

        # Pastikan format tanggal benar
        if isinstance(mulai, dict):
            mulai = mulai.get("startDate", mulai.get("stringValue", str(mulai)))
        if isinstance(selesai, dict):
            selesai = selesai.get("endDate", selesai.get("stringValue", str(selesai)))
        
        # Ambil hanya YYYY-MM-DD
        mulai_str = str(mulai)[:10]
        selesai_str = str(selesai)[:10]
        
        print(f"Processing cuti: mulai={mulai_str}, selesai={selesai_str}")
        
        tgl_mulai = datetime.strptime(mulai_str, "%Y-%m-%d")
        tgl_selesai = datetime.strptime(selesai_str, "%Y-%m-%d")

        # ============ VALIDASI TANGGAL ============
        
        # 1. Validasi tanggal tidak boleh hari ini atau yang sudah lewat
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tgl_mulai_tanpa_waktu = tgl_mulai.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if tgl_mulai_tanpa_waktu < today:
            return f"❌ Tanggal mulai cuti *{tgl_mulai.strftime('%d %B %Y')}* sudah lewat.\n\n📌 Cuti harus diajukan minimal H-1 (satu hari sebelum tanggal cuti)."
        
        # 2. Validasi tanggal mulai tidak boleh sama dengan hari ini (opsional, bisa diatur)
        if tgl_mulai_tanpa_waktu == today:
            return f"❌ Tanggal mulai cuti *{tgl_mulai.strftime('%d %B %Y')}* adalah hari ini.\n\n📌 Pengajuan cuti harus dilakukan *minimal 1 hari sebelum* tanggal cuti dimulai."
        
        # 3. Validasi tanggal selesai harus setelah tanggal mulai
        if tgl_selesai < tgl_mulai:
            return "❌ Tanggal selesai harus *setelah* tanggal mulai."

        # 4. Validasi tanggal mulai tidak boleh lebih dari 1 tahun ke depan
        max_date = today.replace(year=today.year + 1)
        if tgl_mulai > max_date:
            return f"❌ Tanggal mulai cuti *{tgl_mulai.strftime('%d %B %Y')}* terlalu jauh.\n\n📌 Maksimal pengajuan cuti adalah 1 tahun ke depan."

        # 5. Validasi durasi cuti maksimal (misal: maksimal 14 hari berturut-turut)
        MAX_HARI_CUTI_BERTURUT = 14
        jumlah_hari = (tgl_selesai - tgl_mulai).days + 1
        
        if jumlah_hari > MAX_HARI_CUTI_BERTURUT:
            return f"❌ Durasi cuti *{jumlah_hari} hari* melebihi batas maksimal *{MAX_HARI_CUTI_BERTURUT} hari* berturut-turut."

        # 6. Validasi sisa cuti mencukupi
        if jumlah_hari > karyawan["sisa_cuti"]:
            return f"❌ Maaf, sisa cuti Anda hanya *{karyawan['sisa_cuti']} hari*, tidak cukup untuk *{jumlah_hari} hari*."

        # 7. Validasi tidak ada cuti yang bentrok (opsional)
        # Cek apakah sudah ada pengajuan cuti di tanggal yang sama
        sheet_pengajuan = get_sheet("PengajuanCuti")
        data_pengajuan = sheet_pengajuan.get_all_values()
        
        for row in data_pengajuan[1:]:
            if len(row) >= 5 and str(row[1]) == str(chat_id):
                existing_mulai = datetime.strptime(row[3], "%Y-%m-%d")
                existing_selesai = datetime.strptime(row[4], "%Y-%m-%d")
                
                # Cek apakah tanggal bentrok
                if (tgl_mulai <= existing_selesai and tgl_selesai >= existing_mulai):
                    return (f"❌ *Bentrok dengan pengajuan cuti sebelumnya!*\n\n"
                            f"Anda sudah mengajukan cuti pada:\n"
                            f"📅 {existing_mulai.strftime('%d %B %Y')} → {existing_selesai.strftime('%d %B %Y')}\n\n"
                            f"Silakan ajukan cuti di luar periode tersebut.")

        # 8. Validasi tidak ada cuti di hari libur nasional (opsional, bisa ditambahkan nanti)
        # if is_libur_nasional(tgl_mulai, tgl_selesai):
        #     return "❌ Maaf, tanggal yang Anda pilih bertepatan dengan hari libur nasional."

        # === SEMUA VALIDASI LOLOS ===
        
        sheet = get_sheet("PengajuanCuti")
        sheet.append_row([
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
                f"⏳ Status: Menunggu Persetujuan\n\n"
                f"📌 *Catatan:* Pengajuan akan diproses oleh atasan Anda.")

    except Exception as e:
        import traceback
        print(f"Error ajukan cuti: {e}")
        print(traceback.format_exc())
        return f"❌ Terjadi kesalahan: {str(e)}"

def is_weekend(date):
    """Cek apakah tanggal adalah weekend (Sabtu=5, Minggu=6)"""
    return date.weekday() >= 5  # 5=Sabtu, 6=Minggu

# Tambahkan di validasi:
weekend_count = 0
current_date = tgl_mulai
while current_date <= tgl_selesai:
    if is_weekend(current_date):
        weekend_count += 1
    current_date += timedelta(days=1)

if weekend_count == jumlah_hari:
    return "❌ Maaf, cuti tidak dapat diajukan pada hari Sabtu dan Minggu.\n\n📌 Silakan pilih hari kerja."

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
        # Ambil tanggal dari params atau dari teks asli
        mulai = params.get("tanggal_mulai") or params.get("date") or params.get("startDate")
        selesai = params.get("tanggal_selesai") or params.get("date-range") or params.get("endDate")
        
        # Jika tidak ada dari Dialogflow, ekstrak dari teks asli
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

        # Handle /start
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

        # Handle bantuan
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

        # Kirim ke Dialogflow
        intent, params, fulfillment = detect_intent(chat_id, text)
        print(f"Intent: {intent}")
        print(f"Params: {params}")

        # Proses intent
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
