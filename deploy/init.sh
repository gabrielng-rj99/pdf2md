#!/usr/bin/env bash
#
# init.sh - Helper to initialize deployment for PDF-to-Markdown-with-Images (deploy/)
#
# Updated: This version renders docker-compose.yml from docker-compose.template.yml
# using environment variables loaded from deploy/.env (if present), then proceeds
# to create network, generate certs, build and start the stack as before.
#
set -euo pipefail
#
# Helpers ---------------------------------------------------------------------
#
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir" || exit 1
#
# Defaults (will be overridden by .env if present)
ENV_FILE="$script_dir/.env"
TEMPLATE_FILE="$script_dir/docker-compose.template.yml"
DOCKER_COMPOSE_FILE="$script_dir/docker-compose.yml"
#
# Load .env if present (simple KEY=VALUE lines)
if [ -f "$ENV_FILE" ]; then
  echo "Loading environment from $ENV_FILE"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
#
# Provide variable fallbacks
DOCKER_NETWORK_NAME="${DOCKER_NETWORK_NAME:-pdf2md_net}"
USE_EXTERNAL_NETWORK="${USE_EXTERNAL_NETWORK:-false}"
EXTERNAL_NETWORK_NAME="${EXTERNAL_NETWORK_NAME:-}"
NETWORK_SUBNET="${NETWORK_SUBNET:-172.18.0.0/24}"
NETWORK_GATEWAY="${NETWORK_GATEWAY:-172.18.0.1}"
#
APP_INTERNAL_IP="${APP_INTERNAL_IP:-172.18.0.200}"
NGINX_INTERNAL_IP="${NGINX_INTERNAL_IP:-172.18.0.201}"
APP_INTERNAL_PORT="${APP_INTERNAL_PORT:-8000}"
#
CERT_DIR="${CERT_DIR:-./certs}"
CERT_CRT="${CERT_CRT:-pdf2md.home.arpa.crt}"
CERT_KEY="${CERT_KEY:-pdf2md.home.arpa.key}"
DOMAIN="${DOMAIN:-pdf2md.home.arpa}"
DOMAIN_ALIASES="${DOMAIN_ALIASES:-}"
#
LETSENCRYPT="${LETSENCRYPT:-false}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-admin@home.arpa}"
#
EXPOSE_HTTP="${EXPOSE_HTTP:-false}"
EXPOSE_HTTPS="${EXPOSE_HTTPS:-false}"
HOST_BIND_IP="${HOST_BIND_IP:-}"
EXPOSE_HTTP_PORT="${EXPOSE_HTTP_PORT:-80}"
EXPOSE_HTTPS_PORT="${EXPOSE_HTTPS_PORT:-443}"
REMOVE_NETWORK_ON_DOWN="${REMOVE_NETWORK_ON_DOWN:-true}"
#
GUNICORN_WORKERS="${GUNICORN_WORKERS:-4}"
#
# track if script generated certs (so we can optionally remove them on down)
GENERATED_MARKER="${GENERATED_CERT_MARKER:-.generated_by_init}"
#
# Compose command resolver
# Compose command wrapper: always use 'sudo docker compose' (no fallbacks).
# This enforces use of the docker CLI with sudo; if the plugin is not available the script will fail here.
run_compose() {
  # Attempt to run using the docker CLI compose plugin with sudo.
  if sudo docker compose "$@"; then
    return 0
  fi

  # If we reach here, the 'docker compose' plugin is not available or failed.
  err "Command 'sudo docker compose' failed or is not available. Install the Docker Compose plugin so 'sudo docker compose' works on this host."
  return 1
}
#
# Functions -------------------------------------------------------------------
#
info() { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[ERROR]\033[0m %s\n" "$*"; }
#
validate_bool() {
  local var="$1"
  local name="$2"
  if [[ ! "$var" =~ ^(true|false|True|False)$ ]]; then
    warn "$name has invalid value: '$var' (expected true/false, defaulting to false)"
  fi
}
#
ensure_network() {
  validate_bool "$USE_EXTERNAL_NETWORK" "USE_EXTERNAL_NETWORK"
  if [ "${USE_EXTERNAL_NETWORK}" = "true" ] || [ "${USE_EXTERNAL_NETWORK}" = "True" ]; then
    if [ -z "$EXTERNAL_NETWORK_NAME" ]; then
      err "USE_EXTERNAL_NETWORK=true but EXTERNAL_NETWORK_NAME is empty in .env"
      exit 1
    fi
    info "Using external existing network: $EXTERNAL_NETWORK_NAME"
    if ! sudo docker network ls --format '{{.Name}}' | grep -xq "$EXTERNAL_NETWORK_NAME"; then
      err "External network '$EXTERNAL_NETWORK_NAME' does not exist. Create it with: sudo docker network create $EXTERNAL_NETWORK_NAME"
      exit 1
    fi
    return 0
  fi
#
  # Check if network exists by name
  if sudo docker network ls --format '{{.Name}}' | grep -xq "$DOCKER_NETWORK_NAME"; then
    info "Docker network '$DOCKER_NETWORK_NAME' already exists"
    return 0
  fi
#
  info "Creating docker network '$DOCKER_NETWORK_NAME' (subnet=${NETWORK_SUBNET}, gateway=${NETWORK_GATEWAY})"
  sudo docker network create --driver bridge --subnet "$NETWORK_SUBNET" --gateway "$NETWORK_GATEWAY" "$DOCKER_NETWORK_NAME"
  info "Network created: $DOCKER_NETWORK_NAME"
}
#
generate_self_signed_certs() {
  # If LETSENCRYPT=true we skip self-signed generation
  validate_bool "$LETSENCRYPT" "LETSENCRYPT"
  if [ "${LETSENCRYPT}" = "true" ] || [ "${LETSENCRYPT}" = "True" ]; then
    warn "LETSENCRYPT=true in .env: skipping self-signed certificate generation"
    return 0
  fi
#
  mkdir -p "$CERT_DIR"
  crt_path="$CERT_DIR/$CERT_CRT"
  key_path="$CERT_DIR/$CERT_KEY"
#
  if [ -f "$crt_path" ] && [ -f "$key_path" ]; then
    info "Certificate and key already exist in $CERT_DIR — skipping generation"
    return 0
  fi
#
  info "Generating self-signed certificate for '$DOMAIN' -> $crt_path"
  # Build SAN list if DOMAIN_ALIASES set
  SAN=""
  if [ -n "$DOMAIN_ALIASES" ]; then
    IFS=',' read -r -a aliases <<< "$DOMAIN_ALIASES"
    san_entries=("DNS:${DOMAIN}")
    for a in "${aliases[@]}"; do
      san_entries+=("DNS:${a}")
    done
    SAN=$(printf ",%s" "${san_entries[@]}")
    SAN="${SAN:1}"
  fi
#
  if openssl version >/dev/null 2>&1 && openssl req -help 2>&1 | grep -q -- '--addext'; then
    openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
      -keyout "$key_path" -out "$crt_path" -subj "/CN=${DOMAIN}" \
      -addext "subjectAltName=DNS:${DOMAIN}${DOMAIN_ALIASES:+,$(echo "$DOMAIN_ALIASES" | tr ',' ',DNS:')}"
  else
    tmpcfg="$(mktemp)"
    cat >"$tmpcfg" <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no
#
[req_distinguished_name]
CN = ${DOMAIN}
#
[v3_req]
subjectAltName = @alt_names
#
[alt_names]
DNS.1 = ${DOMAIN}
EOF
    if [ -n "$DOMAIN_ALIASES" ]; then
      I=2
      IFS=',' read -r -a aliases <<< "$DOMAIN_ALIASES"
      for a in "${aliases[@]}"; do
        echo "DNS.$I = ${a}" >>"$tmpcfg"
        I=$((I + 1))
      done
    fi
#
    openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
      -keyout "$key_path" -out "$crt_path" -config "$tmpcfg" -extensions v3_req
    rm -f "$tmpcfg"
  fi
#
  chmod 600 "$key_path"
  chmod 644 "$crt_path"
  touch "$GENERATED_MARKER"
  info "Self-signed certificate generated and stored in $CERT_DIR"
}
#
render_compose_from_template() {
  # Render docker-compose.yml from docker-compose.template.yml using environment variables.
  # This function prefers envsubst if available; otherwise it falls back to a small Python substitution.
  if [ ! -f "$TEMPLATE_FILE" ]; then
    info "No template file found at $TEMPLATE_FILE — skipping render"
    return 0
  fi
  info "Rendering compose file from template: $TEMPLATE_FILE -> $DOCKER_COMPOSE_FILE"
  # Export variables so envsubst can see them (we already set -a when loading .env)
  if command -v envsubst >/dev/null 2>&1; then
    envsubst <"$TEMPLATE_FILE" >"$DOCKER_COMPOSE_FILE"
  else
    # Fallback Python substitution: replace ${VAR} and ${VAR:-default} with environment values
    python3 - <<'PY' "$TEMPLATE_FILE" "$DOCKER_COMPOSE_FILE"
import sys,os,re
tpl=open(sys.argv[1]).read()
def replace(match):
    expr=match.group(1)
    # handle ${VAR:-default}
    import re
    m=re.match(r'^([^:]+)(?::-(.*))?$',expr)
    if not m:
        return ''
    var=m.group(1)
    default=m.group(2) or ''
    return os.environ.get(var, default)
res=re.sub(r'\$\{([^}]+)\}', replace, tpl)
open(sys.argv[2],'w').write(res)
PY
  fi
  info "Rendered $DOCKER_COMPOSE_FILE"
}
#
build_and_start() {
  info "Rendering compose and starting stack..."
  # Render compose from template if template exists
  render_compose_from_template
#
  # Use compose file in deploy directory
  if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
    err "Compose file not found: $DOCKER_COMPOSE_FILE"
    exit 1
  fi
#
  # Build
  run_compose -f "$DOCKER_COMPOSE_FILE" build --pull
  # Up
  run_compose -f "$DOCKER_COMPOSE_FILE" up -d
  info "Stack started"
}
#
stop_and_cleanup() {
  info "Stopping compose stack..."
  if [ -f "$DOCKER_COMPOSE_FILE" ]; then
    run_compose -f "$DOCKER_COMPOSE_FILE" down
  else
    warn "Compose file not found; skipping compose down"
  fi
#
  # Remove network if we created it and USE_EXTERNAL_NETWORK is false and REMOVE_NETWORK_ON_DOWN is true
  validate_bool "$USE_EXTERNAL_NETWORK" "USE_EXTERNAL_NETWORK"
  validate_bool "$REMOVE_NETWORK_ON_DOWN" "REMOVE_NETWORK_ON_DOWN"
  if [ "${USE_EXTERNAL_NETWORK}" = "false" ] || [ "${USE_EXTERNAL_NETWORK}" = "False" ]; then
    if [ "${REMOVE_NETWORK_ON_DOWN}" = "true" ] || [ "${REMOVE_NETWORK_ON_DOWN}" = "True" ]; then
      if sudo docker network ls --format '{{.Name}}' | grep -xq "$DOCKER_NETWORK_NAME"; then
        info "Removing docker network '$DOCKER_NETWORK_NAME'..."
        if ! sudo docker network rm "$DOCKER_NETWORK_NAME"; then
          warn "Failed to remove network (it may be in use)"
        fi
      fi
    else
      info "REMOVE_NETWORK_ON_DOWN is false; leaving network intact"
    fi
  fi
#
  # Cleanup generated certs if they were created by this script and removal is enabled
  validate_bool "${REMOVE_CERTS_ON_DOWN:-true}" "REMOVE_CERTS_ON_DOWN"
  if [ -f "$GENERATED_MARKER" ] && { [ "${REMOVE_CERTS_ON_DOWN:-true}" = "true" ] || [ "${REMOVE_CERTS_ON_DOWN:-True}" = "True" ]; }; then
    warn "Removing generated certificates in $CERT_DIR (generated by this script)"
    if ! rm -f "$CERT_DIR/$CERT_CRT" "$CERT_DIR/$CERT_KEY" "$GENERATED_MARKER"; then
      warn "Failed to remove some cert files"
    fi
  else
    info "No generated cert marker found or removal disabled; not removing certs"
  fi
#
  info "Cleanup complete"
}
#
show_help() {
  cat <<EOF
Usage: $0 <command>
#
Commands:
  up            Create network (if needed), render compose from template, generate self-signed certs, build and start the stack.
  down          Stop the stack, remove network (if it was created by this script and REMOVE_NETWORK_ON_DOWN=true), delete generated certs (if enabled).
  certs         Generate self-signed certs (no compose actions).
  network       Create the docker network (if not exists).
  clean-certs   Remove certs generated by this script.
  help          Show this help message.
#
Notes:
  - Edit deploy/.env to control behavior (network name, subnet, IPs, domain, cert paths).
  - If USE_EXTERNAL_NETWORK=true, the script will expect EXTERNAL_NETWORK_NAME to exist and will NOT create/remove networks.
  - For production, replace self-signed certs with proper CA-signed certificates and set LETSENCRYPT=true if you have ACME configured.
EOF
}
#
clean_generated_certs() {
  if [ -f "$GENERATED_MARKER" ]; then
    info "Removing generated certs..."
    if rm -f "$CERT_DIR/$CERT_CRT" "$CERT_DIR/$CERT_KEY" "$GENERATED_MARKER"; then
      info "Generated certs removed successfully"
    else
      warn "Failed to remove some generated cert files"
    fi
  else
    warn "No generated certs marker found; nothing to remove"
  fi
}
#
# Main ------------------------------------------------------------------------
#
if [ $# -lt 1 ]; then
  cmd="up"
else
  cmd="$1"
fi
#
case "$cmd" in
  up)
    ensure_network
    generate_self_signed_certs
    build_and_start
    validate_bool "$EXPOSE_HTTP" "EXPOSE_HTTP"
    validate_bool "$EXPOSE_HTTPS" "EXPOSE_HTTPS"
    info "Application should be reachable via the proxy container (internal network)."
    if [ "${EXPOSE_HTTP}" = "true" ] || [ "${EXPOSE_HTTPS}" = "true" ]; then
      info "You have enabled host port exposure in .env; ensure firewall rules allow access."
    fi
    ;;
#
  down)
    stop_and_cleanup
    ;;
#
  certs)
    generate_self_signed_certs
    ;;
#
  network)
    ensure_network
    ;;
#
  clean-certs)
    clean_generated_certs
    ;;
#
  help|--help|-h)
    show_help
    ;;
#
  *)
    err "Unknown command: $cmd"
    show_help
    exit 2
    ;;
esac
#
exit 0
