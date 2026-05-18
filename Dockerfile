# ============================================
# Stage 1: Build the Go WhatsApp Bridge
# ============================================
FROM golang:1.24-bookworm AS go-builder

WORKDIR /build

# Copy Go module files first for better layer caching
COPY whatsapp-bridge/go.mod whatsapp-bridge/go.sum ./
RUN go mod download

# Copy Go source and build with CGO enabled (required for go-sqlite3)
COPY whatsapp-bridge/main.go ./
RUN CGO_ENABLED=1 GOOS=linux go build -o whatsapp-bridge main.go

# ============================================
# Stage 2: Runtime - Go bridge only
# ============================================
FROM debian:bookworm-slim

# Install minimal runtime deps (libc for CGO, ca-certs for HTTPS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/whatsapp-bridge

# Copy the compiled Go binary
COPY --from=go-builder /build/whatsapp-bridge ./whatsapp-bridge

# Create store directory (will be bind-mounted)
RUN mkdir -p store

EXPOSE 8080

CMD ["./whatsapp-bridge"]
