# Deploying the wall (Docker + Tailscale Funnel)

The wall runs on any small Linux server as two containers from `docker-compose.yml`:

- **app**: the image built from `Dockerfile` (React build + Python server + MediaPipe model).
- **tailscale**: joins your tailnet as `party` and serves `https://party.<tailnet>.ts.net` to the public internet
  with Funnel. The app shares its network namespace and listens on `127.0.0.1:8000` only, so the one way in is
  Tailscale Serve/Funnel on 443: **no port open on the server, on the Docker bridge, or to other tailnet devices**.

Guests' phones never talk to the server: they upload to the Google Photos album, and the server polls it.
Only the projector computer opens the public URL, and the passcode gates it.

## 1. Tailscale (once)

In the [admin console](https://login.tailscale.com/admin):

1. **DNS:** enable **MagicDNS** and **HTTPS certificates**. Funnel needs both.
2. **Access controls:** tag the node and let it use Funnel, but reach nothing else. The server downloads photos
   from the internet, so treat it as exposed: with the default allow-all policy, someone who breaks into the app
   is inside your tailnet. Add to the policy file:
   ```json
   "tagOwners": { "tag:party": ["autogroup:admin"] },
   "nodeAttrs": [{ "target": ["tag:party"], "attr": ["funnel"] }]
   ```
   Then make sure no `acls` / `grants` rule lists `tag:party` (or `*`) as a **source**. If you still have the
   default `{"src": ["*"], "dst": ["*:*"]}`, replace it with rules for your own users, for example:
   ```json
   "grants": [{ "src": ["autogroup:member"], "dst": ["*"], "ip": ["*"] }]
   ```
   Rules that let *you* reach the node are fine; the passcode still gates the wall.
3. **Settings → Keys:** generate an auth key that is **pre-authorized** and **tagged `tag:party`**. One-off
   (not reusable) is enough: the node keeps its identity in `ts-state/`, so the key is only spent on the first
   start. Delete it in the console if it ends up unused.

## 2. Server

Any small instance works: effects are applied once per photo, so CPU only matters while photos are arriving.
2 vCPU and 4 GB RAM is plenty, including for building the image. Both x86-64 and ARM64 work.

**Lock the box down first.** Whoever can log in to it has everything: `.env` (the passcode, and the session secret
that signs cookies), every photo, and `ts-state/` (the node's identity, so they could serve their own site at your
URL). Membership of the `docker` group is the same as root.

- SSH keys only (`PasswordAuthentication no`, `PermitRootLogin prohibit-password`).
- A firewall (your provider's, or `ufw`) with no inbound rules except SSH (22/tcp), ideally from your own IP only.
  Tailscale needs **no** inbound ports. Better still: run Tailscale on the host too, use Tailscale SSH, and close 22.
- Never add `ports:` to `docker-compose.yml`: Docker opens published ports past `ufw`.

Install Docker with the Compose plugin (e.g. `curl -fsSL https://get.docker.com | sh`).

## 3. Install and start

On the server:

```bash
git clone <this repo> wall && cd wall
cp config.example.yaml config.yaml        # event.title, qr_url and album_url (see below)
cp .env.example .env && chmod 600 .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # paste into SESSION_SECRET
```

Fill in `.env`:

| Key | Value |
|---|---|
| `PASSCODE` | 8+ characters, not `change-me`. The URL is public, so this is the real gate. Avoid `$` and quotes (Compose interpolates them). |
| `SESSION_SECRET` | the 64 hex characters from above. Changing it signs everyone out. |
| `COOKIE_SECURE` | `true` (Funnel is https) |
| `TS_AUTHKEY` | the `tag:party` auth key from step 1 |
| `TS_EXTRA_ARGS` | `--advertise-tags=tag:party` |

In `config.yaml`, `album_url` is the album's share link (Google Photos → album → Share → Create link) and `qr_url`
is the link guests scan to join and upload; usually both are the same link with collaboration turned on.
Keep `login_title` free of names: the passcode screen is public.

Build and start:

```bash
docker compose up -d --build
```

The first build takes a few minutes. The image is built locally (`pull_policy: never`); nothing is pulled from a
registry except the base images and `tailscale/tailscale`.

<details>
<summary>Building on another machine instead</summary>

If the server is too small to build, build on your machine for the server's CPU and stream the image over SSH,
then copy only `docker-compose.yml`, `ts-serve.json`, `config.yaml` and `.env` to the server:

```bash
docker buildx build --platform linux/amd64 -t photo-wall:latest --load .     # or linux/arm64
docker save photo-wall:latest | gzip | ssh <server> 'gunzip | docker load'
ssh <server> 'cd wall && docker compose up -d --no-build'
```
</details>

## 4. Check it

On the server, in the `wall` folder:

```bash
docker compose ps                                # app and tailscale both running
docker compose logs tailscale | grep -i funnel   # the public URL
docker compose logs -f app                       # a sync every 90 s
docker compose exec app python -m wall status    # photo counts per status, last sync and its error
```

From another device on your tailnet, `curl http://party:8000/` must **fail** to connect: the app listens on
loopback only, and the one way in is `https://party.<tailnet>.ts.net`.

From anywhere, with only the URL and the passcode (from a checkout of this repo):

```bash
cd backend
WALL_PASSCODE='<passcode>' uv run python -m wall --remote https://party.<tailnet>.ts.net photos
```

Then open the URL in a browser, enter the passcode, and the wall appears. Without a session, `/api/*` and
`/media/*` answer 401.

## 5. Files on the server

| Path | What | Keep secret |
|---|---|---|
| `.env` | passcode, session secret, Tailscale key | yes (`chmod 600`) |
| `config.yaml` | event title, album link, display defaults | the album link lets anyone view the album |
| `data/` | SQLite db, original and processed photos | yes; wipe after the event |
| `ts-state/` | the node's Tailscale identity | yes |

## 6. Updating

```bash
git pull && docker compose up -d --build
docker image prune -f                    # drop the replaced image
```

After changing only `config.yaml`, run `docker compose restart app`; after changing `.env`, run
`docker compose up -d` (recreates the containers with the new values). Browsers keep their session across restarts
as long as `SESSION_SECRET` and `PASSCODE` stay the same.

## 7. After the event

```bash
docker compose exec app python -m wall wipe --yes     # photos and database
docker compose exec tailscale tailscale logout        # releases the node
docker compose down
cd .. && rm -rf wall                                  # .env, config.yaml, ts-state/, data/
```

Then:
- In the Tailscale admin console, remove the `party` machine if it is still listed, and delete any unused key.
- In Google Photos, turn off link sharing and collaboration on the album.
- Optionally remove `tag:party` from the policy file; without a tagged device it does nothing.

## 8. Notes

- **Session cookie:** `HttpOnly; Secure; SameSite=Lax`, 30 days. It's `Secure`, so the wall must be opened over
  https (Funnel) or on `localhost`. For plain-http testing on a LAN IP, set `COOKIE_SECURE=false`.
- **Rate limit:** 5 login attempts per minute per IP, and 30 per minute in total. Tailscale's proxy connects from
  127.0.0.1, and uvicorn trusts `X-Forwarded-For` from there only, so the per-IP limit applies to the real client.
- **Ending access:** change `PASSCODE` and run `docker compose up -d`. Every existing session stops working, and open
  walls return to the passcode screen.
- **DNS:** `docker-compose.yml` pins the tailscale container's DNS to `1.1.1.1` / `9.9.9.9`, which works around hosts
  whose Docker daemon is configured with IPv6-only resolvers. Remove the `dns:` line if your host doesn't need it.
- **Without Tailscale** (a laptop on the venue's LAN only, never a public server: this is plain http, so the passcode
  crosses the network unencrypted): `cd backend && uv run python -m wall --config ../config.yaml serve --host 0.0.0.0`
  with `COOKIE_SECURE=false` in `.env`.
