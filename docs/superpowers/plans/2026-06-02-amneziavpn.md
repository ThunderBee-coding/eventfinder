# AmneziaVPN Docker Container — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AmneziaWG-VPN-Server als Docker-Container aufsetzen, damit Freunde in Russland via DefaultVPN-App (iOS) oder AmneziaWG (Android) die Zensur umgehen und FaceTime/iMessage/WhatsApp nutzen können.

**Architecture:** Container `eyrafir/amnezia-wg-easy` läuft auf Port 51820/UDP (direkt exposed, kein Cloudflare) und 51821/TCP (Web-UI, nur localhost via Cloudflare Tunnel). AWG-Protokoll mit echten Obfuskationsparametern (zufällige H1–H4, S1/S2 ≠ 0) umgeht russisches DPI. Full-Tunnel leitet gesamten Client-Traffic über den VPS.

**Tech Stack:** Docker Compose, `eyrafir/amnezia-wg-easy` Image (userspace amneziawg-go, kein Kernelmodul), iptables NAT, Cloudflare Tunnel (cloudflared), Cloudflare DNS.

---

## File Structure

| Pfad | Zweck |
|------|-------|
| `/docker/amneziavpn/docker-compose.yml` | Container-Definition |
| `/docker/amneziavpn/.env` | Secrets (Passwort-Hash, AWG-Parameter) — nicht in git! |
| `/docker/amneziavpn/data/` | Persistente WireGuard-Configs (Volume-Mount) |

---

## Task 1: Image inspizieren & Env-Vars verifizieren

**Ziel:** Bevor wir docker-compose schreiben, die tatsächlichen Env-Var-Namen des Images bestätigen — sie können von Forks zu Forks abweichen.

**Files:**
- Kein Datei-Output — reine Recherche

- [ ] **Schritt 1.1: Image pullen und Env-Vars auslesen**

```bash
docker pull eyrafir/amnezia-wg-easy:latest
docker inspect eyrafir/amnezia-wg-easy:latest | python3 -c "
import json, sys
data = json.load(sys.stdin)
env = data[0]['Config']['Env']
for e in env:
    print(e)
"
```

Erwartete Ausgabe: Liste von Env-Vars wie `WG_HOST=`, `WG_PORT=`, `PASSWORD=` oder `PASSWORD_HASH=`, ggf. `AWG_JC=` etc.

- [ ] **Schritt 1.2: AWG-Parameter-Support prüfen**

```bash
docker run --rm --entrypoint sh eyrafir/amnezia-wg-easy:latest -c "env | grep -i 'awg\|amnezia\|jc\|jmin\|jmax\|h1\|h2\|h3\|h4\|s1\|s2'" 2>/dev/null || echo "Keine AWG-Env-Vars gefunden"
```

**Wenn KEINE AWG Env-Vars gefunden:** AWG-Parameter werden im Web-UI nach erstem Start gesetzt (unter Settings → AmneziaWG). Dann Schritte 2.3–2.4 überspringen.

**Wenn AWG Env-Vars gefunden:** Exakte Namen notieren — z.B. `AWG_JC`, `AWG_JMIN` etc. — und in Task 3 verwenden.

- [ ] **Schritt 1.3: Passwort-Env-Var-Name prüfen**

Aus der Inspect-Ausgabe prüfen: Heißt die Variable `PASSWORD` (Klartext) oder `PASSWORD_HASH` (bcrypt)?

- Falls `PASSWORD_HASH`: bcrypt-Hash wird in Task 2 generiert
- Falls `PASSWORD`: Klartextpasswort direkt in `.env` — dann Schritt 2.5 überspringen

---

## Task 2: Host vorbereiten & Secrets generieren

**Files:**
- Erstellen: `/docker/amneziavpn/`
- Erstellen: `/docker/amneziavpn/.env`
- Modifizieren: `/etc/sysctl.conf`

- [ ] **Schritt 2.1: Verzeichnis anlegen**

```bash
mkdir -p /docker/amneziavpn/data
chmod 700 /docker/amneziavpn/data
```

- [ ] **Schritt 2.2: IP-Forwarding dauerhaft aktivieren**

```bash
grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p
sysctl net.ipv4.ip_forward
```

Erwartete Ausgabe: `net.ipv4.ip_forward = 1`

- [ ] **Schritt 2.3: Zufällige AWG-Obfuskationsparameter generieren**

```bash
python3 -c "
import random
vals = random.sample(range(100, 2**32-1), 4)
print('AWG_H1=' + str(vals[0]))
print('AWG_H2=' + str(vals[1]))
print('AWG_H3=' + str(vals[2]))
print('AWG_H4=' + str(vals[3]))
"
```

Diese 4 Werte notieren — sie kommen in Schritt 2.6 in die `.env`.

**Wichtig:** H1–H4 müssen unterschiedlich sein und > 4. Die WireGuard-Standardwerte (1, 2, 3, 4) deaktivieren die Obfuskation — russisches DPI erkennt dann den Traffic.

- [ ] **Schritt 2.4: Passwort für Web-UI wählen und hashen**

```bash
# Starkes Passwort wählen (mindestens 16 Zeichen), dann hashen:
docker run --rm ghcr.io/wg-easy/wg-easy wgpw 'DEIN_PASSWORT_HIER'
```

Erwartete Ausgabe: `PASSWORD_HASH='$2b$12$...'`

Den Hash (inkl. `$2b$...`) kopieren — kommt in Schritt 2.6.

**Falls das Image kein `wgpw` kennt** (ältere wg-easy Fork):
```bash
docker run --rm python:3-alpine python3 -c "import bcrypt; print(bcrypt.hashpw(b'DEIN_PASSWORT_HIER', bcrypt.gensalt(12)).decode())"
```

- [ ] **Schritt 2.5: Port 51820 freigeben (falls UFW aktiv)**

```bash
ufw status
# Falls aktiv:
ufw allow 51820/udp
ufw status | grep 51820
```

Erwartete Ausgabe: `51820/udp    ALLOW`

- [ ] **Schritt 2.6: `.env`-Datei erstellen**

```bash
cat > /docker/amneziavpn/.env << 'EOF'
WG_HOST=family.thunderbee.uk
WG_PORT=51820
WG_DEFAULT_DNS=1.1.1.1
WG_ALLOWED_IPS=0.0.0.0/0,::/0
WG_DEFAULT_ADDRESS=10.8.0.x
WG_MTU=1420
WG_PERSISTENT_KEEPALIVE=25
PASSWORD_HASH=$2b$12$HASH_AUS_SCHRITT_2_4_HIER_ERSETZEN
AWG_JC=4
AWG_JMIN=40
AWG_JMAX=70
AWG_S1=50
AWG_S2=100
AWG_H1=WERT_AUS_SCHRITT_2_3
AWG_H2=WERT_AUS_SCHRITT_2_3
AWG_H3=WERT_AUS_SCHRITT_2_3
AWG_H4=WERT_AUS_SCHRITT_2_3
EOF
chmod 600 /docker/amneziavpn/.env
```

**Danach:** Alle Platzhalter (`HASH_AUS_SCHRITT_2_4_HIER_ERSETZEN`, `WERT_AUS_SCHRITT_2_3`) durch echte Werte aus den vorherigen Schritten ersetzen.

Ergebnis prüfen:
```bash
cat /docker/amneziavpn/.env | grep -v HASH
```

---

## Task 3: docker-compose.yml schreiben

**Files:**
- Erstellen: `/docker/amneziavpn/docker-compose.yml`

- [ ] **Schritt 3.1: docker-compose.yml anlegen**

```bash
cat > /docker/amneziavpn/docker-compose.yml << 'EOF'
services:
  amneziavpn:
    image: eyrafir/amnezia-wg-easy:latest
    container_name: amneziavpn
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv4.conf.all.src_valid_mark=1
    env_file:
      - .env
    ports:
      - "0.0.0.0:51820:51820/udp"
      - "127.0.0.1:51821:51821/tcp"
    volumes:
      - ./data:/etc/wireguard
    restart: unless-stopped
EOF
```

- [ ] **Schritt 3.2: Konfig validieren**

```bash
cd /docker/amneziavpn && docker compose config
```

Erwartete Ausgabe: Gültige YAML-Konfiguration ohne Fehler.

---

## Task 4: Container starten & verifizieren

**Files:**
- Keine Änderungen — nur Betrieb

- [ ] **Schritt 4.1: Container starten**

```bash
cd /docker/amneziavpn && docker compose up -d
sleep 10
docker ps | grep amneziavpn
```

Erwartete Ausgabe: Zeile mit `amneziavpn` und Status `Up X seconds`.

- [ ] **Schritt 4.2: Container-Logs prüfen**

```bash
docker logs amneziavpn 2>&1 | tail -30
```

Auf Fehler achten. Typische Hinweise auf Erfolg:
- `Server is listening on port 51821`
- `WireGuard interface wg0 created` oder `amneziawg0 created`

**Falls Fehler mit AWG-Parametern:** Prüfen ob das Image die Env-Vars kennt. Falls nicht, AWG-Params aus `.env` entfernen und nach dem Start im Web-UI setzen (Settings → AmneziaWG Parameters).

- [ ] **Schritt 4.3: UDP-Port-Bindung verifizieren**

```bash
ss -ulnp | grep 51820
```

Erwartete Ausgabe: Zeile mit `0.0.0.0:51820` — Port ist direkt ans Interface gebunden, nicht nur localhost.

- [ ] **Schritt 4.4: Web-UI lokal erreichbar**

```bash
curl -sI http://127.0.0.1:51821/ | head -5
```

Erwartete Ausgabe: `HTTP/1.1 200 OK` oder `HTTP/1.1 302 Found` (Redirect zu Login).

- [ ] **Schritt 4.5: AWG-Interface im Container prüfen**

```bash
docker exec amneziavpn sh -c "ip link show | grep -E 'wg|awg'" 2>/dev/null
```

Erwartete Ausgabe: Interface `wg0` oder `awg0` — zeigt an, dass der VPN-Server aktiv lauscht.

---

## Task 5: Cloudflare Tunnel & DNS konfigurieren

**Wichtig:** Diese Schritte erfordern Zugriff auf das Cloudflare Zero Trust Dashboard (manuell im Browser).

**Files:**
- Keine lokalen Dateien

- [ ] **Schritt 5.1: DNS A-Record anlegen (Cloudflare Dashboard)**

1. Cloudflare Dashboard öffnen → `thunderbee.uk` → DNS
2. Record hinzufügen:
   - **Typ:** A
   - **Name:** `family`
   - **IPv4:** `76.13.45.58`
   - **Proxy-Status:** **Grauer Strich (DNS only)** — NICHT orange! Cloudflare darf UDP-Traffic nicht proxyen.
3. Speichern

Verifizieren (nach max. 2 Minuten Propagation):
```bash
dig +short family.thunderbee.uk
```
Erwartete Ausgabe: `76.13.45.58`

- [ ] **Schritt 5.2: Cloudflare Tunnel Eintrag für Web-UI hinzufügen**

1. Cloudflare Zero Trust Dashboard → Networks → Tunnels
2. Bestehenden Tunnel auswählen (derselbe wie für andere Dienste)
3. „Edit" → „Public Hostnames" → „Add a public hostname":
   - **Subdomain:** `family-admin`
   - **Domain:** `thunderbee.uk`
   - **Service Type:** HTTP
   - **URL:** `localhost:51821`
4. Speichern

- [ ] **Schritt 5.3: Web-UI via Cloudflare-Domain testen**

```bash
curl -sI https://family-admin.thunderbee.uk/ | head -5
```

Erwartete Ausgabe: `HTTP/1.1 200 OK` — Web-UI ist via HTTPS erreichbar.

**Falls 502 Bad Gateway:** Cloudflared-Logs prüfen:
```bash
sudo journalctl -u cloudflared -f --since "1 min ago"
```

---

## Task 6: Ersten VPN-Client anlegen & testen

**Files:**
- Keine Dateien

- [ ] **Schritt 6.1: Im Web-UI einloggen**

Browser öffnen: `https://family-admin.thunderbee.uk`

Mit dem Passwort aus Task 2 einloggen.

- [ ] **Schritt 6.2: AWG-Parameter im Web-UI prüfen**

Falls das Image AWG-Params nicht aus Env-Vars liest (Task 1, Schritt 1.2 ergab keine AWG-Env-Vars):

1. Settings → AmneziaWG Parameters öffnen
2. Folgende Werte eintragen (eigene zufällige H1–H4 aus Task 2 Schritt 2.3 verwenden!):
   - Jc: `4`
   - Jmin: `40`
   - Jmax: `70`
   - S1: `50`
   - S2: `100`
   - H1: (Wert aus Schritt 2.3)
   - H2: (Wert aus Schritt 2.3)
   - H3: (Wert aus Schritt 2.3)
   - H4: (Wert aus Schritt 2.3)
3. Speichern — Container startet WireGuard-Interface neu

- [ ] **Schritt 6.3: Test-Client anlegen**

1. „+ New Client" klicken
2. Name: `test-lokal`
3. Client anlegen — QR-Code und `.conf`-Download erscheinen

- [ ] **Schritt 6.4: `.conf`-Datei herunterladen und Inhalt prüfen**

Die `.conf`-Datei muss AWG-Parameter enthalten (nicht nur Standard-WireGuard-Felder):

```
[Interface]
PrivateKey = ...
Address = 10.8.0.2/32
DNS = 1.1.1.1
Jc = 4
Jmin = 40
Jmax = 70
S1 = 50
S2 = 100
H1 = (zufälliger Wert)
H2 = (zufälliger Wert)
...

[Peer]
PublicKey = ...
Endpoint = family.thunderbee.uk:51820
AllowedIPs = 0.0.0.0/0, ::/0
```

**Falls keine `Jc`/`H1`-Zeilen in der Config:** AWG-Parameter wurden nicht korrekt gesetzt → Schritt 6.2 wiederholen, dann neuen Client anlegen.

- [ ] **Schritt 6.5: VPN-Verbindung lokal testen (vom VPS)**

```bash
# .conf-Datei temporär auf den VPS kopieren (aus Web-UI herunterladen)
# AWG-Tools prüfen ob im Container verfügbar:
docker exec amneziavpn sh -c "awg show" 2>/dev/null || docker exec amneziavpn sh -c "wg show" 2>/dev/null
```

Erwartete Ausgabe: Interface-Status mit Peer-Zähler.

- [ ] **Schritt 6.6: Test-Client aufräumen, echte Clients anlegen**

1. `test-lokal` löschen
2. Für jeden Freund einen Client anlegen: z.B. `masha-iphone`, `ivan-android`
3. QR-Codes per sicheren Kanal teilen (Signal, iMessage)

---

## Task 7: Firewall & Sicherheitscheck

**Files:**
- Keine

- [ ] **Schritt 7.1: Port-Exposition final verifizieren**

```bash
echo "=== VPN-Port (UDP, direkt exposed) ==="
ss -ulnp | grep 51820

echo "=== Web-UI (TCP, nur localhost) ==="
ss -tlnp | grep 51821

echo "=== Kein direkter Web-Zugriff von außen möglich ==="
curl -sf --max-time 3 http://76.13.45.58:51821/ && echo "FEHLER: Port von außen erreichbar!" || echo "OK: Port nicht von außen erreichbar"
```

Erwartete Ausgabe:
- UDP 51820: `0.0.0.0:51820` (direkt exposed — korrekt für VPN)
- TCP 51821: `127.0.0.1:51821` (nur localhost — korrekt)
- HTTP-Test schlägt fehl (Timeout) — korrekt

- [ ] **Schritt 7.2: DNS-only Cloudflare prüfen**

```bash
dig family.thunderbee.uk | grep -E "ANSWER|76\.13"
```

Erwartete Ausgabe: Direkte IP `76.13.45.58` — keine Cloudflare-Proxy-IPs (104.x.x.x).

Falls Cloudflare-Proxy-IPs erscheinen: Im Cloudflare-Dashboard sicherstellen, dass der A-Record `family` auf „DNS only" (grauer Strich) steht, nicht auf „Proxied" (orange).

- [ ] **Schritt 7.3: Abschlussdokumentation**

```bash
echo "=== AmneziaVPN Setup Zusammenfassung ==="
echo "VPN-Endpunkt:      family.thunderbee.uk:51820 (UDP)"
echo "Admin-UI:          https://family-admin.thunderbee.uk"
echo "Container:         $(docker ps --filter name=amneziavpn --format '{{.Status}}')"
echo "Protokoll:         AmneziaWG (AWG)"
echo "Client-Apps:"
echo "  iOS (Russland):  DefaultVPN (App Store)"
echo "  Android:         AmneziaWG (Google Play)"
echo "  Windows/macOS:   AmneziaVPN (amnezia.org)"
```

---

## Hinweise für Freunde (Onboarding)

Freunden folgende Informationen mitteilen:

**iOS (Russland):** App „DefaultVPN" im App Store installieren → „+" → QR-Code scannen oder .conf-Datei importieren → Verbinden

**Android:** App „AmneziaWG" bei Google Play installieren → „+" → QR-Code scannen → Verbinden

**Windows/macOS:** AmneziaVPN von amnezia.org herunterladen → Server hinzufügen → .conf-Datei importieren

**Wichtig:** Full-Tunnel ist aktiv — der gesamte Internettraffic läuft über den VPS, sobald VPN aktiv ist.
