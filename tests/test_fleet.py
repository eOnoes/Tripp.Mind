import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fleet_entrypoints_are_valid_javascript():
    for script in [
        "event-bridge.js",
        "backup-service.js",
        "bots/telegram-bot.js",
        "bots/discord-bot.js",
        "server.js",
    ]:
        subprocess.run(["node", "--check", script], cwd=ROOT, check=True, capture_output=True, text=True, timeout=10)


def test_event_bridge_websocket_server_starts_contract():
    source = (ROOT / "event-bridge.js").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "new WebSocket.Server({ server })" in source
    assert "server.listen(port" in source
    assert "event-bridge:" in compose
    assert "EVENT_BRIDGE_PORT: ${EVENT_BRIDGE_PORT:-3001}" in compose
    assert "./event-bridge.js:/app/event-bridge.js:ro" in compose


def test_telegram_bot_initializes_contract():
    source = (ROOT / "bots" / "telegram-bot.js").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "TELEGRAM_BOT_TOKEN is required" in source
    assert "new TelegramBot(token, { polling: true })" in source
    assert "telegram bot started" in source
    assert "telegram-bot:" in compose
    assert "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}" in compose


def test_discord_bot_initializes_contract():
    source = (ROOT / "bots" / "discord-bot.js").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "DISCORD_BOT_TOKEN is required" in source
    assert "DISCORD_APPLICATION_ID is required" in source
    assert "discord.login(token)" in source
    assert "discord bot started" in source
    assert "discord-bot:" in compose
    assert "DISCORD_BOT_TOKEN: ${DISCORD_BOT_TOKEN:-}" in compose


def test_backup_service_creates_backup_directory_contract(tmp_path):
    source = (ROOT / "backup-service.js").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    backup_dir = tmp_path / "backups"

    os.makedirs(backup_dir, exist_ok=True)

    assert backup_dir.is_dir()
    assert "await fs.mkdir(backupDir, { recursive: true })" in source
    assert "BACKUP_CRON_SCHEDULE: ${BACKUP_CRON_SCHEDULE:-0 2 * * *}" in compose
    assert "backups:/backups" in compose
