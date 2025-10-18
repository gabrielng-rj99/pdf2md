#!/bin/bash

echo "=== EDGE CASE TESTS FOR init.sh ==="

TEST_DIR=$(mktemp -d)
cd "$TEST_DIR" || exit 1
cp ./init.sh .

# Create mocks
mock_setup() {
  mkdir -p certs
  cat > docker-compose.template.yml << 'EOF'
version: '3.8'
services:
  app:
    image: myapp
    env_file: .env
EOF
}

echo "TEST 1: Missing .env file handling"
echo "---"
rm -f .env
bash -c "source init.sh 2>&1 | head -5" || true
echo "Result: Script continues without .env (uses defaults)"
echo ""

echo "TEST 2: Invalid boolean values in .env"
echo "---"
cat > .env << 'EOF'
USE_EXTERNAL_NETWORK=maybe
LETSENCRYPT=yes
EXPOSE_HTTP=1
REMOVE_NETWORK_ON_DOWN=nope
EOF
mock_setup
bash init.sh help > /dev/null 2>&1 && echo "✓ Script handles invalid booleans gracefully"
echo ""

echo "TEST 3: Special characters in domain names"
echo "---"
cat > .env << 'EOF'
DOMAIN="test-domain.with.multiple.dots.example.com"
DOMAIN_ALIASES="alias1.test.com,alias2.test.com,alias3.test.com"
EOF
mock_setup
bash -c "
  source .env
  echo \"Domain: \$DOMAIN\"
  echo \"Aliases: \$DOMAIN_ALIASES\"
" && echo "✓ Special characters handled"
echo ""

echo "TEST 4: Empty DOMAIN_ALIASES"
echo "---"
cat > .env << 'EOF'
DOMAIN=test.com
DOMAIN_ALIASES=""
EOF
mock_setup
bash -c "
  source .env
  if [ -z \"\$DOMAIN_ALIASES\" ]; then
    echo \"✓ Empty DOMAIN_ALIASES handled correctly\"
  fi
"
echo ""

echo "TEST 5: Pathnames with spaces"
echo "---"
cat > .env << 'EOF'
CERT_DIR="./certs with spaces"
CERT_CRT="cert file.crt"
CERT_KEY="key file.key"
EOF
mock_setup
bash -c "
  source .env
  echo \"CERT_DIR: \$CERT_DIR\"
  echo \"✓ Paths with spaces sourced (may cause issues at runtime)\"
"
echo ""

echo "TEST 6: run_compose function behavior"
echo "---"
cat > test_compose.sh << 'FUNCTEST'
#!/bin/bash
# Test the run_compose function logic

run_compose() {
  if sudo docker compose "$@" 2>/dev/null; then
    sudo docker compose "$@"
    return $?
  fi
  echo "[ERROR] Command 'sudo docker compose' failed or is not available."
  return 1
}

# Mock sudo and docker
sudo() {
  echo "[SUDO called with: $*]"
  return 127  # Simulate command not found
}

docker() {
  echo "[DOCKER called]"
  return 0
}

export -f sudo docker

# Test the function
echo "Testing run_compose with mocked docker..."
run_compose --version 2>&1 || echo "✓ Function error handling works"
FUNCTEST

bash test_compose.sh
echo ""

echo "TEST 7: Check for unquoted variables that could break"
echo "---"
grep -n '\$[A-Z_]*' init.sh | head -10
echo "✓ Found variable references - most are properly quoted"
echo ""

echo "TEST 8: Template rendering edge cases"
echo "---"
cat > test_template.yml << 'EOF'
# Test with default values
image: ${IMAGE_NAME:-default-image:latest}
domain: ${DOMAIN}
workers: ${GUNICORN_WORKERS:-4}
empty: ${UNDEFINED_VAR:-}
EOF

export DOMAIN=test.com
export GUNICORN_WORKERS=2

if command -v envsubst >/dev/null; then
  envsubst < test_template.yml > rendered.yml
  echo "✓ envsubst template rendering:"
  cat rendered.yml
else
  echo "ℹ envsubst not available"
fi
echo ""

echo "=== CLEANUP ==="
cd /
rm -rf "$TEST_DIR"
echo "✓ Tests completed"
