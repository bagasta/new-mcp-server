# How to Use the MCP REST API

This guide shows how to call every MCP tool exposed by the REST transport.

## Prerequisites

1. Activate your virtual environment and install dependencies.
2. Start the REST transport:
   ```bash
   python -m src.transports.api
   ```
   By default the server listens on `http://localhost:8002`.
3. Ensure required environment variables are set (for example `SERPER_API_KEY`, `REMINDER_WEBHOOK_URL`, `MESSAGE_WEBHOOK_URL`).

If you run the examples from another host or port, replace `http://localhost:8002` accordingly.

Each request uses the same pattern:

```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "<tool name>",
    "arguments": { /* tool specific arguments */ }
  }'
```

The sections below provide concrete payloads for every tool.

---

## Calculator Tools

### add
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "add",
    "arguments": {"a": 3, "b": 9}
  }'
```

### subtract
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "subtract",
    "arguments": {"a": 12, "b": 5}
  }'
```

### multiply
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "multiply",
    "arguments": {"a": 6, "b": 7}
  }'
```

### divide
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "divide",
    "arguments": {"a": 22, "b": 7}
  }'
```

### power
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "power",
    "arguments": {"base": 2, "exponent": 8}
  }'
```

### sqrt
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "sqrt",
    "arguments": {"value": 144}
  }'
```

### factorial
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "factorial",
    "arguments": {"value": 6}
  }'
```

### percentage
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "percentage",
    "arguments": {"value": 250, "percent": 18}
  }'
```

---

## Web Utilities

### fetch_web_content
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "fetch_web_content",
    "arguments": {"url": "https://example.com", "timeout": 10}
  }'
```

### web_search
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "web_search",
    "arguments": {
      "query": "latest langchain news",
      "country": "us",
      "language": "en",
      "num_results": 5,
      "timeout": 10
    }
  }'
```

---

## Reminder Management

### schedule_reminder
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "schedule_reminder",
    "arguments": {
      "title": "Standup with Nina",
      "message": "Reminder: standup begins in 10 minutes.",
      "target_time_iso": "2024-11-18T08:45:00Z",
      "payload": {
        "to": "whatsapp:+628123456789",
        "message": "Standup with Nina begins in 10 minutes."
      }
    }
  }'
```

### list_reminders
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "list_reminders",
    "arguments": {"status": "pending", "limit": 10}
  }'
```

### cancel_reminder
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "cancel_reminder",
    "arguments": {"reminder_id": "REMINDER-ID-HERE"}
  }'
```

---

## Immediate Message Dispatch

### send_message
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "send_message",
    "arguments": {
      "to": "slack:#support",
      "message": "Ticket #1234 flagged as urgent."
    }
  }'
```

---

## Deep Research Workflow

### deep_research
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "deep_research",
    "arguments": {
      "search_topic": "AI adoption in agriculture",
      "email": "research@contoso.com"
    }
  }'
```

---

## Document Generators

### pdf_generate
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "pdf_generate",
    "arguments": {
      "title": "Weekly Report",
      "content": "Summary of weekly activities...",
      "filename": "weekly-report.pdf",
      "author": "Automation Bot"
    }
  }'
```

### docx_generate
```bash
curl -X POST "http://localhost:8002/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "docx_generate",
    "arguments": {
      "title": "Meeting Minutes",
      "content": "Agenda:\n1. Updates\n2. Risks\n3. Next steps",
      "filename": "minutes.docx",
      "author": "Automation Bot"
    }
  }'
```

---

## Tips

- All timestamps must include a timezone offset (e.g. `Z` or `+07:00`).
- Optional arguments can be omitted by removing them from the `arguments` object.
- The API responds with structured JSON; add `| jq` to the end of a `curl` command to pretty-print the response.
