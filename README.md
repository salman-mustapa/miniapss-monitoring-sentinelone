# Mini Apps Monitoring SentinelOne

## 🛠️ Teknologi yang Digunakan

- `Python 3.10+` → bahasa utama.

- `Flask / FastAPI` → web dashboard + webhook receiver.

- `OpenAI API` → untuk AI summary & mitigasi (dengan masking data).

- `JSON file` → backup event harian & config.

- `Logging (Python logging)` → simpan error/success.

- `Requests / httpx` → komunikasi dengan SentinelOne API & webhook (Telegram, Teams, WA).

- `WhatsApp (self-hosted via WA Web protocol / Baileys Python binding)` → kirim pesan ke grup.

- `Telegram Bot API` → notifikasi cepat.

- `Microsoft Teams Webhook` → untuk tim manajemen.

---
## 📌 Rangkuman Sistem

-  Config Management → semua setting (Telegram, WA, Teams, AI, SentinelOne) disimpan di config.json.

- `Event Collection`

- `Polling SentinelOne API (per menit).`

- `Webhook dari SentinelOne (langsung push ke sistem kita).`

- `Backup Engine` → event disimpan di storage/events/YYYY-MM-DD.json (supaya aman setelah 14 hari data dihapus di SentinelOne).

- `Sanitizer` → masking data sensitif (user, hostname, IP, path).

- `AI Processor` → ringkas + beri langkah mitigasi (pakai OpenAI API).

- `Notifier` → kirim ke Telegram, Teams, WhatsApp dengan format berbeda.

- `Logger` → error & success log.

- `Web Dashboard` → lihat status, logs, config, trigger manual.

---
## 🔄 Flow Sistem

```
SentinelOne (event / webhook)
        ↓
   [Backup Engine] → simpan raw event JSON
        ↓
   [Sanitizer] → masking data sensitif
        ↓
   [AI Processor] → summary + mitigasi
        ↓
   [Notifier] → Telegram / WhatsApp / Teams
        ↓
   [Logs] → error.log & success.log
        ↓
   [Web Dashboard] → monitoring & trigger
```
---
## 📂 Struktur Folder

```
sentinel-monitor/
├── config/
│   └── config.json             # penyimpanan config user (API key, token, dsb.)
├── logs/                       # Penyimpanan logs (all logs, error log & success log)
│   ├── all.log
│   ├── error.log
│   └── success.log
├── notifier/
│   ├── __init__.py
│   ├── teams.py                # class TeamsNotifier
│   ├── telegram.py             # class TelegramNotifier
│   └── whatsapp/
│       ├── __init__.py
│       ├── cloud.py            # WA API-based (Fonnte/Meta/Twilio)
│       └── bridge.py           # WA Node.js bridge (QR based)
├── storage/
│   └── events/
│       └── detections_20250906_233355.json
├── src/
│   ├── __init__.py
│   ├── backup.py               # modul backup rutin
│   ├── config.py               # loader & handler config.json
│   ├── logger.py               # setup logging (all/error/success)
│   ├── main.py                 # core app entry (dipanggil dari run.py)
│   ├── sentinel_api.py         # wrapper API SentinelOne (get_detection, get_activities, dll.)
│   └── webapp.py               # FastAPI app (HTTP endpoint /send/alert)
├── run.py                      # ⬅️ entry utama (jalankan webapp + CLI setup)
├── setup_config.py             # (optional, bisa dipanggil via run.py)
├── requirements.txt
└── README.md
```
---

## Menjalankan Program
#### 1. setup configurasi
```bash
python3 run.py --setup
```

#### 2. jalankan webserver untuk menerima triger dari sentinel one
```bash
python3 run.py
```
- untuk menggunakannya tinggal ke configurasi webhook sentinelone
- tambahkan url 
     ```
     http://domainkamu/send/alert
     ```

- untuk response pilih full threat ajag

### Arsitektur Sederhana

```
+--------------------+       +-------------------+
|  SentinelOne       |       | WhatsApp Gateway  |
|  (alerts/events)   |       | (Node.js service) |
+---------+----------+       +----------+--------+
          |                             |
          v                             |
+---------+----------+   REST API       |
| sentinel-monitor   | <----------------+
| (Python, Flask)    | 
| - Webhook listener |
| - Polling engine   |
| - Notifiers        |
| - Dashboard (UI)   |
+--------------------+
          |
          v
   +-------------+
   | Dashboard   |
   | (Flask UI)  |
   +-------------+

```