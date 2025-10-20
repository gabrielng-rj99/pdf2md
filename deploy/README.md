# PDF2MD Deployment

Simple Docker Compose setup for the PDF to Markdown converter with **true network isolation**.

## 🚀 Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Generate SSL certificate (first time only)
./generate-cert.sh

# 3. Start services
docker compose up -d

# 4. Test network isolation
./test-isolation.sh

# 5. Stop services
docker compose down
```

---

## 🔐 Network Isolation Architecture

This deployment implements **true Docker network isolation** where:

- ✅ **App is COMPLETELY isolated** from the host (no direct access possible)
- ✅ **Host can only access via nginx** (reverse proxy on ports 80/443)
- ✅ **Nginx bridges internal app to external network**
- ✅ **Two separate networks** prevent direct exposure

### Network Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    Host Machine                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ╔═══════════════════════════════════════════════════╗  │
│  ║  INTERNAL NETWORK (pdf2md_internal)               ║  │
│  ║  Subnet: 172.18.0.0/24                           ║  │
│  ║  ⚠️  COMPLETELY ISOLATED FROM HOST                ║  │
│  ║  ICC: Disabled (no inter-container comm)         ║  │
│  ║                                                  ║  │
│  ║  ┌─────────────────┐      ┌──────────────────┐  ║  │
│  ║  │  App Container  │      │ Nginx Container  │  ║  │
│  ║  │  172.18.0.100   │◄────►│ 172.18.0.101     │  ║  │
│  ║  │  :8000          │      │ (internal IP)    │  ║  │
│  ║  └─────────────────┘      └──────────────────┘  ║  │
│  ║                                  ▲               ║  │
│  ╚══════════════════════════════════╬═══════════════╝  │
│                                      │                 │
│  ╔═══════════════════════════════════╩═══════════════╗  │
│  ║  EXTERNAL NETWORK (pdf2md_external)              ║  │
│  ║  Subnet: 172.19.0.0/24                          ║  │
│  ║  🌐 CONNECTED TO HOST                           ║  │
│  ║                                                  ║  │
│  ║                  ┌──────────────────┐             ║  │
│  ║                  │ Nginx Container  │             ║  │
│  ║                  │ 172.19.0.100     │             ║  │
│  ║                  │ :80, :443 ◄──────┼────────────►  │
│  ║                  └──────────────────┘             ║  │
│  ╚══════════════════════════════════════════════════╝  │
│                                                         │
│  Host Port 80 ──────► Nginx :80                        │
│  Host Port 443 ─────► Nginx :443                       │
│                                                         │
└──────────────────────────────────────────────────────────┘
```

### Key Security Points

| Component | Access | Details |
|-----------|--------|---------|
| **App (172.18.0.100)** | ❌ Not accessible from host | No port mapping, internal network only |
| **Nginx Internal (172.18.0.101)** | ❌ Not accessible from host | Internal network only |
| **Nginx External (172.19.0.100)** | ✅ Accessible via :80/:443 | Mapped to host ports |
| **Host → App** | ❌ BLOCKED | Must go through nginx proxy |
| **Host → Nginx** | ✅ ALLOWED | Only via mapped ports (80/443) |
| **Nginx → App** | ✅ ALLOWED | Internal network communication |

---

## 📋 Default Configuration

All defaults are used when variables are not set in `.env`.

### Internal Network (App + Nginx)
| Setting | Default | Variable |
|---------|---------|----------|
| Name | `pdf2md_internal` | `INTERNAL_NETWORK_NAME` |
| Driver | `bridge` | (fixed) |
| Subnet | `172.18.0.0/24` | `INTERNAL_NETWORK_SUBNET` |
| Gateway | `172.18.0.1` | `INTERNAL_NETWORK_GATEWAY` |
| MTU | `1500` | `INTERNAL_NETWORK_MTU` |
| ICC | `false` | `INTERNAL_NETWORK_ICC` |

### External Network (Nginx only)
| Setting | Default | Variable |
|---------|---------|----------|
| Name | `pdf2md_external` | `EXTERNAL_NETWORK_NAME` |
| Driver | `bridge` | (fixed) |
| Subnet | `172.19.0.0/24` | `EXTERNAL_NETWORK_SUBNET` |
| Gateway | `172.19.0.1` | `EXTERNAL_NETWORK_GATEWAY` |
| MTU | `1500` | `EXTERNAL_NETWORK_MTU` |

### Application Container
| Setting | Default | Variable |
|---------|---------|----------|
| Name | `extract-pdf` | `APP_CONTAINER_NAME` |
| Image | `extract-pdf:latest` | `APP_IMAGE` |
| IP (internal) | `172.18.0.100` | `APP_IP` |
| Port | `8000` | `APP_PORT` |
| Environment | `production` | `ENV` |
| Workers | `4` | `GUNICORN_WORKERS` |

### Nginx Container
| Setting | Default | Variable |
|---------|---------|----------|
| Name | `extract-pdf-nginx` | `NGINX_CONTAINER_NAME` |
| Image | `nginx:stable` | `NGINX_IMAGE` |
| IP (internal) | `172.18.0.101` | `NGINX_INTERNAL_IP` |
| IP (external) | `172.19.0.100` | `NGINX_EXTERNAL_IP` |
| HTTP Port | `80` | `HTTP_PORT` |
| HTTPS Port | `443` | `HTTPS_PORT` |
| Host HTTP Port | `80` | `HOST_HTTP_PORT` |
| Host HTTPS Port | `443` | `HOST_HTTPS_PORT` |

### Volumes
| Mount Point | Host Path | Purpose |
|-------------|-----------|---------|
| `/app/output` | `../output` | PDF output files |
| `/app/config.ini` | `../config.ini` | App config |
| `/etc/nginx/certs` | `./certs` | SSL certificates |
| `/var/log/nginx` | `./log` | Nginx logs |

---

## 🔐 SSL Certificate Generation

Before starting the services, generate a self-signed SSL certificate:

```bash
./generate-cert.sh [domain] [days]
```

### Parameters
- `domain` - Certificate domain (default: `localhost`)
- `days` - Certificate validity in days (default: `365`)

### Examples
```bash
# Basic (generates for localhost, valid 365 days)
./generate-cert.sh

# Custom domain, 2 years validity
./generate-cert.sh example.com 730

# Custom domain only
./generate-cert.sh mydomain.local
```

### What it does
- Creates `./certs/` directory if it doesn't exist
- Generates `server.key` and `server.crt`
- Sets proper permissions (600 for key, 644 for cert)
- Regenerates certificates (overwrites old ones if they exist)

### For Production
Replace `server.crt` and `server.key` with certificates from your Certificate Authority (Let's Encrypt, Sectigo, etc).

---

## 🧪 Testing Network Isolation

Verify that the network isolation is working correctly:

```bash
./test-isolation.sh
```

### What the test does
1. ✅ Verifies host **CANNOT** ping app container
2. ✅ Verifies host **CANNOT** ping nginx internal IP
3. ✅ Verifies nginx **CAN** access app via internal DNS
4. ✅ Verifies host **CAN** access nginx via external port (80/443)
5. ✅ Displays network configuration details

### Expected Results
```
✓ Host BLOCKED: Não consegue pingar app
✓ Host BLOCKED: Não consegue pingar nginx interno
✓ Nginx acessa App via DNS interno (http://app:8000)
✓ Host consegue conectar ao nginx na porta 443
✓ Rede interna (pdf2md_internal): 1 container
✓ Rede externa (pdf2md_external): nginx presente
```

If any checks fail, review the docker-compose.yml and network configuration.

---

## Environment Variables

All variables in `.env` are **optional**. Omit to use defaults from `docker-compose.yml`.

```env
# ========== INTERNAL NETWORK (App + Nginx) ==========
# Name of the internal bridge network
INTERNAL_NETWORK_NAME=pdf2md_internal

# Internal network subnet (must not overlap with other networks)
INTERNAL_NETWORK_SUBNET=172.18.0.0/24

# Internal network gateway
INTERNAL_NETWORK_GATEWAY=172.18.0.1

# Enable inter-container communication (false = more secure)
INTERNAL_NETWORK_ICC=false

# MTU for internal network
INTERNAL_NETWORK_MTU=1500

# ========== EXTERNAL NETWORK (Nginx only) ==========
# Name of the external bridge network
EXTERNAL_NETWORK_NAME=pdf2md_external

# External network subnet (must not overlap with internal or other networks)
EXTERNAL_NETWORK_SUBNET=172.19.0.0/24

# External network gateway
EXTERNAL_NETWORK_GATEWAY=172.19.0.1

# ICC for external network (usually true, but only nginx is here)
EXTERNAL_NETWORK_ICC=true

# MTU for external network
EXTERNAL_NETWORK_MTU=1500

# ========== APPLICATION CONTAINER ==========
# Docker image for the app
APP_IMAGE=extract-pdf:latest

# Container name for the app
APP_CONTAINER_NAME=extract-pdf

# Port the app listens on (inside container)
APP_PORT=8000

# IP address on internal network
APP_IP=172.18.0.100

# Environment (production/development)
ENV=production

# Number of Gunicorn workers
GUNICORN_WORKERS=4

# ========== NGINX CONTAINER ==========
# Docker image for nginx
NGINX_IMAGE=nginx:stable

# Container name for nginx
NGINX_CONTAINER_NAME=extract-pdf-nginx

# HTTP port inside container
HTTP_PORT=80

# HTTPS port inside container
HTTPS_PORT=443

# HTTP port on host machine (mapped to nginx HTTP_PORT)
HOST_HTTP_PORT=80

# HTTPS port on host machine (mapped to nginx HTTPS_PORT)
HOST_HTTPS_PORT=443

# Nginx IP on internal network
NGINX_INTERNAL_IP=172.18.0.101

# Nginx IP on external network
NGINX_EXTERNAL_IP=172.19.0.100

# ========== VOLUMES ==========
# Host directory for PDF outputs
HOST_OUTPUT_DIR=../output

# Host file for app configuration
HOST_CONFIG_INI=../config.ini

# Directory containing SSL certificates
CERT_DIR=./certs
```

---

## Accessing Services

### From Inside Containers
```bash
# Test app from nginx
docker compose exec nginx curl http://app:8000

# App internal IP (DNS resolution)
docker compose exec nginx curl http://172.18.0.100:8000

# Test nginx from app
docker compose exec app curl http://nginx/health
```

### From Host Machine

**Option 1: Via Nginx (Recommended - Security Best Practice)**
```bash
# HTTP
curl http://localhost:80

# HTTPS (with self-signed cert warning)
curl -k https://localhost:443
```

**Option 2: Direct Container Access (Development Only)**
```bash
# Docker exec into container
docker compose exec app curl localhost:8000

# Docker exec from another container
docker compose exec nginx curl http://app:8000
```

**Option 3: Temporary Port Mapping (Development Only)**

Edit `docker-compose.yml` to add ports mapping:
```yaml
services:
  app:
    ports:
      - "8000:8000"
```

⚠️ **WARNING**: This breaks the security model! Only for development.

---

## Common Tasks

### View Logs
```bash
# All services
docker compose logs -f

# App only
docker compose logs -f app

# Nginx only
docker compose logs -f nginx

# Last 50 lines
docker compose logs --tail 50

# Nginx error logs (from volume)
tail -f log/error.log
```

### Check Status
```bash
# Container status
docker compose ps

# Network details
docker network inspect pdf2md_internal
docker network inspect pdf2md_external

# Container IP addresses
docker compose exec app ip addr show
docker compose exec nginx ip addr show
```

### Access Container Shell
```bash
docker compose exec app bash
docker compose exec nginx bash

# Root shell
docker compose exec -u root app bash
```

### Restart Services
```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart app
docker compose restart nginx
```

### Rebuild Images
```bash
# Rebuild app image
docker compose up -d --build app

# Rebuild all
docker compose up -d --build
```

### Remove Everything
```bash
# Remove containers and networks
docker compose down

# Also remove volumes
docker compose down -v

# Remove images too
docker compose down -v --rmi all
```

---

## Development vs Production

### Development Mode
```env
# .env
ENV=development
GUNICORN_WORKERS=1
```

Reload app on code changes:
```bash
docker compose restart app
```

### Production Mode
```env
# .env
ENV=production
GUNICORN_WORKERS=4  # Adjust based on CPU cores
```

Use real SSL certificates:
1. Replace `certs/server.crt` and `certs/server.key`
2. Update nginx config if needed
3. Restart: `docker compose up -d`

---

## Troubleshooting

### Network already exists error
```bash
# Remove networks
docker network rm pdf2md_internal pdf2md_external

# Start fresh
docker compose up -d
```

### Can't communicate between app and nginx
```bash
# Verify both containers are on internal network
docker network inspect pdf2md_internal

# Test direct access
docker compose exec nginx curl http://172.18.0.100:8000

# Check DNS
docker compose exec nginx nslookup app
```

### Host can't access nginx
```bash
# Verify nginx is listening
docker compose exec nginx netstat -tlnp

# Check port mapping
docker compose ps

# Test from host
curl -v http://localhost

# Check firewall
sudo iptables -L | grep 80
```

### Certificates not working
```bash
# Regenerate
rm -rf certs/
./generate-cert.sh

# Verify certificate
openssl x509 -in certs/server.crt -text -noout

# Check nginx config
docker compose exec nginx nginx -t

# Restart nginx
docker compose restart nginx
```

### Permission errors on volumes
```bash
# Fix ownership
chmod -R 755 output/
chmod 644 config.ini

# Or (if using docker-compose v2+)
docker compose exec -u root app chown -R appuser:appuser /app/output
```

### Container crashes on startup
```bash
# Check logs
docker compose logs app

# Try interactive mode
docker compose run --rm app bash

# Inside container, test app
python -m pdf2md --help
```

---

## File Structure

```
deploy/
├── docker-compose.yml          # Main compose configuration
├── .env.example                # Example environment file
├── Dockerfile                  # App image definition
├── README.md                   # This file
├── generate-cert.sh            # SSL certificate generator
├── test-isolation.sh           # Network isolation tester
├── nginx/
│   ├── conf.d/
│   │   └── default.conf        # Nginx reverse proxy config
│   └── ssl/
│       └── (certificates go here)
├── certs/                      # SSL certificates (generated)
│   ├── server.crt
│   └── server.key
└── log/                        # Nginx logs (auto-created)
    ├── access.log
    └── error.log
```

---

## Important Notes

### Security
- ✅ **No ports exposed to host by default** — intentional for security
- ✅ **App completely isolated** — no direct host access possible
- ✅ **All traffic through nginx** — HTTP → HTTPS termination
- ✅ **Internal network isolated** — ICC disabled by default

---

## 🔒 Segurança de Rede

**IMPORTANTE:**  
A rede interna (`${INTERNAL_NETWORK_NAME}`) deve ser bloqueada via firewall no host principal para garantir que só containers se comuniquem.

### Exemplos de bloqueio:

- **iptables** (legacy):
  ```sh
  sudo iptables -I DOCKER-USER -d 172.18.1.0/24 -j DROP
  ```
- **nftables** (moderno):
  ```sh
  sudo nft add rule inet filter output ip daddr 172.18.1.0/24 drop
  sudo nft add rule inet filter forward ip daddr 172.18.1.0/24 drop
  ```
  *(Adapte para sua tabela/chain conforme sua configuração)*

- Só o proxy/nginx deve ser acessível externamente (se/quando for expor portas).
- Nunca exponha o app diretamente ao host ou à internet.

---

### Configuration
- `.env` file is **optional** — all defaults will be used if missing
- Keep `.env` in `.gitignore` to avoid committing sensitive data
- Use `.env.example` as a reference for available variables

### Volumes
- All volume paths are **relative to the `deploy/` directory**
- Output directory is mounted read-write for app to save files
- Config file is mounted read-only to prevent accidental changes

### Production
- Replace self-signed certificates with real ones
- Set `ENV=production`
- Adjust `GUNICORN_WORKERS` based on server CPU cores
- Enable nginx compression and caching if needed
- Set up monitoring and log rotation

---

## Quick Commands Reference

| Command | Purpose |
|---------|---------|
| `docker compose up -d` | Start all services |
| `docker compose down` | Stop and remove containers |
| `docker compose ps` | Show container status |
| `docker compose logs -f` | Stream logs from all services |
| `docker compose restart` | Restart all services |
| `docker compose down -v` | Remove everything (including volumes) |
| `./generate-cert.sh` | Generate SSL certificates |
| `./test-isolation.sh` | Test network isolation |
| `docker network inspect pdf2md_internal` | Show internal network details |
| `docker network inspect pdf2md_external` | Show external network details |
| `docker compose exec app bash` | Shell into app container |
| `docker compose exec nginx bash` | Shell into nginx container |

---

## Support & Debugging

### Enable Debug Logging
```env
# .env
ENV=development
```

### Check System Resources
```bash
docker stats
docker system df
```

### Full System Cleanup
```bash
docker compose down -v
docker system prune -a
docker volume prune
```

### Network Diagnostics
```bash
# List all networks
docker network ls

# Inspect network
docker network inspect pdf2md_internal

# Check container networking
docker inspect extract-pdf | grep -A 10 NetworkSettings
```
