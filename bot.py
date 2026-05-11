import os
import json
import logging
import requests
import re
import gspread
from flask import Flask, request
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import calendar

# Load .env file untuk development lokal
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============ LOGGING ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============ KONFIGURASI (dari Environment Variables) ============
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")
DIALOGFLOW_PROJECT_ID = os.environ.get("DIALOGFLOW_PROJECT_ID", "")

# Service Account dari environment variable (JSON string)
_sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
try:
    SERVICE_ACCOUNT_INFO = json.loads(_sa_json)
except json.JSONDecodeError:
    logger.error("GOOGLE_SERVICE_ACCOUNT_JSON bukan JSON yang valid!")
    SERVICE_ACCOUNT_INFO = {}

# Mapping bulan Indonesia
BULAN_MAP = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'agustus': 8, 'september': 9, 'oktober': 10, 'november': 11, 'desember': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'agu': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'des': 12
}

# Hari libur nasional Indonesia 2026 (update setiap tahun)
HARI_LIBUR = [
    # 2026
    "2026-01-01",  # Tahun Baru
    "2026-01-29",  # Isra Mi'raj
    "2026-02-17",  # Tahun Baru Imlek
    "2026-03-20",  # Hari Raya Nyepi
    "2026-03-29",  # Idul Fitri (perkiraan)
    "2026-03-30",  # Idul Fitri (perkiraan)
    "2026-04-03",  # Wafat Isa Al-Masih
    "2026-05-01",  # Hari Buruh
    "2026-05-14",  # Kenaikan Isa Al-Masih
    "2026-05-26",  # Hari Raya Waisak
    "2026-06-01",  # Hari Lahir Pancasila
    "2026-06-05",  # Idul Adha (perkiraan)
    "2026-06-26",  # Tahun Baru Islam (perkiraan)
    "2026-08-17",  # Hari Kemerdekaan
    "2026-09-05",  # Maulid Nabi (perkiraan)
    "2026-12-25",  # Hari Natal
    # 2025
    "2025-01-01",  # Tahun Baru
    "2025-01-27",  # Isra Mi'raj
    "2025-01-29",  # Tahun Baru Imlek
    "2025-03-29",  # Hari Raya Nyepi
    "2025-03-31",  # Idul Fitri
    "2025-04-01",  # Idul Fitri
    "2025-04-18",  # Wafat Isa Al-Masih
    "2025-05-01",  # Hari Buruh
    "2025-05-12",  # Hari Raya Waisak
    "2025-05-29",  # Kenaikan Isa Al-Masih
    "2025-06-01",  # Hari Lahir Pancasila
    "2025-06-07",  # Idul Adha
    "2025-06-27",  # Tahun Baru Islam
    "2025-08-17",  # Hari Kemerdekaan
    "2025-09-05",  # Maulid Nabi
    "2025-12-25",  # Hari Natal
]


# ============ HITUNG HARI KERJA ============
def hitung_hari_kerja(tgl_mulai, tgl_selesai):
    """Hitung jumlah hari kerja (exclude weekend Sabtu-Minggu dan hari libur nasional)"""
    hari_kerja = 0
    current = tgl_mulai
    detail_libur = []

    while current <= tgl_selesai:
        is_weekend = current.weekday() in (5, 6)  # 5=Sabtu, 6=Minggu
        is_libur = current.strftime("%Y-%m-%d") in HARI_LIBUR

        if not is_weekend and not is_libur:
            hari_kerja += 1
        else:
            if is_weekend:
                detail_libur.append(f"{current.strftime('%d %b')} (weekend)")
            else:
                detail_libur.append(f"{current.strftime('%d %b')} (libur nasional)")

        current += timedelta(days=1)

    return hari_kerja, detail_libur


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
        logger.error(f"Error get_karyawan: {e}")
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
        logger.error(f"Error detect_intent: {e}")
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
        logger.error(f"Error send_telegram: {e}")


# ============ PROSES CUTI DENGAN VALIDASI ============
def proses_ajukan_cuti(chat_id, karyawan, mulai, selesai):
    try:
        if not mulai or not selesai:
            return ("❌ Mohon berikan tanggal mulai dan selesai cuti.\n\n"
                    "Contoh: *saya mau cuti dari 1 Desember 2026 sampai 5 Desember 2026*")

        logger.debug(f"Raw mulai={mulai} ({type(mulai)}), selesai={selesai} ({type(selesai)})")

        # Pastikan format tanggal benar
        if isinstance(mulai, dict):
            mulai = mulai.get("startDate") or mulai.get("stringValue") or mulai.get("date") or str(mulai)
        if isinstance(selesai, dict):
            selesai = selesai.get("endDate") or selesai.get("stringValue") or selesai.get("date") or str(selesai)

        # Konversi ke string
        mulai_str = str(mulai)
        selesai_str = str(selesai)

        # Ekstrak tahun dari string menggunakan regex
        tahun_mulai_match = re.search(r'(202\d|203\d)', mulai_str)
        tahun_selesai_match = re.search(r'(202\d|203\d)', selesai_str)

        tahun_mulai = tahun_mulai_match.group(1) if tahun_mulai_match else None
        tahun_selesai = tahun_selesai_match.group(1) if tahun_selesai_match else None

        # Bersihkan string tanggal
        if 'T' in mulai_str:
            mulai_str = mulai_str.split('T')[0]
        if 'T' in selesai_str:
            selesai_str = selesai_str.split('T')[0]

        # Ekstrak YYYY-MM-DD
        match_mulai = re.search(r'(\d{4})-(\d{2})-(\d{2})', mulai_str)
        match_selesai = re.search(r'(\d{4})-(\d{2})-(\d{2})', selesai_str)

        if match_mulai:
            tgl_mulai = datetime(int(match_mulai.group(1)), int(match_mulai.group(2)), int(match_mulai.group(3)))
        else:
            tgl_mulai = datetime.strptime(mulai_str[:10], "%Y-%m-%d")

        if match_selesai:
            tgl_selesai = datetime(int(match_selesai.group(1)), int(match_selesai.group(2)), int(match_selesai.group(3)))
        else:
            tgl_selesai = datetime.strptime(selesai_str[:10], "%Y-%m-%d")

        # Koreksi tahun jika Dialogflow kasih default 2024
        if tahun_mulai and tgl_mulai.year == 2024 and tahun_mulai != '2024':
            tgl_mulai = tgl_mulai.replace(year=int(tahun_mulai))

        if tahun_selesai and tgl_selesai.year == 2024 and tahun_selesai != '2024':
            tgl_selesai = tgl_selesai.replace(year=int(tahun_selesai))

        logger.info(f"Pengajuan cuti: {karyawan['nama']} | {tgl_mulai.date()} - {tgl_selesai.date()}")

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

        # Validasi 5: Hitung hari kerja (exclude weekend & libur nasional)
        jumlah_hari_kerja, detail_libur = hitung_hari_kerja(tgl_mulai, tgl_selesai)
        jumlah_hari_kalender = (tgl_selesai - tgl_mulai).days + 1

        if jumlah_hari_kerja == 0:
            return ("❌ Periode yang Anda pilih tidak mengandung hari kerja.\n\n"
                    "📌 Semua tanggal dalam rentang tersebut adalah weekend atau hari libur nasional.")

        # Validasi 6: Durasi cuti maksimal 14 hari kerja
        MAX_HARI_CUTI_BERTURUT = 14
        if jumlah_hari_kerja > MAX_HARI_CUTI_BERTURUT:
            return f"❌ Durasi cuti *{jumlah_hari_kerja} hari kerja* melebihi batas maksimal *{MAX_HARI_CUTI_BERTURUT} hari kerja* berturut-turut."

        # Validasi 7: Sisa cuti mencukupi
        if jumlah_hari_kerja > karyawan["sisa_cuti"]:
            return f"❌ Maaf, sisa cuti Anda hanya *{karyawan['sisa_cuti']} hari*, tidak cukup untuk *{jumlah_hari_kerja} hari kerja*."

        # Validasi 8: Cek bentrok dengan pengajuan cuti lain
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
                except Exception:
                    pass

        # SEMUA VALIDASI LOLOS - Simpan ke spreadsheet
        sheet_pengajuan.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(chat_id),
            karyawan["nama"],
            tgl_mulai.strftime("%Y-%m-%d"),
            tgl_selesai.strftime("%Y-%m-%d"),
            jumlah_hari_kerja,
            "Menunggu Persetujuan"
        ])

        # Buat info tambahan jika ada weekend/libur yang di-skip
        info_libur = ""
        if detail_libur:
            info_libur = f"\n📌 _Tidak dihitung: {len(detail_libur)} hari (weekend/libur)_"

        return (f"✅ *Pengajuan cuti berhasil!*\n\n"
                f"👤 Nama: {karyawan['nama']}\n"
                f"📅 Mulai: {tgl_mulai.strftime('%d %B %Y')}\n"
                f"📅 Selesai: {tgl_selesai.strftime('%d %B %Y')}\n"
                f"📊 Jumlah: *{jumlah_hari_kerja} hari kerja* (dari {jumlah_hari_kalender} hari kalender)"
                f"{info_libur}\n"
                f"⏳ Status: Menunggu Persetujuan")

    except Exception as e:
        logger.exception(f"Error ajukan cuti untuk chat_id={chat_id}")
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
                pesan += f"📊 {row[5]} hari kerja\n\n"

        return pesan if ada else "📋 Belum ada pengajuan cuti."

    except Exception as e:
        logger.error(f"Error status cuti: {e}")
        return "❌ Terjadi kesalahan saat mengecek status cuti."


def process_intent(chat_id, intent, params, fulfillment, original_text=""):
    karyawan = get_karyawan(chat_id)

    if not karyawan:
        return f"❌ Data karyawan tidak ditemukan.\nTelegram ID Anda: {chat_id}"

    logger.info(f"Intent: {intent} | chat_id: {chat_id} | params: {params}")

    if intent == "cek_saldo_cuti":
        return f"👋 Halo {karyawan['nama']}!\n\n📊 *Sisa cuti Anda: {karyawan['sisa_cuti']} hari*"

    elif intent == "ajukan_cuti":
        mulai = params.get("tanggal_mulai") or params.get("date") or params.get("startDate")
        selesai = params.get("tanggal_selesai") or params.get("date-range") or params.get("endDate")

        if not mulai or not selesai:
            mulai, selesai = extract_two_dates(original_text)
            logger.debug(f"Extracted from text: mulai={mulai}, selesai={selesai}")

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
        logger.info(f"Webhook received from chat_id: {data.get('message', {}).get('chat', {}).get('id', 'unknown')}")

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
                    f"• Ajukan cuti: *saya mau cuti dari 1 Desember 2026 sampai 5 Desember 2026*\n"
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
                "• `saya mau cuti dari 1 Desember 2026 sampai 5 Desember 2026`\n"
                "• `cuti 10-12-2026 sampai 15-12-2026`\n\n"
                "3️⃣ *Cek Status*\n"
                "• `status cuti saya`\n"
                "• `riwayat cuti`\n\n"
                "4️⃣ *Lihat Profil*\n"
                "• `profil saya`\n"
                "• `info saya`"
            )
            return "ok", 200

        intent, params, fulfillment = detect_intent(chat_id, text)
        response_text = process_intent(chat_id, intent, params, fulfillment, text)
        send_telegram(chat_id, response_text)

        return "ok", 200

    except Exception as e:
        logger.exception("Error di webhook")
        return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
