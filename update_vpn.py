import requests
import base64
import json
import sys
import re


# ============================================================
# API ENDPOINTS
# ============================================================

VPNGATE_CSV_URL = "http://www.vpngate.net/api/iphone/"

TELEXY_TCP_URL = (
    "https://telexy.net/api/v1/vpn"
    "?transport=tcp&sort=ping&limit=300"
)

TELEXY_UDP_URL = (
    "https://telexy.net/api/v1/vpn"
    "?transport=udp&sort=ping&limit=300"
)


# ============================================================
# HTTP HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Linux; Android 15) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Mobile Safari/537.36"
    ),
    "Accept": "*/*"
}


# ============================================================
# BASE64 ENCODING
# ============================================================

def encode_ovpn_config(config):
    """
    Encode a plain-text OVPN configuration to Base64.
    """

    if not config:
        return ""

    try:
        config = str(config).strip()

        if not config:
            return ""

        encoded = base64.b64encode(
            config.encode("utf-8")
        ).decode("ascii")

        return encoded

    except Exception as e:
        print(f"Base64 encoding error: {e}")
        return ""


# ============================================================
# NORMALIZE PROTOCOL
# ============================================================

def normalize_protocol(protocol):
    """
    Normalize protocol values.

    Examples:
        tcp      -> tcp
        tcp4     -> tcp
        tcp-client -> tcp
        udp      -> udp
        udp4     -> udp
    """

    if not protocol:
        return ""

    protocol = str(protocol).lower().strip()

    if "tcp" in protocol:
        return "tcp"

    if "udp" in protocol:
        return "udp"

    return ""


# ============================================================
# DETECT PROTOCOL FROM OVPN CONFIG
# ============================================================

def detect_protocol_from_ovpn(config):
    """
    Detect TCP or UDP from an OVPN configuration.
    """

    if not config:
        return ""

    try:
        text = str(config).lower()

        if re.search(
            r"^\s*proto\s+tcp",
            text,
            re.MULTILINE
        ):
            return "tcp"

        if re.search(
            r"^\s*proto\s+udp",
            text,
            re.MULTILINE
        ):
            return "udp"

    except Exception:
        pass

    return ""


# ============================================================
# EXTRACT REMOTE HOST AND PORT
# ============================================================

def extract_remote(config):
    """
    Extract the remote host and port from an OVPN config.
    """

    if not config:
        return "", ""

    try:
        match = re.search(
            r"^\s*remote\s+([^\s]+)\s+([0-9]+)",
            config,
            re.MULTILINE | re.IGNORECASE
        )

        if match:
            host = match.group(1).strip()
            port = match.group(2).strip()

            return host, port

    except Exception:
        pass

    return "", ""


# ============================================================
# CLEAN OVPN CONFIGURATION
# ============================================================

def clean_ovpn_config(config):
    """
    Remove configuration lines that may cause compatibility
    problems with older OpenVPN libraries.
    """

    if not config:
        return ""

    try:
        lines = config.splitlines()
        cleaned = []

        for line in lines:

            stripped = line.strip()

            # Remove data-ciphers AES-128-CBC line.
            if stripped.lower().startswith("data-ciphers "):

                if "AES-128-CBC" in stripped.upper():
                    continue

            cleaned.append(line)

        return "\n".join(cleaned).strip()

    except Exception:
        return config


# ============================================================
# UNIQUE SERVER KEY
# ============================================================

def make_unique_key(ip, protocol):
    """
    Create a unique key using IP + protocol.

    This allows the same IP to have both TCP and UDP entries.
    """

    return (
        str(ip).strip().lower()
        + "|"
        + str(protocol).strip().lower()
    )


# ============================================================
# FETCH VPN GATE SERVERS
# ============================================================

def fetch_vpngate_csv(existing_keys):

    configs = []

    try:

        print("Fetching VPN Gate servers...")

        response = requests.get(
            VPNGATE_CSV_URL,
            headers=HEADERS,
            timeout=20
        )

        print(
            f"VPN Gate HTTP status: "
            f"{response.status_code}"
        )

        if response.status_code != 200:
            print("VPN Gate request failed.")
            return configs

        lines = response.text.splitlines()

        for line in lines:

            try:

                # Skip comments and empty lines.
                if (
                    line.startswith("#")
                    or line.startswith("*")
                    or not line.strip()
                ):
                    continue

                parts = line.split(",")

                if len(parts) < 15:
                    continue

                # VPN Gate CSV fields.
                ip = parts[1].strip()
                score = parts[2].strip()
                ping = parts[3].strip()
                speed = parts[4].strip()
                country = parts[5].strip()
                country_code = parts[6].strip()
                base64_config = parts[14].strip()

                if not ip or not base64_config:
                    continue

                # VPN Gate provides the OVPN configuration
                # as Base64.
                #
                # Decode it temporarily only to inspect and
                # clean the configuration.
                try:
                    ovpn_config = base64.b64decode(
                        base64_config,
                        validate=False
                    ).decode(
                        "utf-8",
                        errors="ignore"
                    )

                except Exception:
                    continue

                if not ovpn_config.strip():
                    continue

                # Clean configuration.
                ovpn_config = clean_ovpn_config(
                    ovpn_config
                )

                # Detect protocol.
                protocol = detect_protocol_from_ovpn(
                    ovpn_config
                )

                if not protocol:
                    continue

                # Create unique key.
                unique_key = make_unique_key(
                    ip,
                    protocol
                )

                if unique_key in existing_keys:
                    continue

                # Extract remote port.
                remote_host, remote_port = extract_remote(
                    ovpn_config
                )

                # Encode cleaned OVPN configuration.
                encoded_config = encode_ovpn_config(
                    ovpn_config
                )

                if not encoded_config:
                    continue

                server = {
                    "ip": ip,
                    "port": remote_port,
                    "country": country,
                    "country_code": country_code.upper(),
                    "protocol": protocol,
                    "ping": ping,
                    "speed": speed,
                    "score": score,
                    "source": "vpngate",
                    "ovpn_config": encoded_config
                }

                configs.append(server)

                existing_keys.add(unique_key)

            except Exception:
                continue

    except Exception as e:

        print(
            f"VPN Gate error: {e}"
        )

    print(
        f"VPN Gate servers collected: "
        f"{len(configs)}"
    )

    return configs


# ============================================================
# FETCH TELEXy SERVERS
# ============================================================

def fetch_telexy_json(
    url,
    default_protocol,
    existing_keys
):

    configs = []

    try:

        print(
            f"Fetching Telexy "
            f"{default_protocol.upper()} servers..."
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        print(
            f"Telexy HTTP status: "
            f"{response.status_code}"
        )

        if response.status_code != 200:
            print(
                f"Telexy {default_protocol.upper()} "
                f"request failed."
            )
            return configs

        data = response.json()

        # Handle different possible API response formats.
        if isinstance(data, list):

            items = data

        elif isinstance(data, dict):

            items = (
                data.get("data")
                or data.get("results")
                or data.get("servers")
                or []
            )

        else:

            items = []

        if not isinstance(items, list):
            return configs

        for item in items:

            try:

                if not isinstance(item, dict):
                    continue

                # ------------------------------------------------
                # IP ADDRESS
                # ------------------------------------------------

                ip = str(
                    item.get("ip")
                    or item.get("ip_address")
                    or item.get("host")
                    or ""
                ).strip()

                if not ip:
                    continue

                # ------------------------------------------------
                # PROTOCOL
                # ------------------------------------------------

                protocol = normalize_protocol(
                    item.get("transport")
                    or item.get("protocol")
                    or default_protocol
                )

                if not protocol:
                    protocol = default_protocol

                # ------------------------------------------------
                # OVPN CONFIGURATION
                # ------------------------------------------------

                raw_config = (
                    item.get("ovpn_config")
                    or item.get("config")
                    or item.get("ovpn")
                    or item.get("openvpn")
                    or ""
                )

                if not raw_config:
                    continue

                raw_config = str(
                    raw_config
                ).strip()

                # ------------------------------------------------
                # CHECK WHETHER CONFIG IS ALREADY BASE64
                # ------------------------------------------------

                is_base64 = False

                try:

                    test_base64 = re.sub(
                        r"\s+",
                        "",
                        raw_config
                    )

                    decoded = base64.b64decode(
                        test_base64,
                        validate=True
                    )

                    decoded_text = decoded.decode(
                        "utf-8",
                        errors="ignore"
                    )

                    if (
                        "client" in decoded_text.lower()
                        or "remote " in decoded_text.lower()
                        or "proto " in decoded_text.lower()
                        or "<ca>" in decoded_text.lower()
                    ):
                        is_base64 = True

                except Exception:
                    is_base64 = False

                # ------------------------------------------------
                # ALREADY BASE64
                # ------------------------------------------------

                if is_base64:

                    encoded_config = re.sub(
                        r"\s+",
                        "",
                        raw_config
                    )

                    # Detect protocol from decoded config.
                    try:

                        decoded_config = (
                            base64.b64decode(
                                encoded_config
                            ).decode(
                                "utf-8",
                                errors="ignore"
                            )
                        )

                        detected_protocol = (
                            detect_protocol_from_ovpn(
                                decoded_config
                            )
                        )

                        if detected_protocol:
                            protocol = detected_protocol

                    except Exception:
                        pass

                # ------------------------------------------------
                # PLAIN TEXT OVPN
                # ------------------------------------------------

                else:

                    clean_config = clean_ovpn_config(
                        raw_config
                    )

                    detected_protocol = (
                        detect_protocol_from_ovpn(
                            clean_config
                        )
                    )

                    if detected_protocol:
                        protocol = detected_protocol

                    encoded_config = encode_ovpn_config(
                        clean_config
                    )

                if not encoded_config:
                    continue

                # ------------------------------------------------
                # UNIQUE KEY
                # ------------------------------------------------

                unique_key = make_unique_key(
                    ip,
                    protocol
                )

                if unique_key in existing_keys:
                    continue

                # ------------------------------------------------
                # SERVER INFORMATION
                # ------------------------------------------------

                country = str(
                    item.get("country")
                    or item.get("country_name")
                    or "Unknown"
                ).strip()

                country_code = str(
                    item.get("country_code")
                    or item.get("country_short")
                    or "XX"
                ).strip().upper()

                ping = str(
                    item.get("ping")
                    or item.get("latency")
                    or 0
                ).strip()

                speed = str(
                    item.get("speed")
                    or item.get("download_speed")
                    or 0
                ).strip()

                score = str(
                    item.get("score")
                    or 0
                ).strip()

                port = str(
                    item.get("port")
                    or item.get("server_port")
                    or ""
                ).strip()

                server = {
                    "ip": ip,
                    "port": port,
                    "country": country,
                    "country_code": country_code,
                    "protocol": protocol,
                    "ping": ping,
                    "speed": speed,
                    "score": score,
                    "source": "telexy",
                    "ovpn_config": encoded_config
                }

                configs.append(server)

                existing_keys.add(unique_key)

            except Exception:
                continue

    except Exception as e:

        print(
            f"Telexy {default_protocol.upper()} "
            f"error: {e}"
        )

    print(
        f"Telexy {default_protocol.upper()} "
        f"servers collected: {len(configs)}"
    )

    return configs


# ============================================================
# CONVERT VALUE TO NUMBER
# ============================================================

def numeric_value(value):

    try:

        if value is None:
            return 0

        text = str(value)

        match = re.search(
            r"[-+]?[0-9]*\.?[0-9]+",
            text
        )

        if match:
            return float(
                match.group(0)
            )

    except Exception:
        pass

    return 0


# ============================================================
# MAIN
# ============================================================

def main():

    all_configs = []

    # Track IP + protocol instead of IP only.
    # Therefore:
    #
    # 1.2.3.4 + TCP
    # 1.2.3.4 + UDP
    #
    # can both exist.
    seen_keys = set()

    # ========================================================
    # VPN GATE
    # ========================================================

    vpngate_servers = fetch_vpngate_csv(
        seen_keys
    )

    all_configs.extend(
        vpngate_servers
    )

    # ========================================================
    # TELEXy TCP
    # ========================================================

    telexy_tcp_servers = fetch_telexy_json(
        TELEXY_TCP_URL,
        "tcp",
        seen_keys
    )

    all_configs.extend(
        telexy_tcp_servers
    )

    # ========================================================
    # TELEXy UDP
    # ========================================================

    telexy_udp_servers = fetch_telexy_json(
        TELEXY_UDP_URL,
        "udp",
        seen_keys
    )

    all_configs.extend(
        telexy_udp_servers
    )

    # ========================================================
    # CHECK RESULTS
    # ========================================================

    if not all_configs:

        print("No VPN configurations were collected.")

        sys.exit(1)

    # ========================================================
    # NORMALIZE PROTOCOLS
    # ========================================================

    for server in all_configs:

        server["protocol"] = normalize_protocol(
            server.get("protocol")
        )

    # ========================================================
    # SEPARATE TCP AND UDP
    # ========================================================

    tcp_servers = [
        server
        for server in all_configs
        if server.get("protocol") == "tcp"
    ]

    udp_servers = [
        server
        for server in all_configs
        if server.get("protocol") == "udp"
    ]

    # ========================================================
    # SORT BY PING
    # ========================================================

    tcp_servers.sort(
        key=lambda server: numeric_value(
            server.get("ping")
        )
    )

    udp_servers.sort(
        key=lambda server: numeric_value(
            server.get("ping")
        )
    )

    all_configs.sort(
        key=lambda server: numeric_value(
            server.get("ping")
        )
    )

    # ========================================================
    # SAVE TCP JSON
    # ========================================================

    with open(
        "tcp.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            tcp_servers,
            file,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # SAVE UDP JSON
    # ========================================================

    with open(
        "udp.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            udp_servers,
            file,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # SAVE ALL JSON
    # ========================================================

    with open(
        "all.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            all_configs,
            file,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 50)
    print("VPN SERVER UPDATE SUMMARY")
    print("=" * 50)

    print(
        f"Total servers : {len(all_configs)}"
    )

    print(
        f"TCP servers   : {len(tcp_servers)}"
    )

    print(
        f"UDP servers   : {len(udp_servers)}"
    )

    print()
    print("Generated files:")

    print(
        f"  tcp.json  -> {len(tcp_servers)} servers"
    )

    print(
        f"  udp.json  -> {len(udp_servers)} servers"
    )

    print(
        f"  all.json  -> {len(all_configs)} servers"
    )

    print("=" * 50)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
