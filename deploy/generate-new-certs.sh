#!/bin/bash
# Generate self-signed SSL certificate for local development
# Usage: ./generate-cert.sh [domain] [days]
# Note: Regenerates certificate if it already exists

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="$SCRIPT_DIR/certs"
DOMAIN="${1:-localhost}"
DAYS="${2:-365}"
KEY_FILE="$CERT_DIR/server.key"
CRT_FILE="$CERT_DIR/server.crt"

# Create certs directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Remove old certificates if they exist
[ -f "$KEY_FILE" ] && rm -f "$KEY_FILE"
[ -f "$CRT_FILE" ] && rm -f "$CRT_FILE"

# Generate self-signed certificate
echo "Generating self-signed certificate..."
openssl req -x509 -nodes -days "$DAYS" -newkey rsa:2048 \
  -keyout "$KEY_FILE" \
  -out "$CRT_FILE" \
  -subj "/CN=$DOMAIN"

chmod 600 "$KEY_FILE"
chmod 644 "$CRT_FILE"

echo "✓ Certificate generated successfully"
echo "  Domain: $DOMAIN"
echo "  Valid for: $DAYS days"
echo "  Key: $KEY_FILE"
echo "  Cert: $CRT_FILE"
