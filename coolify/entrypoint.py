#!/usr/bin/env python3
"""Prepare persistent world state, generate Caddy routing, and supervise Basis worlds."""
import ipaddress
import os
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

WORLD_FILE = Path(os.environ.get("WORLD_CONFIG", "/etc/basis/worlds.conf"))
DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/data"))
CADDY_FILE = Path(os.environ.get("CADDY_CONFIG", "/shared/caddy/Caddyfile"))
APP = Path("/opt/basis/BasisNetworkConsole.dll")
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
children = []


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        raise SystemExit(f"{name} must be an integer")


def read_worlds():
    if not WORLD_FILE.is_file():
        raise SystemExit(f"Missing worlds file: {WORLD_FILE}")
    worlds, slugs, ports = [], set(), set()
    for line_no, raw in enumerate(WORLD_FILE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split(None, 3)
        if len(fields) != 4:
            raise SystemExit(f"{WORLD_FILE}:{line_no}: expected <slug> <UDP port> <bundle> <display name>")
        slug, port_text, bundle, name = fields
        if not SLUG_RE.fullmatch(slug) or len(slug) > 40:
            raise SystemExit(f"{WORLD_FILE}:{line_no}: invalid slug {slug!r}")
        try:
            port = int(port_text)
        except ValueError:
            raise SystemExit(f"{WORLD_FILE}:{line_no}: invalid UDP port {port_text!r}")
        if not 1024 <= port <= 65535 or port in ports:
            raise SystemExit(f"{WORLD_FILE}:{line_no}: port must be unique and between 1024 and 65535")
        if slug in slugs:
            raise SystemExit(f"{WORLD_FILE}:{line_no}: duplicate slug {slug!r}")
        slugs.add(slug)
        ports.add(port)
        worlds.append({"slug": slug, "port": port, "bundle": bundle, "name": name})
    if not worlds:
        raise SystemExit("worlds.conf contains no worlds")
    if worlds[0]["port"] != 4296:
        print("WARNING: first world is the hub; keeping it on UDP 4296 is strongly recommended", flush=True)
    start, end = env_int("WORLD_PORT_START", 4296), env_int("WORLD_PORT_END", 4395)
    for world in worlds:
        if not start <= world["port"] <= end:
            raise SystemExit(f"world {world['slug']}: UDP port {world['port']} is outside published range {start}-{end}")
    return worlds


def bundle_url(bundle):
    if bundle.startswith("https://"):
        return bundle
    base = os.environ.get("CDN_BASE", "").rstrip("/")
    if not base:
        raise SystemExit(f"CDN_BASE is required for relative bundle {bundle!r}")
    return base + "/" + bundle.lstrip("/")


def write_world_config(world, index):
    slug = world["slug"]
    var = re.sub(r"[^A-Z0-9]", "_", slug.upper())
    password = os.environ.get("UNLOCK_PASSWORD_" + var) or os.environ.get("UNLOCK_PASSWORD", "")
    if not password:
        raise SystemExit(f"Set UNLOCK_PASSWORD or UNLOCK_PASSWORD_{var} in Coolify environment variables")
    root = DATA_ROOT / "worlds" / slug
    for folder in ("initialresources", "config/transports", "storage", "defaultlibrary"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    config = ET.Element("BasisLoadableConfiguration")
    values = {
        "Mode": "1", "LoadedNetID": slug, "UnlockPassword": password,
        "CombinedURL": bundle_url(world["bundle"]), "QuaternionW": "1",
        "ScaleX": "1", "ScaleY": "1", "ScaleZ": "1", "Persist": "true",
    }
    for key, value in values.items():
        ET.SubElement(config, key).text = value
    target = root / "initialresources" / "world.xml"
    target.write_bytes(ET.tostring(config, encoding="utf-8", xml_declaration=True))
    target.chmod(0o600)
    if os.environ.get("WEB_PLAYERS", "no").lower() == "yes":
        proxy_net = os.environ.get("PROXY_NET", "172.30.42.0/24")
        transport = ET.Element("BasisWebSocketTransportConfig")
        ET.SubElement(transport, "TrustedProxies").text = proxy_net
        transport_path = root / "config" / "transports" / "websocket.xml"
        transport_path.write_bytes(ET.tostring(transport, encoding="utf-8", xml_declaration=True))
    world.update({
        "root": root,
        "health_port": 10666 + index,
        "password": os.environ.get(var + "_PASSWORD", ""),
        "peer_limit": os.environ.get(var + "_PEER_LIMIT", "64"),
        "motd": os.environ.get(var + "_MOTD", ""),
        "api_key": os.environ.get(var + "_API_KEY", ""),
    })


def write_caddy(worlds):
    if os.environ.get("WEB_PLAYERS", "no").lower() != "yes":
        return
    zone = os.environ.get("DNS_ZONE", "").strip().rstrip(".").lower()
    if not zone or "." not in zone:
        raise SystemExit("WEB_PLAYERS=yes requires DNS_ZONE to be a real domain, e.g. worlds.example.com")
    host = os.environ.get("DNS_HOST", "vm1").strip().lower()
    if not re.fullmatch(r"[a-z0-9-]+", host):
        raise SystemExit("DNS_HOST must be a single DNS label")
    web_client = os.environ.get("WEB_CLIENT_URL", "").rstrip("/")
    proxy_ranges = os.environ.get("COOLIFY_PROXY_NET", "").split()
    for network in proxy_ranges:
        try:
            ipaddress.ip_network(network, strict=False)
        except ValueError:
            raise SystemExit(f"Invalid COOLIFY_PROXY_NET entry: {network}")
    lines = ["# TLS is terminated by the Coolify proxy; Caddy receives HTTP on its private service network.", "{", "  servers {", "    protocols h1 h2"]
    if proxy_ranges:
        lines.append("    trusted_proxies static " + " ".join(proxy_ranges))
        lines.append("    client_ip_headers X-Forwarded-For")
    lines.extend(["  }", "}", ""])
    for i, world in enumerate(worlds):
        slug, port = world["slug"], world["port"]
        names = [f"{slug}.{zone}"]
        if i == 0:
            names = [zone, f"{slug}.{zone}", f"{host}.{zone}"]
        lines.append(", ".join("http://" + name for name in names) + " {")
        if web_client:
            lines.extend([
                "  @webpage header Accept *text/html*",
                f"  redir @webpage {web_client}/?connection={{host}}:443 302",
            ])
        lines.extend([f"  reverse_proxy basis:{port}", "}", ""])
    CADDY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = CADDY_FILE.with_suffix(".tmp")
    temp.write_text("\n".join(lines), encoding="utf-8")
    temp.replace(CADDY_FILE)
    print(f"Generated Coolify proxy routes for {len(worlds)} worlds in {zone}", flush=True)


def stop_all(*_):
    for proc in children:
        if proc.poll() is None:
            proc.terminate()
    deadline = time.time() + 15
    for proc in children:
        try:
            proc.wait(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.exit(0)


def main():
    worlds = read_worlds()
    for i, world in enumerate(worlds):
        write_world_config(world, i)
    write_caddy(worlds)
    for world in worlds:
        env = os.environ.copy()
        env.update({
            "SetPort": str(world["port"]),
            "HealthCheckPort": str(world["health_port"]),
            "ServerName": world["name"],
            "ServerMotd": world["motd"],
            "Password": world["password"],
            "PeerLimit": world["peer_limit"],
            "ApiKey": world["api_key"],
            "ApiEnabled": "true",
            "BasisFirstAdmin": os.environ.get("BASIS_FIRST_ADMIN", ""),
            "HealthCheckHost": "*",
            "EnableStatistics": "true",
            "EnableConsole": "false",
        })
        if os.environ.get("WEB_PLAYERS", "no").lower() == "yes":
            env["NetworkStackId"] = "litenetlib,websocket"
        print(f"Starting world {world['slug']} on UDP {world['port']} (health TCP {world['health_port']})", flush=True)
        children.append(subprocess.Popen(["dotnet", str(APP)], cwd=world["root"], env=env))
    signal.signal(signal.SIGTERM, stop_all)
    signal.signal(signal.SIGINT, stop_all)
    while True:
        for world, proc in zip(worlds, children):
            code = proc.poll()
            if code is not None:
                print(f"World {world['slug']} exited with status {code}; stopping all worlds", flush=True)
                stop_all()
        time.sleep(2)


if __name__ == "__main__":
    main()
