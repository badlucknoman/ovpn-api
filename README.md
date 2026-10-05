# VPN Server API

Automatically collects OpenVPN server configurations from multiple public VPN sources and generates ready-to-use JSON files.

## Features

- Fetches servers from VPN Gate
- Fetches TCP servers from Telexy
- Fetches UDP servers from Telexy
- Supports both TCP and UDP
- Removes duplicate servers using `IP + protocol`
- Keeps the same IP if it provides both TCP and UDP
- Detects OpenVPN protocol automatically
- Stores OVPN configurations as Base64
- Extracts server ports when available
- Includes country and country code
- Includes ping, speed, and score
- Sorts servers by ping
- Generates separate TCP and UDP JSON files
- Can be automated using GitHub Actions

## Data Sources

### VPN Gate

```text
http://www.vpngate.net/api/iphone/
```

### Telexy TCP

```text
https://telexy.net/api/v1/vpn?transport=tcp&sort=ping&limit=300
```

### Telexy UDP

```text
https://telexy.net/api/v1/vpn?transport=udp&sort=ping&limit=300
```

## Repository Structure

```text
.
├── update_vpn.py
├── tcp.json
├── udp.json
├── all.json
└── .github/
    └── workflows/
        └── update-vpn.yml
```

## Generated Files

### tcp.json

Contains OpenVPN servers using TCP.

### udp.json

Contains OpenVPN servers using UDP.

### all.json

Contains all collected TCP and UDP servers.

## OVPN Configuration

The `ovpn_config` field contains the OpenVPN configuration encoded with Base64.

Example:

```json
{
  "ip": "1.2.3.4",
  "port": "443",
  "country": "Japan",
  "country_code": "JP",
  "protocol": "tcp",
  "ping": "120",
  "speed": "15000000",
  "score": "100",
  "source": "vpngate",
  "ovpn_config": "Y2xpZW50CnByb3RvIHRjcAo..."
}
```

### Java / Android Example

```java
String encodedConfig = server.get("ovpn_config").toString();

String ovpnConfig = new String(
    android.util.Base64.decode(
        encodedConfig,
        android.util.Base64.DEFAULT
    ),
    "UTF-8"
);
```

## Duplicate Handling

The project uses `IP + Protocol` as the unique server identifier.

For example:

```text
1.2.3.4 + TCP
1.2.3.4 + UDP
```

are treated as two different servers.

## Sorting

Servers are sorted by ping, with lower ping appearing first.

## Running Locally

Install the dependency:

```bash
pip install requests
```

Run the script:

```bash
python update_vpn.py
```

The script generates:

```text
tcp.json
udp.json
all.json
```

## GitHub Actions

Create:

```text
.github/workflows/update-vpn.yml
```

Example:

```yaml
name: Update VPN Servers

on:
  schedule:
    - cron: "*/30 * * * *"

  workflow_dispatch:

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.x"

      - name: Install dependencies
        run: |
          pip install requests

      - name: Update VPN server data
        run: |
          python update_vpn.py

      - name: Commit updated JSON files
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

          git add tcp.json udp.json all.json

          git diff --cached --quiet || git commit -m "Update VPN server data"

      - name: Push changes
        run: |
          git push
```

## Automatic Updates

The workflow runs every 30 minutes and can also be started manually from:

```text
GitHub → Actions → Update VPN Servers → Run workflow
```

## Using the JSON Files

After GitHub Actions updates the repository, the JSON files can be accessed through GitHub Raw.

Example:

```text
https://raw.githubusercontent.com/badlucknoman/ovpn-api/main/tcp.json
```

```text
https://raw.githubusercontent.com/badlucknoman/ovpn-api/main/udp.json
```

```text
https://raw.githubusercontent.com/badlucknoman/ovpn-api/main/all.json
```

Replace `USERNAME` and `REPOSITORY` with your GitHub username and repository name.

## Android / Sketchware Flow

```text
GitHub JSON
    ↓
Download JSON
    ↓
Parse server information
    ↓
User selects server
    ↓
Read ovpn_config
    ↓
Base64 decode
    ↓
OpenVPN configuration
    ↓
Start OpenVPN
```

## Important Notes

The VPN configurations are collected from public sources.

Server availability, speed, ping, and reliability can change at any time.

A server appearing in the JSON file does not guarantee that it is currently online or that it will successfully establish a VPN connection.

Use third-party VPN configurations at your own discretion.

## License

This project is provided for educational and development purposes.

The project does not guarantee the availability, security, privacy, speed, or reliability of any third-party VPN server.
