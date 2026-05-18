# WhatsApp MCP Server — Docker Setup

Run the WhatsApp MCP Server 24/7 using Docker Desktop on Windows.

## Prerequisites

- [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) installed and running
- **Microsoft SQL Server** running in Docker (see details below)

## Database Setup (Microsoft SQL Server)

The WhatsApp AI bot uses Microsoft SQL Server to store classification logs, RAG training histories, marketing broadcast schedules, and active message auditing.

### Option A: Install via Docker Desktop Extensions (Recommended)
1. Open **Docker Desktop**.
2. Click on **Extensions** in the left sidebar.
3. Search for **SQL Server** or **SQL containers** (such as the official Microsoft SQL Server Developer extension).
4. Install it, and configure it with:
   - **Port**: `14314` (mapped to `1433` inside the container)
   - **Username**: `sa`
   - **Password**: `Berrysandkeys-99` (or update it in your `context.yaml`)

### Option B: Run via command line (Fastest)
Run the following PowerShell command to launch a pre-configured SQL Server 2022 container:
```powershell
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=Berrysandkeys-99" -p 14314:1433 --name whatsapp-mssql -d mcr.microsoft.com/mssql/server:2022-latest
```
*(The bot automatically connects to `host.docker.internal,14314` and runs all required migrations automatically on startup).*

## Quick Start

### 1. Build the container

```powershell
cd d:\whatsapp-mcp
docker compose build
```

### 2. First run (QR code authentication)

Run in **attached mode** so you can see the QR code:

```powershell
docker compose up
```

Scan the QR code displayed in the terminal with your WhatsApp app (**Settings → Linked Devices → Link a Device**).

Once connected, press `Ctrl+C` to stop the container.

### 3. Run in background (24/7)

```powershell
docker compose up -d
```

The container will automatically restart if it crashes or after a system reboot (as long as Docker Desktop is running).

## Common Commands

| Action | Command |
|---|---|
| View logs | `docker compose logs -f` |
| Stop | `docker compose down` |
| Restart | `docker compose restart` |
| Rebuild after code changes | `docker compose build && docker compose up -d` |

## Re-authentication

If your WhatsApp session expires (~20 days), you'll need to re-scan:

```powershell
# 1. Stop the container
docker compose down

# 2. Clear session data from the local store folder
Remove-Item -Path "whatsapp-bridge\store\whatsapp.db", "whatsapp-bridge\store\messages.db" -Force -ErrorAction SilentlyContinue

# 3. Start again to get a fresh QR code
docker compose up
```

Scan the new QR code, then `Ctrl+C` and run `docker compose up -d` again.

## Data Persistence

WhatsApp session and message history are stored in the `whatsapp-bridge/store/` directory on your host machine. This is mapped into the container via a bind mount, ensuring your session persists across container restarts.

To back up your data, simply copy the `whatsapp-bridge/store/` folder.

## Architecture

```
┌─────────────────────────────────────┐
│  Docker Container (whatsapp-mcp)    │
│                                     │
│  ┌──────────────┐  ┌─────────────┐  │
│  │  Go Bridge   │  │ Python MCP  │  │
│  │  (port 8080) │◄─┤  Server     │  │
│  └──────┬───────┘  └──────┬──────┘  │
│         │                 │         │
│         ▼                 ▼         │
│  ┌────────────────────────────────┐ │
│  │  SQLite DB (Docker Volume)     │ │
│  │  /app/whatsapp-bridge/store/   │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```
