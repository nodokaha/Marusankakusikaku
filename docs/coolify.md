# Deploy BasisMultiWorld with Coolify

This preset runs the complete multi-world stack as one Coolify Docker Compose resource. One Basis
container supervises the configured worlds; an optional Caddy service routes HTTP/WebSocket traffic behind the Coolify proxy. The
existing configure.sh + generated Compose workflow remains available for conventional Docker Compose
deployments.

## 1. Create the Coolify resource

1. In Coolify, create a Docker Compose resource from https://github.com/nodokaha/Marusankakusikaku.
2. Set the Compose file path to coolify/compose.yaml.
3. Configure the environment variables below in the resource's Environment Variables panel.
4. Add COMPOSE_PROFILES=web and WEB_PLAYERS=yes if you want browser clients / WSS. Leave the
   profile unset for native UDP-only operation.
5. When the web profile is enabled, configure the Coolify proxy domain(s) on the caddy service,
   targeting internal port 80. Add the hub domain (DNS_ZONE), the hub slug domain, DNS_HOST.DNS_ZONE,
   and one domain for every other world slug. Coolify's proxy provides HTTPS; Caddy routes the
   resulting HTTP/WebSocket traffic to the correct Basis listener.
6. Deploy. The first build downloads the pinned Basis and WebSocket transport sources and compiles
   the server; this can take several minutes and needs roughly 1.5 GB RAM and 2 GB free disk.

Do not add a separate Coolify resource for each world. Do not expose health ports or dashboard ports.

## 2. Required environment variables

Use .env.example as the starting point. At minimum:

| Variable | Example | Purpose |
| --- | --- | --- |
| BASIS_REF | 2f5b3e106ea10a1dc96b208d000428a335ef7c6c | Pinned upstream Basis commit |
| WEBSOCKET_REF | 62a4468432eb82c78ac744a7e78fca4bb91f7c8a | Pinned WebSocket transport commit |
| CDN_BASE | https://cdn.example.com/basis | Base URL for relative .BEE bundle paths |
| UNLOCK_PASSWORD | secret | Bundle build password; per-world UNLOCK_PASSWORD_SLUG overrides it |
| BASIS_FIRST_ADMIN | did:key:... | Comma-separated admin DID(s), seeded on first boot |
| WORLD_PORT_START | 4296 | First published UDP port |
| WORLD_PORT_END | 4298 | Last published UDP port |

Set HUB_PASSWORD, FOREST_PASSWORD, etc. for join passwords; optional per-world variables are
<SLUG>_MOTD, <SLUG>_PEER_LIMIT, and <SLUG>_API_KEY. Slugs are upper-cased and dashes become
underscores. Every port in worlds.conf must fall inside the published range.

For web clients, additionally set:

- WEB_PLAYERS=yes
- DNS_ZONE=worlds.example.com (must be a real domain pointing to this host)
- DNS_HOST=vm1 (single DNS label; defaults to vm1)
- optionally WEB_CLIENT_URL=https://play.worlds.example.com

Coolify's proxy obtains and renews HTTPS certificates for the configured domains. Do not publish
host ports 80 or 443 from this Compose stack: Coolify already owns them. WSS uses the normal HTTPS
port 443 through the proxy; UDP game traffic goes directly to Basis. Set PROXY_NET to a subnet that
does not overlap another Docker network if the default 172.30.42.0/24 is already in use. Set
COOLIFY_PROXY_NET to the CIDR of the Coolify proxy's Docker network if you want the original client
IP forwarded through Caddy to Basis. Find it with docker network inspect coolify.

## 3. Configure the worlds

Edit worlds.conf in the repository before deployment. The first row is the hub and should use
UDP port 4296. For example:

```text
hub      4296   Hub.BEE       My Hub
forest   4297   Forest.BEE    Forest Walk
city     4298   City.BEE      City at Night
```

Each bundle may be an absolute HTTPS URL or a path relative to CDN_BASE. World data, configuration,
saved props, storage and default-library files are stored in the named basis-data volume under
/data/worlds/<slug>.

The Basis service publishes UDP over the configured port range. Keep the range as small as
practical and ensure the firewall allows the UDP ports used by your worlds.
DNS SRV records are still required for native clients to discover each world's UDP port; use
dns-records.sh for the BIND records.

## 4. Persistence and updates

Coolify's named volumes persist across redeployments:

- basis-data: world configuration, player storage, saved props and default library
- caddy-data and caddy-state: Caddy state (TLS certificates are managed by the Coolify proxy)

Back up these volumes and keep a copy of .env and worlds.conf. Changing BASIS_REF or WEBSOCKET_REF
triggers a new image build. Changing worlds.conf or runtime variables requires redeployment.

## Notes and current limits

- This preset runs all worlds in one Basis container to keep deployment to one resource. A failing
  world currently causes the supervisor to stop the group; independent per-world restart policies
  are not available in this preset.
- The optional per-world dashboard containers from the conventional Compose workflow are not part
  of this preset. Use the existing configure.sh deployment if you need those dashboard services.
- The WebSocket package is included in the image; set WEB_PLAYERS=yes and enable the web Compose
  profile. Configure all world domains on the caddy service at internal port 80 in Coolify. The
  Coolify proxy terminates TLS on 443; Caddy itself is not published on host ports 80/443.
