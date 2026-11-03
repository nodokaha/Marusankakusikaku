# Deploy BasisMultiWorld with Coolify

This preset runs the complete multi-world stack as one Coolify Docker Compose resource. One Basis
container supervises the configured worlds; an optional Caddy service provides HTTPS/WSS. The
existing configure.sh + generated Compose workflow remains available for conventional Docker Compose
deployments.

## 1. Create the Coolify resource

1. In Coolify, create a Docker Compose resource from https://github.com/nodokaha/Marusankakusikaku.
2. Set the Compose file path to coolify/compose.yaml.
3. Configure the environment variables below in the resource's Environment Variables panel.
4. Add COMPOSE_PROFILES=web if you want browser clients / WSS through Caddy. Leave it unset for
   native UDP-only operation.
5. Deploy. The first build downloads the pinned Basis and WebSocket transport sources and compiles
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
| WORLD_PORT_START | 4296 | First published UDP/TCP port |
| WORLD_PORT_END | 4395 | Last published UDP/TCP port |

Set HUB_PASSWORD, FOREST_PASSWORD, etc. for join passwords; optional per-world variables are
<SLUG>_MOTD, <SLUG>_PEER_LIMIT, and <SLUG>_API_KEY. Slugs are upper-cased and dashes become
underscores. Every port in worlds.conf must fall inside the published range.

For web clients, additionally set:

- WEB_PLAYERS=yes
- DNS_ZONE=worlds.example.com (must be a real domain pointing to this host)
- DNS_HOST=vm1 (single DNS label; defaults to vm1)
- optionally WEB_CLIENT_URL=https://play.worlds.example.com

Caddy obtains certificates automatically. TCP 80 and 443 must be reachable, and all world TCP
ports in the published range are forwarded to Caddy. UDP game traffic goes directly to Basis.

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

The Basis service publishes UDP and the Caddy service publishes TCP over the configured port range.
Keep the range as small as practical and ensure the firewall allows the ports used by your worlds.
DNS SRV records are still required for native clients to discover each world's UDP port; use
dns-records.sh for the BIND records.

## 4. Persistence and updates

Coolify's named volumes persist across redeployments:

- basis-data: world configuration, player storage, saved props and default library
- caddy-data and caddy-state: ACME certificates and Caddy state

Back up these volumes and keep a copy of .env and worlds.conf. Changing BASIS_REF or WEBSOCKET_REF
triggers a new image build. Changing worlds.conf or runtime variables requires redeployment.

## Notes and current limits

- This preset runs all worlds in one Basis container to keep deployment to one resource. A failing
  world currently causes the supervisor to stop the group; independent per-world restart policies
  are not available in this preset.
- The optional per-world dashboard containers from the conventional Compose workflow are not part
  of this preset. Use the existing configure.sh deployment if you need those dashboard services.
- The WebSocket package is included in the image; set WEB_PLAYERS=yes and enable the web Compose
  profile to activate the Caddy frontend.
