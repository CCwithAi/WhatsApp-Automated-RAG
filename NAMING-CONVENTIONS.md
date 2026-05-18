# WhatsApp MCP — Naming Conventions

All resources for a given WhatsApp instance follow consistent naming patterns.

## Pattern

| Resource | Format | Example |
|---|---|---|
| Bridge container | `whatsapp-bridge-{name}` | `whatsapp-bridge-cleaner` |
| Bot container | `whatsapp-bot-{name}` | `whatsapp-bot-cleaner` |
| Docker service | `bridge-{name}` / `bot-{name}` | `bridge-cleaner` / `bot-cleaner` |
| Host port | `808{n}` (sequential) | `8081` |
| Instance directory | `./instances/{name}/` | `./instances/cleaner/` |
| Config file | `./instances/{name}/context.yaml` | `./instances/cleaner/context.yaml` |
| Bridge data | `./instances/{name}/store/` | `./instances/cleaner/store/` |
| Docker network | `whatsapp-net-{name}` | `whatsapp-net-cleaner` |
| SQL Server tables | `{name}_` prefix | `cleaner_replied_messages` |

## Instance Names

Use short, lowercase, alphanumeric names:

| Instance | Name | Port |
|---|---|---|
| Cleaner in Manchester | `cleaner` | `8081` |
| *(future)* | `affordable` | `8082` |
| *(future)* | `myreta` | `8083` |
| *(future)* | `sellmyauto` | `8084` |

## Adding a New Instance

1. Create `instances/{name}/context.yaml` (copy from an existing one)
2. Add `bridge-{name}` and `bot-{name}` services in `docker-compose.yml`
3. Add `whatsapp-net-{name}` network
4. Run `docker compose up bridge-{name}` to scan QR code
5. Start everything: `docker compose up -d`

## SQL Server Tables

Each instance creates tables prefixed with its name:
- `{name}_replied_messages` — Dedup tracking
- `{name}_reply_cooldowns` — Rate limiting
- `{name}_message_log` — Full audit trail
- `{name}_marketing_messages` — Broadcast queue
- `{name}_marketing_log` — Delivery tracking
