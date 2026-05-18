# WhatsApp MCP Server - Setup Documentation

## Overview
This project connects your personal WhatsApp account to AI assistants via MCP (Model Context Protocol).
It consists of two components:
1. **Go WhatsApp Bridge** (`whatsapp-bridge/`) - Connects to WhatsApp Web API, stores messages in SQLite
2. **Python MCP Server** (`whatsapp-mcp-server/`) - Exposes MCP tools for AI assistants

## Prerequisites Installed
- **Go** 1.24.7
- **GCC** (tdm64-1) 10.3.0 — required for CGO (go-sqlite3) on Windows
- **Python** 3.14.0
- **UV** 0.10.2 (at `C:\Users\andre\.local\bin\uv.exe`)
- CGO enabled via `go env -w CGO_ENABLED=1`

## Code Changes Made
Updated `whatsapp-bridge/main.go` to work with the latest `whatsmeow` library (Feb 2026).
Five function calls had a breaking API change requiring `context.Background()` as first argument:
- `client.Download()` (line 644)
- `sqlstore.New()` (line 803)
- `container.GetFirstDevice()` (line 810)
- `client.GetGroupInfo()` (line 976)
- `client.Store.Contacts.GetContact()` (line 991)

## Running the Bridge
```powershell
cd D:\whatsapp-mcp\whatsapp-bridge
go run main.go
```
- First run: scan QR code with WhatsApp (Settings → Linked Devices → Link a Device)
- Re-auth may be needed after ~20 days
- Bridge exposes REST API on `http://localhost:8080`

## MCP Server Configuration

### For Gemini CLI / Code Assist
Add to your `settings.json` or MCP config:
```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "C:\\Users\\andre\\.local\\bin\\uv.exe",
      "args": [
        "--directory",
        "D:\\whatsapp-mcp\\whatsapp-mcp-server",
        "run",
        "main.py"
      ]
    }
  }
}
```

### For Cursor
Save to `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "C:\\Users\\andre\\.local\\bin\\uv.exe",
      "args": [
        "--directory",
        "D:\\whatsapp-mcp\\whatsapp-mcp-server",
        "run",
        "main.py"
      ]
    }
  }
}
```

### For Claude Desktop
Save to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or equivalent on Windows.

## Dependencies
- `whatsapp-mcp-server/` uses: `httpx`, `mcp[cli]`, `requests` (managed via UV/pyproject.toml)
- `whatsapp-bridge/` uses: `whatsmeow` (Feb 2026), `go-sqlite3`, `qrterminal`

## Troubleshooting
- **Client outdated error**: Run `go get go.mau.fi/whatsmeow@latest && go mod tidy` in `whatsapp-bridge/`
- **QR code not visible**: Run `go run main.go` in a standalone PowerShell/terminal, not the IDE terminal
- **CGO errors**: Ensure GCC is in PATH and CGO is enabled (`go env -w CGO_ENABLED=1`)
- **Messages not loading**: Wait several minutes after first auth for history sync
- **Out of sync**: Delete `whatsapp-bridge/store/messages.db` and `whatsapp-bridge/store/whatsapp.db`, restart bridge
