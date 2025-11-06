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
git clone https://github.com/bagasta/new-mcp-server.git ~/new-mcp-server
cd ~/new-mcp-server
```

If you already have the repository on the machine, move it into a folder named `new-mcp-server` and treat that directory as the project root for the rest of this guide.

## 2. Create the Virtual Environment
Run the following from the project root (`~/new-mcp-server`):

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r playground/backend/requirements.txt   # Only if you plan to run the playground backend
deactivate
```

These requirements install `fastmcp`, `fastapi`, `uvicorn`, `httpx`, PDF/DOCX generators, and optional PostgreSQL (`psycopg[binary]`) support used by the reminder service.

## 3. Configure Environment Variables
All transports load environment variables from `~/new-mcp-server/.env`. Populate it with the values required for the tools you intend to expose:

```bash
cat <<'EOF' > ~/new-mcp-server/.env
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
- If you do not provide `DATABASE_URL`, the server creates `data/reminders.db` (SQLite) relative to `~/new-mcp-server`.

## 4. Storage Backends
- **SQLite (default):** no extra work. Ensure `~/new-mcp-server/data` exists and is writable. The file is created on first reminder.
```bash
mkdir -p ~/new-mcp-server/data
```
- **PostgreSQL:** set `DATABASE_URL`. `psycopg[binary]` ships with the project; ensure the database exists and the user has permission to create tables.

## 5. Manual SSE Transport Test
Before wiring systemd, verify the server starts and responds:
```bash
cd ~/new-mcp-server
. .venv/bin/activate
uvicorn src.transports.sse:app --host 0.0.0.0 --port 8190
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
User=bagas  # Ganti dengan user yang menjalankan proyek ini
Group=bagas
WorkingDirectory=/home/bagas/new-mcp-server   # Ganti dengan path absolut proyek
EnvironmentFile=/home/bagas/new-mcp-server/.env
Environment=PYTHONPATH=/home/bagas/new-mcp-server
ExecStart=/home/bagas/new-mcp-server/.venv/bin/python -m src.transports.sse
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Ganti `bagas` dan `/home/bagas/new-mcp-server` dengan nama user dan path absolut proyek milikmu.

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
- **REST transport:** add another unit that runs `~/new-mcp-server/.venv/bin/python -m src.transports.api` (port 8002). The playground backend and CLI use this endpoint.
- **Playground backend:** `~/new-mcp-server/.venv/bin/python -m playground.backend.main` (port 8003). Requires `MCP_API_BASE_URL`, `MCP_SSE_URL`, and `OPENAI_API_KEY`.
- **Frontend:** the static files in `playground/frontend/` can be served by any web server (`python -m http.server 8080`, nginx, etc.).
- **Integration test harness:** `python scripts/run_full_test.py` spins up a local webhook catcher and exercises all transports/endpoints. Run it from the project root with the same virtualenv to validate deployments.

## 9. Routine Maintenance
- Pull updates and reinstall dependencies:
```bash
cd ~/new-mcp-server
git fetch --all
git checkout main
git pull
. .venv/bin/activate
pip install -r requirements.txt
pip install -r playground/backend/requirements.txt
deactivate
sudo systemctl restart mcp-sse
```
- Monitor webhook failures in logs; the reminder dispatcher retries with exponential backoff using the `REMINDER_RETRY_*` settings.
- Back up the SQLite file (`~/new-mcp-server/data/reminders.db`) or rely on PostgreSQL backups if using that backend.

## 10. Troubleshooting
- **Port already in use:** adjust the systemd unit to use a different port, then update clients (`MCP_SSE_URL`).
- **Webhook errors:** verify `REMINDER_WEBHOOK_URL`, `MESSAGE_WEBHOOK_URL`, and `DEEP_RESEARCH_WEBHOOK_URL`. The server stops dispatching until it can reach the target.
- **Missing API keys:** `web_search` raises `ValueError` if `SERPER_API_KEY` is absent. LangChain `/calculate` returns HTTP 503 if `OPENAI_API_KEY` is missing.
- **PDF font missing:** `assets/fonts/NotoSans-Regular.ttf` must exist; the server raises `FileNotFoundError` during PDF generation otherwise. Keep `assets/` alongside the code.
- **LangChain SSE connectivity:** ensure `curl http://localhost:8190/sse` works from the playground backend host and that firewalls allow inbound traffic.

With these steps, the SSE transport runs as a managed service, reminders are persisted, and the deployment is ready for LangChain agents or other MCP-compatible clients.
