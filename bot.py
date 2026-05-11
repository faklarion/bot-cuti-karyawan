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

# Mapping nama bulan untuk format output
NAMA_BULAN = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
    7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
}

# Pilihan alasan cuti
ALASAN_CUTI = {
    "pribadi": "Keperluan Pribadi",
    "sakit": "Sakit",
    "keluarga": "Keperluan Keluarga",
    "menikah": "Menikah",
    "melahirkan": "Melahirkan",
    "duka": "Kedukaan",
    "lainnya": "Lainnya"
}

# Hari libur nasional Indonesia (update setiap tahun)
HARI_LIBUR = [
    # 2026
    "2026-01-01", "2026-01-29", "2026-02-17", "2026-03-20",
    "2026-03-29", "2026-03-30", "2026-04-03", "2026-05-01",
    "2026-05-14", "2026-05-26", "2026-06-01", "2026-06-05",
    "2026-06-26", "2026-08-17", "2026-09-05", "2026-12-25",
    # 2025
    "2025-01-01", "2025-01-27", "2025-01-29", "2025-03-29",
    "2025-03-31", "2025-04-01", "2025-04-18", "2025-05-01",
    "2025-05-12", "2025-05-29", "2025-06-01", "2025-06-07",
    "2025-06-27", "2025-08-17", "2025-09-05", "2025-12-25",
]

# Temporary storage untuk pending cuti (sebelum konfirmasi)
# Format: {chat_id: {mulai, selesai, hari_kerja, hari_kalender, alasan, timestamp}}
pending_cuti = {}


# ============ FORMAT TANGGAL INDONESIA ============
def format_tanggal(tgl):
    """Format datetime ke string Indonesia: '1 Desember 2026'"""
    if isinstance(tgl, str):
        tgl = datetime.strptime(tgl, "%Y-%m-%d")
    return f"{tgl.day} {NAMA_BULAN[tgl.month]} {tgl.year}"


def format_tanggal_singkat(tgl):
    """Format datetime ke string singkat: '1 Des 2026'"""
    if isinstance(tgl, str):
        tgl = datetime.strptime(tgl, "%Y-%m-%d")
    bulan_singkat = NAMA_BULAN[tgl.month][:3]
    return f"{tgl.day} {bulan_singkat} {tgl.year}"


# ============ HITUNG HARI KERJA ============
def hitung_hari_kerja(tgl_mulai, tgl_selesai):
    """Hitung jumlah hari kerja (exclude weekend Sabtu-Minggu dan hari libur nasional)"""
    hari_kerja = 0
    current = tgl_mulai
    detail_libur = []

    while current <= tgl_selesai:
        is_weekend = current.weekday() in (5, 6)
        is_libur = current.strftime("%Y-%m-%d") in HARI_LIBUR

        if not is_weekend and not is_libur:
            hari_kerja += 1
        else:
            if is_weekend:
                detail_libur.append(f"{format_tanggal_singkat(current)} (weekend)")
            else:
                detail_libur.append(f"{format_tanggal_singkat(current)} (libur nasional)")

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
def send_telegram(chat_id, text, reply_markup=None):
    """Kirim pesan teks biasa atau dengan inline keyboard"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Error send_telegram: {e}")


def edit_telegram_message(chat_id, message_id, text, reply_markup=None):
    """Edit pesan yang sudah terkirim (untuk update inline keyboard)"""
    url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Error edit_telegram_message: {e}")


def answer_callback(callback_query_id, text=""):
    """Jawab callback query (hilangkan loading di tombol)"""
    url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
    try:
        requests.post(url, json={
            "callback_query_id": callback_query_id,
            "text": text
        })
    except Exception as e:
        logger.error(f"Error answer_callback: {e}")


# ============ PROSES CUTI DENGAN KONFIRMASI ============
def validasi_cuti(chat_id, karyawan, mulai, selesai):
    """Validasi pengajuan cuti dan return data atau error message"""
    try:
        if not mulai or not selesai:
            return None, ("❌ Mohon berikan tanggal mulai dan selesai cuti.\n\n"
                          "Contoh: *saya mau cuti dari 1 Desember 2026 sampai 5 Desember 2026*")

        logger.debug(f"Raw mulai={mulai} ({type(mulai)}), selesai={selesai} ({type(selesai)})")

        # Pastikan format tanggal benar
        if isinstance(mulai, dict):
            mulai = mulai.get("startDate") or mulai.get("stringValue") or mulai.get("date") or str(mulai)
        if isinstance(selesai, dict):
            selesai = selesai.get("endDate") or selesai.get("stringValue") or selesai.get("date") or str(selesai)

        mulai_str = str(mulai)
        selesai_str = str(selesai)

        # Ekstrak tahun
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

        # Koreksi tahun
        if tahun_mulai and tgl_mulai.year == 2024 and tahun_mulai != '2024':
            tgl_mulai = tgl_mulai.replace(year=int(tahun_mulai))
        if tahun_selesai and tgl_selesai.year == 2024 and tahun_selesai != '2024':
            tgl_selesai = tgl_selesai.replace(year=int(tahun_selesai))

        logger.info(f"Pengajuan cuti: {karyawan['nama']} | {tgl_mulai.date()} - {tgl_selesai.date()}")

        # ============ VALIDASI ============
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tgl_mulai_clean = tgl_mulai.replace(hour=0, minute=0, second=0, microsecond=0)

        if tgl_mulai_clean < today:
            return None, f"❌ Tanggal mulai cuti *{format_tanggal(tgl_mulai)}* sudah lewat.\n\n📌 Cuti harus diajukan minimal H-1."

        if tgl_mulai_clean == today:
            return None, f"❌ Tanggal mulai cuti *{format_tanggal(tgl_mulai)}* adalah hari ini.\n\n📌 Pengajuan cuti harus dilakukan *minimal 1 hari sebelum* tanggal cuti dimulai."

        if tgl_selesai < tgl_mulai:
            return None, "❌ Tanggal selesai harus *setelah* tanggal mulai."

        max_date = today.replace(year=today.year + 1)
        if tgl_mulai > max_date:
            return None, f"❌ Tanggal mulai cuti *{format_tanggal(tgl_mulai)}* terlalu jauh.\n\n📌 Maksimal pengajuan cuti adalah 1 tahun ke depan."

        jumlah_hari_kerja, detail_libur = hitung_hari_kerja(tgl_mulai, tgl_selesai)
        jumlah_hari_kalender = (tgl_selesai - tgl_mulai).days + 1

        if jumlah_hari_kerja == 0:
            return None, "❌ Periode yang Anda pilih tidak mengandung hari kerja.\n\n📌 Semua tanggal adalah weekend atau hari libur nasional."

        MAX_HARI_CUTI_BERTURUT = 14
        if jumlah_hari_kerja > MAX_HARI_CUTI_BERTURUT:
            return None, f"❌ Durasi cuti *{jumlah_hari_kerja} hari kerja* melebihi batas maksimal *{MAX_HARI_CUTI_BERTURUT} hari kerja*."

        if jumlah_hari_kerja > karyawan["sisa_cuti"]:
            return None, f"❌ Sisa cuti Anda hanya *{karyawan['sisa_cuti']} hari*, tidak cukup untuk *{jumlah_hari_kerja} hari kerja*."

        # Cek bentrok
        sheet_pengajuan = get_sheet("PengajuanCuti")
        data_pengajuan = sheet_pengajuan.get_all_values()

        for row in data_pengajuan[1:]:
            if len(row) >= 5 and str(row[1]) == str(chat_id):
                try:
                    existing_mulai = datetime.strptime(row[3], "%Y-%m-%d")
                    existing_selesai = datetime.strptime(row[4], "%Y-%m-%d")
                    status = row[6] if len(row) > 6 else ""

                    # Skip yang sudah dibatalkan
                    if status == "Dibatalkan":
                        continue

                    if tgl_mulai <= existing_selesai and tgl_selesai >= existing_mulai:
                        return None, (f"❌ *Bentrok dengan pengajuan cuti sebelumnya!*\n\n"
                                      f"Anda sudah mengajukan cuti pada:\n"
                                      f"📅 {format_tanggal(existing_mulai)} \u2192 {format_tanggal(existing_selesai)}\n\n"
                                      f"Silakan ajukan cuti di luar periode tersebut.")
                except Exception:
                    pass

        # Validasi lolos, return data
        return {
            "tgl_mulai": tgl_mulai,
            "tgl_selesai": tgl_selesai,
            "hari_kerja": jumlah_hari_kerja,
            "hari_kalender": jumlah_hari_kalender,
            "detail_libur": detail_libur
        }, None

    except Exception as e:
        logger.exception(f"Error validasi cuti untuk chat_id={chat_id}")
        return None, f"❌ Terjadi kesalahan: {str(e)}"


def proses_ajukan_cuti(chat_id, karyawan, mulai, selesai):
    """Validasi dan tampilkan konfirmasi dengan inline keyboard"""
    data, error = validasi_cuti(chat_id, karyawan, mulai, selesai)

    if error:
        send_telegram(chat_id, error)
        return

    # Simpan ke pending
    pending_cuti[chat_id] = {
        "mulai": data["tgl_mulai"].strftime("%Y-%m-%d"),
        "selesai": data["tgl_selesai"].strftime("%Y-%m-%d"),
        "hari_kerja": data["hari_kerja"],
        "hari_kalender": data["hari_kalender"],
        "alasan": None,
        "timestamp": datetime.now().isoformat()
    }

    # Info libur
    info_libur = ""
    if data["detail_libur"]:
        info_libur = f"\n📌 _Tidak dihitung: {len(data['detail_libur'])} hari (weekend/libur)_"

    # Kirim konfirmasi dengan pilihan alasan
    text = (f"📋 *Konfirmasi Pengajuan Cuti*\n\n"
            f"👤 Nama: {karyawan['nama']}\n"
            f"📅 Mulai: {format_tanggal(data['tgl_mulai'])}\n"
            f"📅 Selesai: {format_tanggal(data['tgl_selesai'])}\n"
            f"📊 Jumlah: *{data['hari_kerja']} hari kerja* (dari {data['hari_kalender']} hari kalender)"
            f"{info_libur}\n\n"
            f"📝 *Pilih alasan cuti:*")

    # Inline keyboard untuk alasan cuti
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🏠 Pribadi", "callback_data": "alasan_pribadi"},
                {"text": "🤒 Sakit", "callback_data": "alasan_sakit"}
            ],
            [
                {"text": "👨‍👩‍👧 Keluarga", "callback_data": "alasan_keluarga"},
                {"text": "💒 Menikah", "callback_data": "alasan_menikah"}
            ],
            [
                {"text": "🤱 Melahirkan", "callback_data": "alasan_melahirkan"},
                {"text": "🕊️ Kedukaan", "callback_data": "alasan_duka"}
            ],
            [
                {"text": "📄 Lainnya", "callback_data": "alasan_lainnya"}
            ],
            [
                {"text": "❌ Batalkan", "callback_data": "batal_pengajuan"}
            ]
        ]
    }

    send_telegram(chat_id, text, reply_markup=keyboard)


def konfirmasi_final(chat_id, message_id, alasan_key):
    """Tampilkan konfirmasi final setelah alasan dipilih"""
    if chat_id not in pending_cuti:
        edit_telegram_message(chat_id, message_id, "❌ Sesi pengajuan sudah kadaluarsa. Silakan ajukan ulang.")
        return

    pending = pending_cuti[chat_id]
    pending["alasan"] = ALASAN_CUTI.get(alasan_key, "Lainnya")

    text = (f"📋 *Konfirmasi Final*\n\n"
            f"📅 Mulai: {format_tanggal(pending['mulai'])}\n"
            f"📅 Selesai: {format_tanggal(pending['selesai'])}\n"
            f"📊 Jumlah: *{pending['hari_kerja']} hari kerja*\n"
            f"📝 Alasan: {pending['alasan']}\n\n"
            f"Apakah Anda yakin ingin mengajukan cuti ini?")

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Ya, Ajukan", "callback_data": "konfirmasi_ya"},
                {"text": "❌ Tidak, Batalkan", "callback_data": "konfirmasi_tidak"}
            ]
        ]
    }

    edit_telegram_message(chat_id, message_id, text, reply_markup=keyboard)


def simpan_cuti(chat_id, message_id):
    """Simpan cuti ke spreadsheet setelah dikonfirmasi"""
    if chat_id not in pending_cuti:
        edit_telegram_message(chat_id, message_id, "❌ Sesi pengajuan sudah kadaluarsa. Silakan ajukan ulang.")
        return

    pending = pending_cuti.pop(chat_id)
    karyawan = get_karyawan(chat_id)

    if not karyawan:
        edit_telegram_message(chat_id, message_id, "❌ Data karyawan tidak ditemukan.")
        return

    try:
        sheet_pengajuan = get_sheet("PengajuanCuti")
        sheet_pengajuan.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(chat_id),
            karyawan["nama"],
            pending["mulai"],
            pending["selesai"],
            pending["hari_kerja"],
            "Menunggu Persetujuan",
            pending["alasan"]
        ])

        info_libur = ""
        hari_kalender = pending.get("hari_kalender", pending["hari_kerja"])
        if hari_kalender > pending["hari_kerja"]:
            skip = hari_kalender - pending["hari_kerja"]
            info_libur = f"\n📌 _Tidak dihitung: {skip} hari (weekend/libur)_"

        text = (f"✅ *Pengajuan cuti berhasil disimpan!*\n\n"
                f"👤 Nama: {karyawan['nama']}\n"
                f"📅 Mulai: {format_tanggal(pending['mulai'])}\n"
                f"📅 Selesai: {format_tanggal(pending['selesai'])}\n"
                f"📊 Jumlah: *{pending['hari_kerja']} hari kerja*"
                f"{info_libur}\n"
                f"📝 Alasan: {pending['alasan']}\n"
                f"⏳ Status: Menunggu Persetujuan")

        edit_telegram_message(chat_id, message_id, text)
        logger.info(f"Cuti disimpan: {karyawan['nama']} | {pending['mulai']} - {pending['selesai']} | {pending['alasan']}")

    except Exception as e:
        logger.exception(f"Error simpan cuti: {e}")
        edit_telegram_message(chat_id, message_id, f"❌ Gagal menyimpan: {str(e)}")


# ============ BATALKAN CUTI ============
def proses_batalkan_cuti(chat_id):
    """Tampilkan daftar cuti yang bisa dibatalkan"""
    try:
        sheet = get_sheet("PengajuanCuti")
        data = sheet.get_all_values()
        cuti_aktif = []

        for i, row in enumerate(data[1:], start=2):  # start=2 karena row 1 adalah header
            if len(row) >= 7 and str(row[1]) == str(chat_id):
                status = row[6]
                if status == "Menunggu Persetujuan":
                    cuti_aktif.append({
                        "row_index": i,
                        "mulai": row[3],
                        "selesai": row[4],
                        "hari": row[5]
                    })

        if not cuti_aktif:
            send_telegram(chat_id, "📋 Tidak ada pengajuan cuti yang bisa dibatalkan.\n\n_Hanya cuti dengan status 'Menunggu Persetujuan' yang bisa dibatalkan._")
            return

        text = "*🗑️ Pilih cuti yang ingin dibatalkan:*\n\n"
        buttons = []

        for idx, cuti in enumerate(cuti_aktif[:5]):  # Maksimal 5
            text += f"{idx+1}. 📅 {format_tanggal(cuti['mulai'])} \u2192 {format_tanggal(cuti['selesai'])} ({cuti['hari']} hari)\n"
            buttons.append([{
                "text": f"🗑️ Batalkan #{idx+1}",
                "callback_data": f"batalkan_{cuti['row_index']}"
            }])

        buttons.append([{"text": "↩️ Kembali", "callback_data": "batal_menu"}])

        keyboard = {"inline_keyboard": buttons}
        send_telegram(chat_id, text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error proses_batalkan_cuti: {e}")
        send_telegram(chat_id, "❌ Terjadi kesalahan saat mengambil data cuti.")


def eksekusi_batalkan_cuti(chat_id, message_id, row_index):
    """Batalkan cuti di spreadsheet"""
    try:
        sheet = get_sheet("PengajuanCuti")
        row_data = sheet.row_values(row_index)

        if not row_data or str(row_data[1]) != str(chat_id):
            edit_telegram_message(chat_id, message_id, "❌ Data cuti tidak ditemukan atau bukan milik Anda.")
            return

        if len(row_data) > 6 and row_data[6] != "Menunggu Persetujuan":
            edit_telegram_message(chat_id, message_id, "❌ Cuti ini sudah tidak bisa dibatalkan karena statusnya sudah berubah.")
            return

        # Update status menjadi "Dibatalkan"
        sheet.update_cell(row_index, 7, "Dibatalkan")

        text = (f"✅ *Cuti berhasil dibatalkan!*\n\n"
                f"📅 {format_tanggal(row_data[3])} \u2192 {format_tanggal(row_data[4])}\n"
                f"📊 {row_data[5]} hari kerja\n"
                f"🗑️ Status: Dibatalkan")

        edit_telegram_message(chat_id, message_id, text)
        logger.info(f"Cuti dibatalkan: chat_id={chat_id} | {row_data[3]} - {row_data[4]}")

    except Exception as e:
        logger.exception(f"Error eksekusi_batalkan_cuti: {e}")
        edit_telegram_message(chat_id, message_id, f"❌ Gagal membatalkan: {str(e)}")


# ============ STATUS CUTI ============
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
                alasan = row[7] if len(row) > 7 else "-"

                if status == "Disetujui":
                    emoji = "✅"
                elif status == "Ditolak":
                    emoji = "❌"
                elif status == "Dibatalkan":
                    emoji = "🗑️"
                else:
                    emoji = "⏳"

                pesan += f"{emoji} *{status}*\n"
                pesan += f"📅 {format_tanggal(row[3])} \u2192 {format_tanggal(row[4])}\n"
                pesan += f"📊 {row[5]} hari kerja"
                if alasan and alasan != "-":
                    pesan += f" | 📝 {alasan}"
                pesan += "\n\n"

        return pesan if ada else "📋 Belum ada pengajuan cuti."

    except Exception as e:
        logger.error(f"Error status cuti: {e}")
        return "❌ Terjadi kesalahan saat mengecek status cuti."


# ============ PROCESS INTENT ============
def process_intent(chat_id, intent, params, fulfillment, original_text=""):
    karyawan = get_karyawan(chat_id)

    if not karyawan:
        send_telegram(chat_id, f"❌ Data karyawan tidak ditemukan.\nTelegram ID Anda: {chat_id}")
        return

    logger.info(f"Intent: {intent} | chat_id: {chat_id} | params: {params}")

    if intent == "cek_saldo_cuti":
        send_telegram(chat_id, f"👋 Halo {karyawan['nama']}!\n\n📊 *Sisa cuti Anda: {karyawan['sisa_cuti']} hari*")

    elif intent == "ajukan_cuti":
        mulai = params.get("tanggal_mulai") or params.get("date") or params.get("startDate")
        selesai = params.get("tanggal_selesai") or params.get("date-range") or params.get("endDate")

        if not mulai or not selesai:
            mulai, selesai = extract_two_dates(original_text)
            logger.debug(f"Extracted from text: mulai={mulai}, selesai={selesai}")

        proses_ajukan_cuti(chat_id, karyawan, mulai, selesai)

    elif intent in ["cek_status_cuti", "riwayat_cuti"]:
        send_telegram(chat_id, proses_status_cuti(chat_id))

    elif intent == "batalkan_cuti":
        proses_batalkan_cuti(chat_id)

    elif intent == "info_profil":
        send_telegram(chat_id,
            f"👤 *Profil Karyawan*\n\n"
            f"Nama: {karyawan['nama']}\n"
            f"Jabatan: {karyawan['jabatan']}\n"
            f"Divisi: {karyawan['divisi']}\n"
            f"Atasan: {karyawan['atasan']}\n"
            f"Sisa Cuti: {karyawan['sisa_cuti']} hari")

    else:
        send_telegram(chat_id, fulfillment or "❓ Maaf, saya tidak mengerti.\n\nKetik *bantuan* untuk melihat perintah yang tersedia.")


# ============ CALLBACK QUERY HANDLER ============
def handle_callback(data):
    """Handle inline keyboard button presses"""
    callback_query = data["callback_query"]
    callback_id = callback_query["id"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    callback_data = callback_query["data"]

    logger.info(f"Callback: {callback_data} | chat_id: {chat_id}")

    # Alasan cuti dipilih
    if callback_data.startswith("alasan_"):
        alasan_key = callback_data.replace("alasan_", "")
        answer_callback(callback_id, f"Alasan: {ALASAN_CUTI.get(alasan_key, 'Lainnya')}")
        konfirmasi_final(chat_id, message_id, alasan_key)

    # Konfirmasi final
    elif callback_data == "konfirmasi_ya":
        answer_callback(callback_id, "Menyimpan pengajuan...")
        simpan_cuti(chat_id, message_id)

    elif callback_data == "konfirmasi_tidak":
        answer_callback(callback_id, "Pengajuan dibatalkan")
        pending_cuti.pop(chat_id, None)
        edit_telegram_message(chat_id, message_id, "❌ Pengajuan cuti dibatalkan.\n\nAnda bisa mengajukan cuti kapan saja.")

    # Batal pengajuan (dari menu alasan)
    elif callback_data == "batal_pengajuan":
        answer_callback(callback_id, "Dibatalkan")
        pending_cuti.pop(chat_id, None)
        edit_telegram_message(chat_id, message_id, "❌ Pengajuan cuti dibatalkan.\n\nAnda bisa mengajukan cuti kapan saja.")

    # Batalkan cuti yang sudah diajukan
    elif callback_data.startswith("batalkan_"):
        row_index = int(callback_data.replace("batalkan_", ""))
        answer_callback(callback_id, "Membatalkan cuti...")
        eksekusi_batalkan_cuti(chat_id, message_id, row_index)

    # Kembali dari menu batalkan
    elif callback_data == "batal_menu":
        answer_callback(callback_id)
        edit_telegram_message(chat_id, message_id, "👌 Oke, tidak jadi membatalkan cuti.")

    else:
        answer_callback(callback_id, "Perintah tidak dikenali")


# ============ WEBHOOK ============
@app.route("/", methods=["GET"])
def index():
    return "Bot Cuti Karyawan dengan Dialogflow - Aktif"


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        # Handle callback query (inline keyboard button press)
        if data.get("callback_query"):
            handle_callback(data)
            return "ok", 200

        # Handle regular message
        if not data.get("message") or not data["message"].get("text"):
            return "ok", 200

        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]

        logger.info(f"Message from {chat_id}: {text[:50]}")

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
                    f"• Batalkan cuti: *batalkan cuti*\n"
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
                "4️⃣ *Batalkan Cuti*\n"
                "• `batalkan cuti`\n"
                "• `cancel cuti`\n\n"
                "5️⃣ *Lihat Profil*\n"
                "• `profil saya`\n"
                "• `info saya`"
            )
            return "ok", 200

        # Handle perintah batalkan cuti langsung (tanpa Dialogflow)
        if text.lower() in ["batalkan cuti", "cancel cuti", "batal cuti", "/batalkan"]:
            proses_batalkan_cuti(chat_id)
            return "ok", 200

        intent, params, fulfillment = detect_intent(chat_id, text)
        process_intent(chat_id, intent, params, fulfillment, text)

        return "ok", 200

    except Exception as e:
        logger.exception("Error di webhook")
        return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
