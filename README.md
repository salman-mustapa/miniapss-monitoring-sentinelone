# SentinelOne Monitor v2.0

A comprehensive security monitoring system that integrates with SentinelOne API to provide real-time threat detection, multi-channel notifications, and advanced management capabilities.

## Features

### 🛡️ Core Security Monitoring
- **Real-time SentinelOne API Integration**: Continuous polling for threats and security events
- **Webhook Alert Receiver**: Direct integration with SentinelOne webhooks at `/send/alert`
- **Event Backup & Archiving**: Automatic backup of events and alerts to JSONL files
- **Advanced Threat Analysis**: Comprehensive threat data processing and visualization

### 🔔 Multi-Channel Notifications
- **Telegram Bot Integration**: Send alerts via Telegram with bot token and chat ID
- **Microsoft Teams Integration**: Webhook-based notifications to Teams channels
- **WhatsApp Gateway**: Integration with WhatsApp bridge for messaging
- **Connection Testing**: Built-in connection testing for all notification channels

### 🎛️ Web Dashboard
- **Unified Interface**: Single-page application with tabbed interface
- **Hacker-Style UI**: Dark theme with terminal aesthetics and green/cyan accents
- **Real-time Logs**: Expandable log viewer with search and filtering
- **File Management**: Browse and download backup files organized by folders
- **Configuration Management**: Web-based configuration for all system components

### ⚙️ Advanced Configuration
- **SentinelOne Advanced Features**: Dedicated page for API endpoint testing
- **Polling Configuration**: Customizable polling intervals and parameters
- **Backup Management**: Manual and automated backup execution
- **Endpoint Management**: SentinelOne endpoint configuration and testing

## Installation

### Prerequisites
- Python 3.8+
- SentinelOne API access
- Network connectivity for notifications (Telegram, Teams, WhatsApp)

### Setup
1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd miniapps-monitoring
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run initial setup**:
   ```bash
   python run.py --setup
   ```
   This will create the initial `config/config.json` file with default settings.

## Usage

### Command Line Options

```bash
# Start web dashboard (recommended)
python run.py --web

# Run interactive setup wizard
python run.py --setup

# Start polling service only
python run.py --polling

# Run backup service only
python run.py --backup
```

### Web Dashboard

1. **Start the web server**:
   ```bash
   python run.py --web
   ```

2. **Access the dashboard**:
   - Open browser to `http://localhost:5000` (or configured port)
   - Default PIN: `1234` (configurable in setup)

3. **Dashboard Tabs**:
   - **Dashboard**: System overview, logs, and file management
   - **Notifications**: Configure Telegram, Teams, and WhatsApp
   - **WhatsApp**: Advanced WhatsApp gateway management
   - **Configuration**: System settings and SentinelOne API configuration

### Advanced Features

Access advanced SentinelOne features at `/sentinelone-advanced`:
- **Polling Configuration**: Set up automated threat polling
- **Backup Management**: Configure and execute backups
- **Endpoint Testing**: Test SentinelOne API endpoints
- **Data Visualization**: View threat data and statistics

## Configuration

### Main Configuration File: `config/config.json`

```json
{
  "sentinelone": {
    "base_url": "https://your-instance.sentinelone.net",
    "api_token": "your-api-token",
    "polling_interval": 300
  },
  "web": {
    "host": "0.0.0.0",
    "port": 5000,
    "pin": "1234"
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "bot_token": "your-bot-token",
      "chat_id": "your-chat-id"
    },
    "teams": {
      "enabled": true,
      "webhook_url": "your-teams-webhook-url"
    },
    "whatsapp": {
      "enabled": true,
      "session_name": "gateway",
      "gateway_url": "http://localhost:5013"
    }
  },
  "backup": {
    "enabled": true,
    "interval": 3600,
    "retention_days": 30
  }
}
```

### Notification Setup

#### Telegram
1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Get the bot token
3. Get your chat ID (send a message to the bot and check `/getUpdates`)
4. Configure in the Notifications tab

#### Microsoft Teams
1. Create an Incoming Webhook in your Teams channel
2. Copy the webhook URL
3. Configure in the Notifications tab

#### WhatsApp
1. Set up a WhatsApp gateway (e.g., using whatsapp-web.js)
2. Configure the gateway URL (default: `http://localhost:5013`)
3. Configure session name and recipients

## File Structure

```
miniapps-monitoring/
├── config/
│   └── config.json          # Main configuration file
├── logs/
│   ├── app.log             # Application logs
│   ├── error.log           # Error logs
│   └── success.log         # Success logs
├── notifier/
│   ├── telegram.py         # Telegram integration
│   ├── teams.py           # Teams integration
│   └── whatsapp.py        # WhatsApp integration
├── src/
│   ├── backup.py          # Backup functionality
│   ├── config.py          # Configuration management
│   ├── logger.py          # Custom logging
│   ├── main.py            # Application startup
│   ├── sentinel_api.py    # SentinelOne API wrapper
│   └── webapp.py          # FastAPI web application
├── storage/
│   ├── alerts/            # Alert backups
│   └── events/            # Event backups
├── templates/
│   ├── index.html         # Main dashboard
│   ├── login.html         # Login page
│   ├── sentinelone-advanced.html  # Advanced features
│   └── whatsapp.html      # WhatsApp management
├── run.py                 # Main entry point
└── requirements.txt       # Python dependencies
```

## API Endpoints

### Web Dashboard
- `GET /` - Main dashboard
- `GET /login` - Login page
- `POST /login` - Authentication
- `GET /sentinelone-advanced` - Advanced features page

### Configuration API
- `GET /api/config` - Get current configuration
- `POST /api/config/save` - Save configuration
- `POST /api/test-connection` - Test service connections

### SentinelOne API
- `GET /api/sentinel/threats` - Get threats
- `GET /api/sentinel/agents` - Get agents
- `POST /api/sentinel/test` - Test API connection

### Alert Receiver
- `POST /send/alert` - Webhook endpoint for SentinelOne alerts

### File Management
- `GET /api/files/list` - List backup files
- `GET /api/files/download` - Download backup files

## Logging

The system uses a comprehensive logging system with multiple log levels:

- **Application Logs** (`logs/app.log`): General application events
- **Error Logs** (`logs/error.log`): Error events and exceptions
- **Success Logs** (`logs/success.log`): Successful operations
- **Custom Log Levels**: INFO, WARNING, ERROR, SUCCESS

## Security Considerations

1. **API Tokens**: Store SentinelOne API tokens securely
2. **Web PIN**: Change default PIN in production
3. **Network Security**: Restrict access to the web dashboard
4. **Webhook Security**: Validate incoming webhook requests
5. **File Permissions**: Ensure proper file system permissions

## Troubleshooting

### Common Issues

1. **Connection Errors**:
   - Verify SentinelOne API credentials
   - Check network connectivity
   - Validate webhook URLs

2. **Notification Failures**:
   - Test individual notification channels
   - Verify bot tokens and chat IDs
   - Check webhook configurations

3. **Web Dashboard Issues**:
   - Check port availability
   - Verify PIN configuration
   - Review application logs

### Log Analysis
Check the logs directory for detailed error information:
```bash
tail -f logs/app.log      # Application logs
tail -f logs/error.log    # Error logs
tail -f logs/success.log  # Success logs
```

## Development

### Running in Development Mode
```bash
# Install development dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 5000
```

### Adding New Features
1. Update the appropriate module in `src/`
2. Add new API endpoints in `src/webapp.py`
3. Update the web interface in `templates/`
4. Add configuration options to `config.json`

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For support and questions:
1. Check the logs for error details
2. Verify configuration settings
3. Test individual components
4. Review the troubleshooting section

## Version History

### v2.0
- Unified web dashboard with tabbed interface
- Advanced SentinelOne integration
- Multi-channel notification system
- Comprehensive logging and monitoring
- File management and backup system
- Hacker-style UI with terminal aesthetics
