import requests
import base64
import json
import sys

# API Endpoints
VPNGATE_CSV_URL = "http://www.vpngate.net/api/iphone/"
TELEXY_TCP_URL = "https://telexy.net/api/v1/vpn?transport=tcp&sort=ping&limit=300"
TELEXY_UDP_URL = "https://telexy.net/api/v1/vpn?transport=udp&sort=ping&limit=300"


def fetch_vpngate_csv(existing_ips):
    """
    VPN Gate CSV API থেকে OVPN ফেচ ও পার্স করে।
    """
    configs = []
    try:
        print("Fetching from VPN Gate CSV API...")
        res = requests.get(VPNGATE_CSV_URL, timeout=15)
        if res.status_code != 200:
            return configs

        lines = res.text.splitlines()
        for line in lines:
            if line.startswith("#") or line.startswith("*") or not line.strip():
                continue

            parts = line.split(",")
            if len(parts) >= 15 and parts[14]:
                try:
                    ip = parts[1].strip()
                    if ip in existing_ips:
                        continue

                    score = parts[2].strip()
                    ping = parts[3].strip()
                    speed = parts[4].strip()
                    country_long = parts[5].strip()
                    country_short = parts[6].strip()
                    b64_config = parts[14].strip()

                    ovpn_raw = base64.b64decode(b64_config).decode("utf-8", errors="ignore")

                    ovpn_lower = ovpn_raw.lower()
                    protocol = "tcp" if "proto tcp" in ovpn_lower else "udp"

                    configs.append({
                        "ip": ip,
                        "country": country_long,
                        "country_code": country_short,
                        "protocol": protocol,
                        "ping": ping,
                        "speed": speed,
                        "score": score,
                        "ovpn_config": ovpn_raw
                    })
                    existing_ips.add(ip)
                except Exception:
                    continue
    except Exception as e:
        print(f"VPN Gate error: {e}")

    return configs


def fetch_telexy_json(url, default_proto, existing_ips):
    """
    Telexy JSON REST API থেকে OVPN ফেচ ও পার্স করে।
    """
    configs = []
    try:
        print(f"Fetching from Telexy API ({default_proto.upper()})...")
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            return configs

        data = res.json()
        items = data if isinstance(data, list) else data.get("data", data.get("results", []))

        for item in items:
            try:
                ip = str(item.get("ip") or item.get("ip_address") or "").strip()
                if not ip or ip in existing_ips:
                    continue

                country = str(item.get("country") or item.get("country_name") or "Unknown").strip()
                country_code = str(item.get("country_code") or item.get("country_short") or "XX").strip()
                ping = str(item.get("ping") or item.get("latency") or "0")
                speed = str(item.get("speed") or "0")
                score = str(item.get("score") or "0")

                # OVPN Config বের করা (ব্যাসসিক বা প্লেইন টেক্সট)
                raw_config = item.get("ovpn_config") or item.get("config") or item.get("ovpn") or ""
                
                # যদি Base64 ফরম্যাটে থাকে
                if raw_config and not raw_config.startswith("client") and not raw_config.startswith("#"):
                    try:
                        raw_config = base64.b64decode(raw_config).decode("utf-8", errors="ignore")
                    except Exception:
                        pass

                if not raw_config:
                    continue

                proto = str(item.get("transport") or item.get("protocol") or default_proto).lower()

                configs.append({
                    "ip": ip,
                    "country": country,
                    "country_code": country_code,
                    "protocol": proto,
                    "ping": ping,
                    "speed": speed,
                    "score": score,
                    "ovpn_config": raw_config
                })
                existing_ips.add(ip)
            except Exception:
                continue
    except Exception as e:
        print(f"Telexy error ({default_proto}): {e}")

    return configs


def main():
    all_configs = []
    seen_ips = set()

    # ১. VPN Gate CSV থেকে ডাটা নেওয়া
    vpngate_data = fetch_vpngate_csv(seen_ips)
    all_configs.extend(vpngate_data)

    # ২. Telexy TCP API থেকে ডাটা নেওয়া
    telexy_tcp = fetch_telexy_json(TELEXY_TCP_URL, "tcp", seen_ips)
    all_configs.extend(telexy_tcp)

    # ৩. Telexy UDP API থেকে ডাটা নেওয়া
    telexy_udp = fetch_telexy_json(TELEXY_UDP_URL, "udp", seen_ips)
    all_configs.extend(telexy_udp)

    if not all_configs:
        print("No configs fetched!")
        sys.exit(1)

    # TCP এবং UDP ভাগ করা
    tcp_configs = [c for c in all_configs if c["protocol"] == "tcp"]
    udp_configs = [c for c in all_configs if c["protocol"] == "udp"]

    # JSON ফাইল সেভ করা
    with open("tcp.json", "w", encoding="utf-8") as f:
        json.dump(tcp_configs, f, indent=2, ensure_ascii=False)

    with open("udp.json", "w", encoding="utf-8") as f:
        json.dump(udp_configs, f, indent=2, ensure_ascii=False)

    with open("all.json", "w", encoding="utf-8") as f:
        json.dump(all_configs, f, indent=2, ensure_ascii=False)

    print("\n--- Summary ---")
    print(f"Total Unique Configs: {len(all_configs)}")
    print(f"TCP Saved : {len(tcp_configs)} -> tcp.json")
    print(f"UDP Saved : {len(udp_configs)} -> udp.json")
    print(f"All Saved : {len(all_configs)} -> all.json")


if __name__ == "__main__":
    main()
