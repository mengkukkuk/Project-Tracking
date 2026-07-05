# Deploy: SPA on Cloudflare Worker+Pages, Flask backend via Cloudflare quick tunnel

Zero-cost deployment. The Vue SPA and a tiny reverse-proxy Worker run on
Cloudflare; the **unchanged** Flask backend runs as a Windows service on a local
device and is exposed through a Cloudflare **quick tunnel**.

```
Browser ──/api/*──▶ Cloudflare Worker ──reads KV[backend_url]──▶ https://<random>.trycloudflare.com
                                                                        │
        ◀── static SPA (dist/) served by same Worker                    ▼
                                                     cloudflared ──▶ waitress 127.0.0.1:5000 (Flask)
```

Why the Worker: a quick-tunnel URL is **random and changes on every restart**.
The SPA always calls same-origin `/api/*`; the Worker forwards to whatever URL is
currently stored in KV (`backend_url`). On each tunnel restart, `tunnel-run.ps1`
rewrites that KV value — so nothing on Cloudflare needs rebuilding or redeploying.

---

## A. Cloudflare (one-time), from `frontend/`

```bash
npm install                                   # ensure deps (incl. wrangler if added as devDep)
npm i -D wrangler                             # if not already present
npx wrangler login

# Create the KV namespace and copy the printed id into frontend/wrangler.toml (id = "...")
npx wrangler kv namespace create CONFIG

npm run build                                 # -> frontend/dist
npx wrangler deploy                           # deploys SPA + Worker
# => https://project-tracking.<your-subdomain>.workers.dev
```

`VITE_API_BASE` stays empty (see `frontend/.env.production`) so the SPA calls
same-origin `/api`, which hits the Worker.

### Create a scoped API token (for the Windows box to write KV)
Cloudflare dashboard → My Profile → API Tokens → Create Token → Custom:
- Permission: **Account › Workers KV Storage › Edit**
- Note your **Account ID** and the **CONFIG namespace id**.

---

## B. Windows box (the local deploy device)

Prereqs: Python venv set up in `backend/.venv`, `cloudflared` installed
(`winget install --id Cloudflare.cloudflared`), and **NSSM**
(`winget install nssm` or https://nssm.cc).

### B0. One-click install (recommended)
Installs **both** services non-interactively, deriving all paths from the repo
root — portable across machines, no NSSM GUI, no manual typing.

1. Do **B1** below (create `backend/.env`, seed if needed).
2. Copy secrets template and fill in your Cloudflare values:
   ```
   copy deploy\service.config.example.bat deploy\service.config.bat
   ```
   Edit `deploy\service.config.bat` — set `CLOUDFLARE_API_TOKEN`, `CF_ACCOUNT_ID`,
   `CF_KV_NAMESPACE_ID` (this file is git-ignored; never commit it).
3. Right-click `deploy\install-services-tunnel.bat` → **Run as administrator**
   (or run from an elevated `cmd`).

The script installs `ProjTrackApi` + `ProjTrackTunnel` (auto-start, logs to
`deploy\logs`, restart-on-exit), is idempotent (re-running reinstalls cleanly),
and starts both. If `service.config.bat` is missing it prompts for the three
secrets once. Manage afterwards with `nssm status/stop/restart/remove <service>`.

Prefer to do it by hand? Follow **B1–B3** instead.

### B1. Backend `.env`
In `backend/.env` set real secrets and DB, e.g.:
```
SECRET_KEY=<random-32+>
JWT_SECRET_KEY=<random-32+>
DATABASE_URL=postgresql+psycopg2://postgres:<pw>@localhost:5432/ProjectTracking
CORS_ORIGINS=*        # browser never calls the backend directly, so CORS is moot
```
Seed once if needed: `.venv/Scripts/python seed.py`.

### B2. Backend as a service (waitress on 127.0.0.1:5000)
```
nssm install ProjTrackApi "G:\Code\proj-tracking\Project-Tracking\backend\.venv\Scripts\python.exe" "G:\Code\proj-tracking\Project-Tracking\backend\server.py"
nssm set ProjTrackApi AppDirectory "G:\Code\proj-tracking\Project-Tracking\backend"
nssm start ProjTrackApi
```

### B3. Tunnel + KV updater as a service
Set the three env vars on the service (replace placeholders):
```
nssm install ProjTrackTunnel "powershell.exe" "-ExecutionPolicy Bypass -NoProfile -File G:\Code\proj-tracking\Project-Tracking\deploy\tunnel-run.ps1"
nssm set ProjTrackTunnel AppDirectory "G:\Code\proj-tracking\Project-Tracking\deploy"
nssm set ProjTrackTunnel AppEnvironmentExtra "CLOUDFLARE_API_TOKEN=<token>" "CF_ACCOUNT_ID=<account-id>" "CF_KV_NAMESPACE_ID=<kv-namespace-id>"
nssm start ProjTrackTunnel
```

On start (and after every reboot) the script publishes the current tunnel URL to
KV within a few seconds.

---

## C. Verify
1. Open the `*.workers.dev` URL → SPA loads; hard-refresh a deep route like
   `/summaries` → still loads (SPA fallback OK).
2. Log in with a seeded account → `/api/auth/login` returns 200 (Network tab
   shows same-origin `/api/...`).
3. Create/edit a project and toggle a process checkbox → data persists
   (proves Worker → tunnel → waitress → Flask → DB).
4. `nssm restart ProjTrackTunnel` → KV `backend_url` updates automatically; app
   keeps working with **no** Cloudflare redeploy.
5. Reboot the box → both services auto-start and the app recovers.

---

## Notes / limits (quick tunnel)
- Random URL per restart (handled via KV), no SSE (this API doesn't use it),
  best-effort uptime, and the backend is only reachable while the device +
  services are running.
- For a stable URL later: register/move a domain to Cloudflare and switch to a
  **named tunnel**; nothing in `frontend/` changes — just point KV (or the
  Worker) at the fixed hostname.
