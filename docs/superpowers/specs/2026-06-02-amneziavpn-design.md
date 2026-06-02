# AmneziaVPN Docker Container — Design Spec

**Datum:** 2026-06-02  
**Status:** Zur Überprüfung  

---

## Ziel

Einen ressourcenschonenden AmneziaVPN-Server als Docker-Container auf dem VPS einrichten, damit Freunde in Russland (wo Standard-VPN-Protokolle per DPI blockiert werden) über den VPS auf FaceTime, iMessage, WhatsApp und ähnliche Dienste zugreifen können.

---

## Kontext & Einschränkungen

- **Server:** VPS mit 8 GB RAM, 2 CPUs, 25 GB freier Disk
- **Freunde nutzen:** DefaultVPN (iOS, russischer App Store) bzw. AmneziaWG (Android) — beides offizielle Amnezia-Clients, technisch identisch
- **Protokoll:** AmneziaWG (AWG) — WireGuard mit Junk-Paket-Obfuskation, umgeht russisches DPI
- **Clients:** 4–10 Geräte
- **Traffic:** Full-Tunnel (gesamter Traffic über VPS) — nötig für Apple-Dienste (FaceTime, iMessage pinnen auf ihre IPs)
- **Client-Modus** (Verbindung zu externem Exit-Node) wird später als separater Container nachgerüstet

---

## Architektur

```
Freund in Russland (DefaultVPN/AmneziaWG App)
    │
    │  UDP 51820 — AWG-Protokoll (obfuskiert, DPI-resistent)
    ▼
family.thunderbee.uk → VPS öffentliche IP
    │
    ▼
[amneziavpn Container — amneziawg-easy]
    │  NAT/Masquerading (iptables)
    ▼
Internet: Apple-Server, WhatsApp, etc.

Admin (du)
    │  HTTPS via Cloudflare Tunnel
    ▼
family-admin.thunderbee.uk → localhost:51821
    │
    ▼
[Web-UI: Client-Verwaltung, QR-Codes, Config-Export]
```

---

## Komponenten

### Docker-Container: `amneziavpn`

- **Image:** `eyrafir/amnezia-wg-easy` (Community-Fork, zuletzt aktualisiert Jan 2026, 31 MB, nutzt `amneziawg-go` im Userspace — kein AmneziaWG-Kernelmodul auf dem Host nötig)
- **Hinweis Kernel:** Das offizielle `ghcr.io/wg-easy/wg-easy` unterstützt AWG ab v15 via `EXPERIMENTAL_AWG=true`, benötigt aber das AmneziaWG-Kernelmodul (DKMS-Build schlägt auf Kernel 6.8 fehl — bekannter Upstream-Bug). Der `eyrafir`-Fork umgeht das durch userspace AWG.
- **Verzeichnis:** `/docker/amneziavpn/`
- **Volumes:** `./data:/etc/wireguard` (Config-Files persistent auf Host)

### Ports

| Port | Bindung | Zweck |
|------|---------|-------|
| `51820/udp` | `0.0.0.0:51820` | VPN-Traffic — direkt exposed (kein Cloudflare, da UDP) |
| `51821/tcp` | `127.0.0.1:51821` | Web-UI — nur localhost, via Cloudflare Tunnel |

### DNS

- **`family.thunderbee.uk`** — A-Record → VPS-IP, Cloudflare-Proxy **deaktiviert** (grauer Strich / DNS-only), damit UDP-Traffic direkt zur VPS-IP geht
- **`family-admin.thunderbee.uk`** — Cloudflare Tunnel → `localhost:51821` (HTTPS, Proxy aktiv)

---

## Konfiguration (docker-compose.yml)

```yaml
services:
  amneziavpn:
    image: ghcr.io/w6d-io/amneziawg-easy
    container_name: amneziavpn
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv4.conf.all.src_valid_mark=1
    environment:
      - WG_HOST=family.thunderbee.uk
      - PASSWORD_HASH=<bcrypt-hash>          # Web-UI Passwort
      - WG_PORT=51820
      - WG_DEFAULT_DNS=1.1.1.1              # Cloudflare DNS (in Russland erreichbar)
      - WG_ALLOWED_IPS=0.0.0.0/0,::/0       # Full-Tunnel
      # AWG-Obfuskationsparameter für Russland (DPI-resistent)
      # H1-H4: zufällige große uint32-Werte, NICHT 1/2/3/4 (das sind WireGuard-Defaults = keine Obfuskation!)
      # S1/S2: Junk-Bytes vor/nach Handshake, NICHT 0
      - AWG_JC=4
      - AWG_JMIN=40
      - AWG_JMAX=70
      - AWG_S1=50
      - AWG_S2=100
      - AWG_H1=1397921220
      - AWG_H2=1397921221
      - AWG_H3=1397921222
      - AWG_H4=1397921223
      # Wichtig bei Implementierung: eigene zufällige H1-H4 generieren (python3 -c "import random; [print(random.randint(5,2**32-1)) for _ in range(4)]")
    ports:
      - "0.0.0.0:51820:51820/udp"
      - "127.0.0.1:51821:51821/tcp"
    volumes:
      - ./data:/etc/wireguard
    restart: unless-stopped
```

**Hinweis zu AWG-Parametern:** H1–H4 müssen zufällige uint32-Werte > 4 sein und voneinander verschieden. Die Standard-WireGuard-Werte (1/2/3/4) deaktivieren die Obfuskation effektiv — russisches DPI würde den Traffic erkennen. S1/S2 ungleich 0 fügt Junk-Bytes hinzu. Bei Implementierung eigene Zufallswerte generieren (Befehl im Compose-Kommentar). Die Env-Var-Namen (`AWG_JC`, `AWG_H1` etc.) müssen bei Implementierung gegen das tatsächliche eyrafir-Image verifiziert werden.

---

## Host-Voraussetzung

IP-Forwarding muss auf dem Host dauerhaft aktiviert sein:

```bash
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p
```

(Wird im Container über `sysctls` gesetzt, aber Host-Einstellung ist robuster bei Kernel-Upgrades.)

**Kein AmneziaWG-Kernelmodul nötig:** Da `eyrafir/amnezia-wg-easy` `amneziawg-go` im Userspace verwendet, ist keine DKMS-Installation erforderlich. Auf Kernel 6.8 (Ubuntu 24.04) schlägt der DKMS-Build von `amneziawg-linux-kernel-module` ohne manuelle Kernel-Quellen-Verlinkung fehl.

---

## Sicherheit

| Aspekt | Maßnahme |
|--------|----------|
| Web-UI | Nur via Cloudflare Tunnel erreichbar, Passwort-geschützt (bcrypt) |
| VPN-Port | UDP 51820 direkt exposed — unvermeidlich für VPN-Funktion |
| Config-Files | In `/docker/amneziavpn/data/` — nur root lesbar |
| DNS für Clients | 1.1.1.1 (nicht zensiert, kein russischer DNS-Resolver) |
| Protokoll | AWG-Obfuskation verhindert DPI-Erkennung |

---

## Client-Onboarding (für Freunde)

1. Du öffnest `https://family-admin.thunderbee.uk` im Browser
2. Neuen Client anlegen: Name z.B. "Masha-iPhone"
3. QR-Code anzeigen oder `.conf`-Datei exportieren
4. Freund installiert die passende App:
   - **iOS (Russland):** DefaultVPN — App Store (offizielle Amnezia-App unter anderem Namen)
   - **Android:** AmneziaWG — Google Play
   - **Windows/macOS:** AmneziaVPN — direkt von amnezia.org
5. Config via QR-Code scannen oder `.conf`-Datei importieren — verbunden

---

## Ressourcenverbrauch

- **RAM:** ~20–30 MB idle, ~5 MB pro aktivem Client
- **CPU:** Minimal (WireGuard läuft als Kernel-Modul, nicht im Userspace)
- **Disk:** <10 MB Config-Files

---

## Spätere Erweiterung: Client-Modus

Wenn ein externer Exit-Node gewünscht wird (anderer VPS in anderer Region), wird ein zweiter Container als AWG-Client konfiguriert. Dieser Container routet seinen Traffic über den externen Server, ohne den bestehenden Server-Container zu berühren. Die Container-Dienste, die über den Exit-Node gehen sollen, werden dem Netzwerk des Client-Containers hinzugefügt.

---

## Offene Punkte

- Konkreter bcrypt-Hash für Web-UI-Passwort — wird bei Implementierung generiert
- Cloudflare-Tunnel-Eintrag für `family-admin.thunderbee.uk` — wird bei Implementierung hinzugefügt
- DNS-A-Record `family.thunderbee.uk` — muss in Cloudflare manuell angelegt werden (DNS-only, kein Proxy)
