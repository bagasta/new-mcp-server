# How to Deploy the MCP Calculator Server

This guide walks through deploying the MCP Calculator Server on a Linux host, focusing on the Server-Sent Events (SSE) transport that powers LangChain integrations. The same environment can later host the REST, STDIO, or streamable HTTP transports if needed.

## 0. Prerequisites
- Ubuntu 22.04 (or similar), SSH access, and sudo privileges.
- Python 3.10+ with `python3-venv` and build tools (`sudo apt install python3.10 python3-venv build-essential`).
- An outbound internet connection for `pip` and any webhooks or Serper API calls.
- TLS certificates and reverse proxy are optional; the server binds directly to `0.0.0.0` on port `8190` by default.

| Component | Default Port | Process |
|-----------|--------------|---------|
| SSE transport | 8190 | `uvicorn` serving `src.transports.sse:app` |
| REST transport (optional) | 8002 | `src.transports.api.run_api` |
| Playground backend (optional) | 8003 | `playground/backend/main.py` |

## 1. Prepare the Server
```bash
sudo adduser --system --group --home /opt/mcp mcp
sudo mkdir -p /opt/mcp && sudo chown -R mcp:mcp /opt/mcp
sudo -u mcp git clone https://github.com/YOUR_ORG/mcp-calculator.git /opt/mcp
```

If you already have the repository on the machine, copy it into `/opt/mcp` (or any directory owned by the service user) and adjust the rest of the paths accordingly.

## 2. Create the Virtual Environment
```bash
sudo -u mcp python3 -m venv /opt/mcp/.venv
sudo -u mcp /opt/mcp/.venv/bin/pip install --upgrade pip
sudo -u mcp /opt/mcp/.venv/bin/pip install -r /opt/mcp/requirements.txt
sudo -u mcp /opt/mcp/.venv/bin/pip install -r /opt/mcp/playground/backend/requirements.txt  # Only if you plan to run the playground backend
```

These requirements install `fastmcp`, `fastapi`, `uvicorn`, `httpx`, PDF/DOCX generators, and optional PostgreSQL (`psycopg[binary]`) support used by the reminder service.

## 3. Configure Environment Variables
All transports load environment variables from `/opt/mcp/.env`. Populate it with the values required for the tools you intend to expose:

```bash
sudo -u mcp tee /opt/mcp/.env >/dev/null <<'EOF'
# Core MCP server
SERPER_API_KEY=""                # Required for the web_search tool
REMINDER_WEBHOOK_URL=""          # Required to receive scheduled reminders
MESSAGE_WEBHOOK_URL=""           # Optional; defaults to REMINDER_WEBHOOK_URL
DEEP_RESEARCH_WEBHOOK_URL=""     # Optional; defaults to MESSAGE_WEBHOOK_URL

# Storage (choose one backend)
#DATABASE_URL="postgresql://user:pass@host:5432/dbname"
REMINDER_DB_PATH="data/reminders.db"

# Reminder tuning (defaults shown)
REMINDER_POLL_INTERVAL_SECONDS=30
REMINDER_DISPATCH_BATCH_SIZE=10
REMINDER_HTTP_TIMEOUT_SECONDS=10
REMINDER_RETRY_BASE_SECONDS=30
REMINDER_RETRY_MAX_SECONDS=600
REMINDER_MIN_LEAD_SECONDS=5

# Playground / LangChain (optional components)
MCP_API_BASE_URL="http://localhost:8002"
MCP_SSE_URL="http://localhost:8190/sse"
OPENAI_API_KEY=""
EOF
```

Notes:
- The server reads `.env` automatically using `python-dotenv`. If that package is missing, it falls back to a built-in parser.
- Leave comment lines or remove unused keys entirely; empty strings will cause runtime validation errors for webhook URLs.
- If you do not provide `DATABASE_URL`, the server creates `data/reminders.db` (SQLite) relative to `/opt/mcp`.

## 4. Storage Backends
- **SQLite (default):** no extra work. Ensure `/opt/mcp/data` is writable by the service user. The file is created on first reminder.
  ```bash
  sudo -u mcp mkdir -p /opt/mcp/data
  ```
- **PostgreSQL:** set `DATABASE_URL`. `psycopg[binary]` ships with the project; ensure the database exists and the user has permission to create tables.

## 5. Manual SSE Transport Test
Before wiring systemd, verify the server starts and responds:
```bash
sudo -u mcp bash -lc '
  cd /opt/mcp
  source .venv/bin/activate
  uvicorn src.transports.sse:app --host 0.0.0.0 --port 8190
'
```

Open another terminal (or use `curl`) to confirm the endpoint streams events:
```bash
curl -i http://localhost:8190/sse
```
You should see `HTTP/1.1 200 OK` and the connection will remain open (press Ctrl+C to exit). Stop the uvicorn process once verified.

## 6. Keep the SSE Transport Running with systemd
Create `/etc/systemd/system/mcp-sse.service`:

```ini
[Unit]
Description=MCP Calculator SSE Transport
After=network.target

[Service]
Type=simple
User=mcp
Group=mcp
WorkingDirectory=/opt/mcp
EnvironmentFile=/opt/mcp/.env
Environment=PYTHONPATH=/opt/mcp
ExecStart=/opt/mcp/.venv/bin/python -m src.transports.sse
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Reload and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-sse
sudo systemctl status mcp-sse
```

`src.transports.sse.run_sse` binds to `0.0.0.0:8190`; edit `ExecStart` if you prefer a wrapper that calls `run_sse(host="127.0.0.1", port=9000)` or use `uvicorn src.transports.sse:app --port 9000`.

## 7. Verification Checklist
- `sudo ss -ltnp | grep 8190` shows the process listening.
- `journalctl -u mcp-sse -f` streams logs (FastMCP tool registration, reminder dispatcher activity, webhook errors).
- Schedule a reminder via the REST API or LangChain agent and confirm the webhook receives payloads.

## 8. Optional Components
- **REST transport:** add another unit that runs `/opt/mcp/.venv/bin/python -m src.transports.api` (port 8002). The playground backend and CLI use this endpoint.
- **Playground backend:** `/opt/mcp/.venv/bin/python -m playground.backend.main` (port 8003). Requires `MCP_API_BASE_URL`, `MCP_SSE_URL`, and `OPENAI_API_KEY`.
- **Frontend:** the static files in `playground/frontend/` can be served by any web server (`python -m http.server 8080`, nginx, etc.).
- **Integration test harness:** `python scripts/run_full_test.py` spins up a local webhook catcher and exercises all transports/endpoints. Run it from the project root with the same virtualenv to validate deployments.

## 9. Routine Maintenance
- Pull updates and reinstall dependencies:
  ```bash
  sudo -u mcp bash -lc '
    cd /opt/mcp
    git fetch --all
    git checkout main
    git pull
    source .venv/bin/activate
    pip install -r requirements.txt
    pip install -r playground/backend/requirements.txt
  '
  sudo systemctl restart mcp-sse
  ```
- Monitor webhook failures in logs; the reminder dispatcher retries with exponential backoff using the `REMINDER_RETRY_*` settings.
- Back up the SQLite file (`/opt/mcp/data/reminders.db`) or rely on PostgreSQL backups if using that backend.

## 10. Troubleshooting
- **Port already in use:** adjust the systemd unit to use a different port, then update clients (`MCP_SSE_URL`).
- **Webhook errors:** verify `REMINDER_WEBHOOK_URL`, `MESSAGE_WEBHOOK_URL`, and `DEEP_RESEARCH_WEBHOOK_URL`. The server stops dispatching until it can reach the target.
- **Missing API keys:** `web_search` raises `ValueError` if `SERPER_API_KEY` is absent. LangChain `/calculate` returns HTTP 503 if `OPENAI_API_KEY` is missing.
- **PDF font missing:** `assets/fonts/NotoSans-Regular.ttf` must exist; the server raises `FileNotFoundError` during PDF generation otherwise. Keep `assets/` alongside the code.
- **LangChain SSE connectivity:** ensure `curl http://localhost:8190/sse` works from the playground backend host and that firewalls allow inbound traffic.

With these steps, the SSE transport runs as a managed service, reminders are persisted, and the deployment is ready for LangChain agents or other MCP-compatible clients.
