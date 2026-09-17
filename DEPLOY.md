# Deployment (AWS EC2 + twice-daily data push from campus)

The dashboard runs as **one Docker container on one EC2 instance**. It reads a
SQLite database on a Docker volume. The SQL Server is only
reachable from the UM network, so a **scheduled task on a campus Windows PC**
pushes new rows to the instance over SSH twice a day:

```
 campus Windows PC (Task Scheduler, 06:00 + 18:00)          EC2 instance
 ┌──────────────────────────────────────────┐              ┌──────────────────────────────┐
 │ scripts/sync_to_aws.py                   │   ssh/scp    │ container parsivel-demo      │
 │  1. ask instance for watermark per table ├─────────────►│  scripts/ingest.py state     │
 │  2. SELECT rows > watermark from SQL Srv │              │                              │
 │     (as the read-only domain account)    │              │  /incoming/delta-*.db        │
 │  3. scp delta file, run ingest import    ├─────────────►│  scripts/ingest.py import    │
 └──────────────────────────────────────────┘              │   -> /app/data/parsivel.db   │
                                                           │      (Docker volume)         │
                                                           └──────────────────────────────┘
```

- The job is stateless; a missed run is caught up by the next one.
- Applying the same delta twice is harmless (rows above the watermark are
  replaced, not duplicated).
- Image updates never touch the data: the database lives on the
  `parsivel-data` volume, not in the image.

Files involved:

| File | Runs on | Purpose |
|---|---|---|
| `backend/scripts/sync_to_aws.py` | campus PC | pull deltas from SQL Server, ship + apply over SSH |
| `backend/scripts/mssql_source.py` | campus PC | SQL Server connection, domain-account impersonation, SQLite copy |
| `backend/scripts/ingest.py` | container | `state` / `import` / `init` on the SQLite database (stdlib only) |
| `backend/scripts/register_sync_task.ps1` | campus PC | create the Task Scheduler job |
| `backend/scripts/snapshot_to_sqlite.py` | campus PC | full local copy (dev, or seeding) |
| `backend/.sync.env` (from `.sync.env.example`) | campus PC | settings + the account password (gitignored) |
| `Dockerfile`, `docker-compose.prod.yml` | build machine / instance | production image and service |

## 1. EC2 instance (once)

- AMI Amazon Linux 2023, **t3.small**, 20 GB gp3 disk (the database is about
  2.5 GB and grows roughly 1.5 MB/day).
- Security group: TCP 80 and 443 from `0.0.0.0/0`; TCP 22 from the campus
  PC that runs the sync **and** from any machine you deploy from.
- An Elastic IP, so the address survives stop/start, and a DNS name (A
  records for the apex and `www`) pointing at it. HTTPS needs the name.

Install Docker and the compose plugin:

```
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -sSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
mkdir -p ~/incoming
```

Log out and in again so the group change applies.

## 2. Build and ship the image

On your machine (Docker Desktop running), from the repo root:

```
docker compose -f docker-compose.prod.yml build
docker save parsivel-demo -o parsivel-demo.tar
scp -i <key.pem> parsivel-demo.tar docker-compose.prod.yml Caddyfile ec2-user@<ec2-ip>:~
```

On the instance, once, tell Caddy which name to get a certificate for:

```
echo "SITE_DOMAIN=example.org" > ~/.env      # your domain, no www
```

Then (every deploy):

```
docker load -i parsivel-demo.tar
docker compose -f docker-compose.prod.yml up -d
rm parsivel-demo.tar
```

`build: .` in the compose file is ignored as long as the image is already
loaded and you do not pass `--build`. The image has no data in it, so this
is a few hundred MB.

**HTTPS** is handled by the `caddy` service in the compose file: it owns
ports 80 and 443, requests a Let's Encrypt certificate for `SITE_DOMAIN` on
first start (DNS must already resolve to the instance and port 80/443 must
be open), renews it automatically, and forwards to the app container.
Plain HTTP and the `www` name redirect to `https://<domain>`. Certificates
live on the `caddy-data` volume; do not delete it, or Let's Encrypt's
rate limits can lock you out for a week after a few re-issues. Check with
`docker logs parsivel-caddy` and `curl -I https://<domain>/api/ping`.

## 3. Seed the data volume (once)

The container starts with an empty volume. Fill it one of two ways.

**a) From the previous snapshot container** (fastest, if the old
`parsivel-demo` image with the baked-in database is still running):

```
docker ps                                            # note the old container name
docker cp <old-container>:/app/data/parsivel.db ~/parsivel.db   # 2.5 GB, check `df -h`
docker load -i parsivel-demo.tar
docker compose -f docker-compose.prod.yml up -d      # replaces the old container
docker cp ~/parsivel.db parsivel-demo:/app/data/parsivel.db
docker exec parsivel-demo python scripts/ingest.py init          # WAL + indexes
docker compose -f docker-compose.prod.yml restart
rm ~/parsivel.db
docker image prune -f
```

**b) Full load from SQL Server**, from the campus PC once step 4 is set up.
This pulls every table again and copies about 2.5 GB up:

```
.venv\Scripts\python scripts\sync_to_aws.py --full
```

Either way, the first normal sync run afterwards brings the data up to date.

## 4. The campus sync PC (once)

Requirements: Windows, Python 3.12+, **Microsoft ODBC Driver 18 for SQL
Server**, the built-in OpenSSH client (`ssh`/`scp` in `C:\Windows\System32\OpenSSH`),
network access to the SQL Server on port 1433, and outbound SSH to the instance.

Only the `backend` folder is needed on this PC (without `.venv`, `data`,
`logs`, `app`, `tests`), plus the `.pem` key. Copying it on a USB stick works.

```
cd <copy>\backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-sync.txt
copy .sync.env.example .sync.env
```

Edit `.sync.env`: set `PARSIVEL_SQL_PASSWORD`, `PARSIVEL_SSH_HOST` and the
path to the `.pem` key. The read-only account is a **Windows domain
account**, so the script logs in the way `runas /netonly` does, in
process; the PC does not need to be domain-joined and the task can run as
any local user. (If the PC *is* domain-joined and the task runs as the
service account itself, leave `PARSIVEL_SQL_USER` empty.)

Test in stages:

```
.venv\Scripts\python scripts\sync_to_aws.py --dry-run   # SQL Server + SSH state only, no upload
.venv\Scripts\python scripts\sync_to_aws.py             # real push
```

Then register the scheduled task (asks for your Windows password once so it
can run while you are logged off):

```
powershell -ExecutionPolicy Bypass -File scripts\register_sync_task.ps1
```

Defaults: 06:00 and 18:00 local, log in `backend\logs\sync.log`, missed runs
start as soon as the PC is back on. Keep the times away from 01:00–02:00:
`cpuTimestamp` is local time and repeats that hour on the November DST
change, and the watermark is `cpuTimestamp`. To change the schedule:
`register_sync_task.ps1 -Times 05:00,17:00`. To also run once about two
minutes after every boot: add `-AtStartup`. To remove the task:
`register_sync_task.ps1 -Unregister`.

## 5. Day to day

- **Is it working?** The dashboard toolbar shows "Data synced <time>", the
  moment of the last successful run (also at `/api/sync/status`). A run that
  finds nothing new still updates it, so a stale value means the task is not
  running. For detail, `Get-Content backend\logs\sync.log -Tail 20` on the PC,
  or on the instance `docker exec parsivel-demo python scripts/ingest.py state`
  shows the newest timestamp per table.
- **Run a sync by hand:** `Start-ScheduledTask -TaskName "Parsivel dashboard sync"`,
  or run the Python command from step 4.
- **Update the app:** rebuild, ship, `docker load`, `compose up -d`. The volume
  is untouched.
- **Rebuild the data from scratch:** `sync_to_aws.py --full`.
- **Disk:** `df -h` on the instance. Leftover files in `~/incoming` mean an
  import failed mid-way; the log on the PC has the error, and re-running the
  sync is safe.
- **The instance's public IP changed** (after a stop/start or a rebuild;
  a crash or reboot keeps it): the sync logs `ssh failed ... timed out`
  and the dashboard's "Data synced" time stops advancing. Update
  `PARSIVEL_SSH_HOST` in `.sync.env` on the sync PC; nothing else changes.
  An Elastic IP avoids this entirely. After a full rebuild the SSH host key
  also changes, and `ssh` refuses the "changed" key: remove the old line
  for that host from `C:\Users\<you>\.ssh\known_hosts` on the sync PC.

## Teardown

Terminate the EC2 instance and unregister the scheduled task on the PC.
Nothing else was created in AWS.
