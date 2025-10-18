#!/bin/bash
# Test script to verify init.sh logic without requiring docker/sudo

# Create a temporary test environment
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR" || exit 1

# Copy init.sh
cp ./init.sh .

# Mock sudo to avoid password prompts
sudo() {
  echo "[MOCK-SUDO] $@"
  return 0
}
export -f sudo

# Mock docker to check calls
docker() {
  echo "[MOCK-DOCKER] $@"
  return 0
}
export -f docker

# Create template file
mkdir -p certs
cat > docker-compose.template.yml << 'EOF'
version: '3.8'
services:
  app:
    image: myapp:latest
    environment:
      - DOMAIN=${DOMAIN}
      - WORKERS=${GUNICORN_WORKERS}
EOF

# Create .env
cat > .env << 'EOF'
DOMAIN=pdf2md.test
DOCKER_NETWORK_NAME=test_net
GUNICORN_WORKERS=2
EOF

echo "=== TEST 1: Verify syntax ==="
bash -n init.sh && echo "✓ Syntax valid"

echo ""
echo "=== TEST 2: Test help command ==="
bash init.sh help 2>&1 | head -20

echo ""
echo "=== TEST 3: Source test - check variable loading ==="
bash << 'SRCTEST'
source .env
echo "✓ .env loaded successfully"
echo "  DOMAIN=$DOMAIN"
echo "  GUNICORN_WORKERS=$GUNICORN_WORKERS"
SRCTEST

echo ""
echo "=== TEST 4: Test template rendering (envsubst or python) ==="
bash << 'RENDERTEST'
source .env
if command -v envsubst >/dev/null 2>&1; then
  echo "✓ envsubst available"
  export DOMAIN GUNICORN_WORKERS
  envsubst < docker-compose.template.yml > docker-compose.yml
  echo "✓ Template rendered with envsubst"
else
  echo "ℹ envsubst not available, testing python fallback"
  python3 - <<'PY' docker-compose.template.yml docker-compose.yml
import sys,os,re
tpl=open(sys.argv[1]).read()
def replace(match):
    expr=match.group(1)
    m=re.match(r'^([^:]+)(?::-(.*))?$',expr)
    if not m:
        return ''
    var=m.group(1)
    default=m.group(2) or ''
    return os.environ.get(var, default)
res=re.sub(r'\$\{([^}]+)\}', replace, tpl)
open(sys.argv[2],'w').write(res)
PY
  echo "✓ Template rendered with python"
fi
cat docker-compose.yml
RENDERTEST

echo ""
echo "=== TEST 5: Check generated files ==="
ls -la

echo ""
echo "=== CLEANUP ==="
cd /
rm -rf "$TEST_DIR"
echo "✓ Test environment cleaned up"
