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

---
## Cara Penggunaan
# python-monitor (SentinelOne Monitor)

Ringkasan:
- Web dashboard: `python run.py --web` (baca `config/config.json` untuk host/port)
- Setup wizard: `python run.py --setup`
- Polling loop: `python run.py --polling` (requires valid SentinelOne config)
- Incoming webhook: POST JSON to `/send/alert` (FastAPI server) — saved to `storage/alerts/<date>/...`

## Important files
- `config/config.json` — semua konfigurasi (SentinelOne, channels, web, polling)
- `src/webapp.py` — FastAPI app (routes: `/`, `/login`, `/config`, `/whatsapp`, `/send/alert`)
- `src/config.py` — load_config() / save_config()
- `notifier/telegram.py` — notif via Telegram
- `run.py` — entrypoint

## Quick start
1. Run setup wizard if config missing:
`python run.py --setup` isi SentinelOne base_url, API token, channels, web host/port, dan PIN.

2. Start web dashboard:
`python run.py --web` buka `http://<host>:<port>/` -> login with PIN (set during setup).  
Edit WhatsApp config on `/whatsapp` and general settings on `/config`.

3. Hook SentinelOne webhook to:
`POST https://<your-monitor-host>/send/alert` The app saves the alert and will send Telegram notification if configured.

## Templates
Create folder `templates/` and add simple files:
- `login.html`, `index.html`, `config.html`, `whatsapp.html`.
(See examples in repository README or ask me to create them here.)

## WhatsApp Multi-Session Integration

### Features
- **Multiple Sessions**: Create and manage multiple WhatsApp sessions
- **Session-Aware Operations**: All WhatsApp operations support session selection
- **QR Code Display**: Visual QR code display for easy scanning
- **Session Status**: Real-time session status indicators
- **Conditional UI**: Smart UI flow based on session availability

### WhatsApp Gateway API Format

The system integrates with WhatsApp gateway using the following API format:

**Send Message**:
```bash
curl -X POST http://localhost:5013/api/kirim-pesan \
  -H "Content-Type: application/json" \
  -d '{"number":"120363220075343815@g.us","message":"Halo Group!","session":"testing"}'
```

**Get Logs**:
```bash
# All logs for a session
curl http://localhost:5013/api/logs?session=gateway

# Logs for specific target in session
curl http://localhost:5013/api/logs/6282154488769?session=gateway
```

### Session Management Workflow

1. **Initial Setup**: If no sessions exist, the UI shows configuration form
2. **Session Creation**: Auto-creates session after saving configuration
3. **Session Selection**: Select active session for operations
4. **QR Code Scanning**: Display QR as image for WhatsApp connection
5. **Message Sending**: Session-aware message dispatch

### Enhanced API Endpoints

- `GET /api/wa/sessions` - List all sessions with status
- `POST /api/wa/connect` - Create/connect session
- `GET /api/wa/qr?session=<name>` - Get QR code for session
- `GET /api/wa/groups?session=<name>` - List groups in session
- `GET /api/wa/fetch-groups?session=<name>` - Fetch groups from WhatsApp
- `POST /api/wa/send` - Send message (with session parameter)
- `GET /api/wa/logs?session=<name>` - Get logs for session
- `GET /api/wa/logs/<target>?session=<name>` - Get logs for specific target

### Configuration Fields
- `bridge_url`: WhatsApp gateway base URL
- `session_name`: Default session name
- `notify_number`: Phone number/group for notifications
- `notify_session`: Session to use for notifications

### Multi-Session Benefits
- **Isolation**: Separate WhatsApp accounts for different purposes
- **Reliability**: Backup sessions if primary session fails
- **Organization**: Different sessions for different teams/groups
- **Scalability**: Handle multiple WhatsApp integrations simultaneously

## Notes
- `config/config.json` **must not** be committed (keeps secrets).
- WhatsApp multi-session support requires external WhatsApp gateway service
- If you want backup scheduler or advanced polling orchestration (systemd/pm2), I can add examples.