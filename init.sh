#!/bin/sh
set -e

# Caminho do script de geração de certificados
CERT_SCRIPT="deploy/generate-new-certs.sh"

# Verifica se o script existe e é executável
if [ ! -x "$CERT_SCRIPT" ]; then
  echo "Tornando $CERT_SCRIPT executável..."
  chmod +x "$CERT_SCRIPT"
fi

echo "Gerando certificados SSL..."
"$CERT_SCRIPT"

echo "Subindo containers com Docker Compose..."
docker compose -f deploy/docker-compose.yml up -d

echo "Init concluído!"
