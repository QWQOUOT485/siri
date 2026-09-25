# Network Architecture & Constraints

Answers: Why can iPhone connect from different floors?

### LAN Only (#1, #2)
- System only operates within LAN / Local Network
- Home/building use, approximately 1F to 4F with Wi-Fi
- No Internet control needed
- Architecture: iPhone → Siri → Apple Shortcuts → Home LAN/Wi-Fi → Windows Agent → Windows System Operations

### No Public Network Solutions (#2)
The Windows Agent remains LAN-only and must never accept public Internet control.

Spotify integration is one narrow exception for **outbound HTTPS only**: the Windows PC may initiate connections to Spotify Accounts / Spotify Web API for OAuth, catalog search, device discovery, and playback control. This does not expose the Agent port to the Internet.

Do NOT use:
- Tailscale / Tailscale Funnel
- Cloudflare Tunnel
- ngrok
- Public VPS
- Router Port Forwarding
- UPnP Port Mapping
- DDNS
- Public API
- Any method exposing Windows Agent to Internet

### Different Wi-Fi Does NOT Mean Can't Connect (#27, #84, #85)
Different floors may have:
- Different Wi-Fi names
- Different Access Points
- Different Mesh nodes
- Different IP subnets

As long as routing between subnets exists, it works.
Example: iPhone 192.168.20.30 → Windows 192.168.10.50, as long as Router/L3 switch allows 192.168.20.0/24 → 192.168.10.0/24.

Do NOT write 'must be on same 192.168.1.x'.

### Potential Connection Issues (#28)
- Guest Wi-Fi
- AP Isolation
- Client Isolation
- VLAN Isolation
- Inter-VLAN Firewall
- Windows Firewall
- Windows Network Profile = Public
- Wrong IP
- Server not started
- Wrong port
- Wi-Fi Router blocking LAN-to-LAN

### Cross-Floor Troubleshooting (#84)
'1F works but 4F doesn't?' Check:
1. Is 4F Wi-Fi a Guest Network?
2. AP Isolation enabled?
3. Different VLAN?
4. Router allows Inter-VLAN routing?
5. Windows Firewall allowed subnet?
6. IP correct?

### Windows IP Configuration (#29)
**Option A:** Windows hostname (e.g. `http://MY-PC:8000`) — works if DNS/mDNS/local hostname resolution is functional.

**Option B:** Fixed IP via Router DHCP Reservation (recommended over manual static IP for general users). Example: `192.168.10.50`.

### Optional: LAN Discovery (#30)
- Bonjour / mDNS / zeroconf for easier discovery (e.g. `windows-agent.local`)
- Optional feature only, not mandatory
- mDNS may not work across VLAN/subnet
- Fixed IP / DNS hostname must remain available

### FastAPI Server (#24)
- LAN server, must listen on LAN (not just 127.0.0.1)
- e.g. `0.0.0.0:8000`
- Combined with Windows Firewall restrictions

### Optional Local AI Runtime
- The LAN-facing Windows Agent and the optional LM Studio runtime are separate network boundaries.
- Production LM Studio access must bind to and use `http://127.0.0.1:<port>/v1` only; it must not listen on `0.0.0.0`, the Windows LAN address, or a public interface.
- A non-loopback LM Studio endpoint such as `192.168.0.199:1234` is permitted only for an explicitly isolated development/benchmark run, never as an automatic production fallback.
- The Agent must reject a non-loopback AI endpoint in production configuration rather than silently widening the exposure. The iPhone continues to call only the LAN-facing Agent API.

### Windows Firewall (#25, #26)
- TCP port (e.g. 8000)
- Private Profile only
- No Public Profile
- No Internet exposure
- If current profile is Public: warn, don't change
- Consider multi-subnet RFC1918 ranges (don't restrict to LocalSubnet only)
- `allowed_networks` configurable
- See [Security Model](SECURITY.md#firewall-security)

### HTTP vs HTTPS (#34)
- V1: HTTP (`http://WINDOWS-IP:8000`)
- LAN has no transport encryption
- Security relies on: trusted home network, Windows Firewall, API authentication, no Internet exposure, no Guest Wi-Fi, no arbitrary shell
- Optional HTTPS mode if easy to install without complicating iPhone certificate management
- Don't make installation overly complex for HTTPS

### Network Health Test (#83)
1. Start Windows Agent
2. On Windows: confirm `/health` works
3. From iPhone Safari: open `http://WINDOWS-IP:8000/health`
4. If 'Agent online' visible: network is OK
5. If Safari can't connect: troubleshoot LAN first, don't blame Siri Shortcut

### Inter-VLAN / Multi-Subnet (#85, #26)
- Windows = 192.168.1.50, iPhone = 192.168.20.25 — works if network routing allows it
- Firewall `allowed_networks` should cover 192.168.x.x, 10.x.x.x, 172.16-31.x.x
- Don't restrict to single subnet
