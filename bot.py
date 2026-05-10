import os
import json
import requests
import re
import gspread
from flask import Flask, request
from google.oauth2.service_account import Credentials
from datetime import datetime

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


def extract_tanggal(text):
    pattern_dmy = r'\d{1,2}[-/]\d{1,2}[-/]\d{4}'
    pattern_iso = r'\d{4}-\d{2}-\d{2}'
    
    dates_dmy = re.findall(pattern_dmy, text)
    dates_iso = re.findall(pattern_iso, text)
    
    def parse_tanggal(date_str):
        # Coba D-M-YYYY dulu
        try:
            return datetime.strptime(date_str, "%d-%m-%Y").strftime("%Y-%m-%d")
        except:
            pass
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except:
            pass
        # Terakhir baru ISO
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        except:
            pass
        return None

    # Prioritaskan DMY dulu baru ISO
    all_dates = dates_dmy + dates_iso
    parsed = [parse_tanggal(d) for d in all_dates if parse_tanggal(d)]
    
    if len(parsed) >= 2:
        return parsed[0], parsed[1]
    elif len(parsed) == 1:
        return parsed[0], None
    return None, None

def get_karyawan(chat_id):
    try:
        sheet = get_sheet("Karyawan")
        data = sheet.get_all_values()
        chat_id_str = str(chat_id)
        print(f"Total rows: {len(data)}")
        print(f"Looking for chat_id: {chat_id_str}")
        for i, row in enumerate(data[1:]):
            print(f"Row {i}: {row}")
            if len(row) >= 6 and str(row[5]).strip() == chat_id_str:
                return {
                    "nama": row[2],
                    "jabatan": row[3],
                    "divisi": row[4],
                    "sisa_cuti": int(row[8]) if row[8] else 0,
                    "atasan": row[9] if len(row) > 9 else "-"
                }
        print("Karyawan tidak ditemukan")
        return None
    except Exception as e:
        import traceback
        print(f"Error get_karyawan: {e}")
        print(traceback.format_exc())
        return None

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
        print(f"Dialogflow result: {result}")

        intent = result["queryResult"]["intent"]["displayName"]
        params = result["queryResult"].get("parameters", {})
        fulfillment = result["queryResult"].get("fulfillmentText", "")
        return intent, params, fulfillment

    except Exception as e:
        import traceback
        print(f"Error detect_intent: {e}")
        print(traceback.format_exc())
        return "Default Fallback Intent", {}, ""

# ============ TELEGRAM ============
def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

# ============ PROSES INTENT ============
def format_tanggal(date_str):
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", ""))
        return dt.strftime("%d %B %Y")
    except:
        return date_str
        
def proses_ajukan_cuti(chat_id, karyawan, mulai, selesai):
    try:
        if not mulai or not selesai:
            return ("Mohon berikan tanggal mulai dan selesai cuti.\n\n"
                    "Contoh: saya mau cuti dari 12-01-2026 sampai 15-01-2026")

        if isinstance(mulai, list): mulai = mulai[0]
        if isinstance(selesai, list): selesai = selesai[0]

        # Ambil hanya bagian tanggal YYYY-MM-DD
        mulai_str = str(mulai)[:10]
        selesai_str = str(selesai)[:10]

        tgl_mulai = datetime.strptime(mulai_str, "%Y-%m-%d")
        tgl_selesai = datetime.strptime(selesai_str, "%Y-%m-%d")

        if tgl_selesai < tgl_mulai:
            return "Tanggal selesai harus setelah tanggal mulai."

        jumlah_hari = (tgl_selesai - tgl_mulai).days + 1

        if jumlah_hari > karyawan["sisa_cuti"]:
            return f"Maaf, sisa cuti Anda hanya {karyawan['sisa_cuti']} hari, tidak cukup untuk {jumlah_hari} hari."

        sheet = get_sheet("PengajuanCuti")
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(chat_id),
            karyawan["nama"],
            tgl_mulai.strftime("%Y-%m-%d"),
            tgl_selesai.strftime("%Y-%m-%d"),
            jumlah_hari,
            "Menunggu"
        ])

        return (f"✅ Pengajuan cuti berhasil!\n\n"
                f"Nama: {karyawan['nama']}\n"
                f"Mulai: {tgl_mulai.strftime('%d %B %Y')}\n"
                f"Selesai: {tgl_selesai.strftime('%d %B %Y')}\n"
                f"Jumlah: {jumlah_hari} hari\n"
                f"Status: Menunggu Persetujuan")

    except Exception as e:
        import traceback
        print(f"Error ajukan cuti: {e}")
        print(traceback.format_exc())
        return "Terjadi kesalahan saat mengajukan cuti."

def proses_status_cuti(chat_id):
    try:
        sheet = get_sheet("PengajuanCuti")
        data = sheet.get_all_values()
        pesan = "📋 Status Pengajuan Cuti\n\n"
        ada = False
        count = 0

        for row in reversed(data[1:]):
            if count >= 5:
                break
            if len(row) >= 7 and str(row[1]) == str(chat_id):
                ada = True
                count += 1
                status = row[6] or "Menunggu"
                emoji = "✅" if status == "Disetujui" else ("❌" if status == "Ditolak" else "⏳")
                pesan += f"{emoji} {status}\n"
                pesan += f"📅 {row[3]} → {row[4]}\n"
                pesan += f"📊 {row[5]} hari\n\n"

        return pesan if ada else "Belum ada pengajuan cuti."

    except Exception as e:
        print(f"Error status cuti: {e}")
        return "Terjadi kesalahan saat mengecek status cuti."

def process_intent(chat_id, intent, params, fulfillment):
    karyawan = get_karyawan(chat_id)

    if not karyawan:
        return "Data karyawan tidak ditemukan. Hubungi admin."

    if intent == "cek_saldo_cuti":
        return f"👋 Halo {karyawan['nama']}\n\n📊 Sisa cuti Anda: {karyawan['sisa_cuti']} hari"

    elif intent == "ajukan_cuti":
        return proses_ajukan_cuti(chat_id, karyawan, params.get("tanggal_mulai"), params.get("tanggal_selesai"))

    elif intent in ["cek_status_cuti", "riwayat_cuti"]:
        return proses_status_cuti(chat_id)

    elif intent == "info_profil":
        return (f"👤 Profil Karyawan\n\n"
                f"Nama: {karyawan['nama']}\n"
                f"Jabatan: {karyawan['jabatan']}\n"
                f"Divisi: {karyawan['divisi']}\n"
                f"Atasan: {karyawan['atasan']}\n"
                f"Sisa Cuti: {karyawan['sisa_cuti']} hari")

    else:
        return fulfillment or "Maaf, saya tidak mengerti. Coba ketik 'sisa cuti saya' atau 'profil saya'."

# ============ WEBHOOK ============
@app.route("/", methods=["GET"])
def index():
    return "Bot Cuti Karyawan Aktif"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print(f"Data masuk: {data}")

        if not data.get("message") or not data["message"].get("text"):
            return "ok", 200

        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]

        if text == "/start":
            karyawan = get_karyawan(chat_id)
            if karyawan:
                send_telegram(chat_id,
                    f"Halo {karyawan['nama']}! 👋\n\n"
                    f"Selamat datang di Bot Cuti Karyawan.\n"
                    f"Sisa cuti Anda: {karyawan['sisa_cuti']} hari\n\n"
                    f"Ketik pesan seperti:\n"
                    f"- sisa cuti saya\n"
                    f"- saya mau cuti dari 12-01-2026 sampai 15-01-2026\n"
                    f"- status cuti saya\n"
                    f"- profil saya"
                )
            else:
                send_telegram(chat_id, f"Data karyawan tidak ditemukan.\nTelegram ID Anda: {chat_id}")
            return "ok", 200

        intent, params, fulfillment = detect_intent(chat_id, text)
        print(f"Intent: {intent} | Params: {params}")

        # Untuk ajukan_cuti, ambil tanggal dari teks langsung
        if intent == "ajukan_cuti":
            mulai, selesai = extract_tanggal(text)
            print(f"Tanggal extracted: mulai={mulai}, selesai={selesai}")
            params["tanggal_mulai"] = mulai if mulai else ""
            params["tanggal_selesai"] = selesai if selesai else ""

        response_text = process_intent(chat_id, intent, params, fulfillment)
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
