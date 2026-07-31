# Demo deployment (AWS EC2, one-time data snapshot)

This deploys the dashboard as a **single Docker container** on one EC2 instance:

- The Vue frontend is built and served by the Flask backend (same origin, so no
  CORS and no frontend config changes).
- The data is a **one-time snapshot** of the SQL Server database baked into the
  image as a SQLite file — no database server in AWS, and the demo shows
  non-live data.

When live data is needed again later, point `DATABASE_URL` back at a credentialed
SQL Server connection (the MSSQL code paths are untouched) and re-add the
Microsoft ODBC driver install to the Dockerfile (see `backend/Dockerfile` for
the original steps).

## 1. Snapshot the data (once, on your Windows machine)

Needs your Windows domain login, so run from a shell with domain credentials
(same as running the backend locally):

```
runas /netonly /user:UMROOT\<your-user> cmd
cd <repo>\backend
uv run python scripts\snapshot_to_sqlite.py --server <host> --database <db>
```

(Any Python 3.12 environment with the backend dependencies works — a plain
venv's `.venv\Scripts\python` in place of `uv run python` is fine.)

This writes `backend/data/parsivel.db` (all 5 tables + an index on
`parsivel_OTT.cpuTimestamp`) and prints row counts. The file is gitignored.

## 2. Build and test locally (gate before deploying)

```
docker compose -f docker-compose.prod.yml up --build -d
```

Then check `http://localhost` (port 80; if taken, change the mapping to
`8080:8000` temporarily):

- `http://localhost/api/ping` returns `{"status": "ok"}`
- Landing page and dashboard render with snapshot data (charts populate)
- Refresh the browser while on `/dashboard` (tests the SPA fallback)
- Change date ranges/filters; download the CSV export
- `docker compose -f docker-compose.prod.yml logs` shows no errors

Stop with `docker compose -f docker-compose.prod.yml down`.

## 3. Launch the EC2 instance (once)

- AMI: Amazon Linux 2023, instance type **t3.small**, 20 GB gp3 disk
- Security group: allow inbound TCP 80 from `0.0.0.0/0`, TCP 22 from your IP only
- Create/download a key pair for SSH

Install Docker on the instance:

```
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
# docker compose v2 plugin
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -sSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

Log out/in (or `newgrp docker`) so the group change applies.

## 4. Ship the image and run it

On your machine (PowerShell), export the image built in step 2 and copy it up
(no ECR/registry needed). **Note:** if your machine builds ARM images (it
shouldn't on x86 Windows), build with `--platform linux/amd64`.

```
docker save parsivel-demo -o parsivel-demo.tar
scp -i <key.pem> parsivel-demo.tar docker-compose.prod.yml ec2-user@<ec2-ip>:~
```

On the instance:

```
docker load -i parsivel-demo.tar
docker compose -f docker-compose.prod.yml up -d
```

(`build: .` in the compose file is ignored as long as the `parsivel-demo`
image is already loaded and you don't pass `--build`.)

Demo URL: **http://\<ec2-public-ip\>** — plain HTTP, fine for a temporary demo.

## 5. Updating the demo

Rebuild locally (e.g. after re-running the snapshot), then repeat step 4.
On the instance, `docker compose -f docker-compose.prod.yml up -d` again after
`docker load` — compose replaces the running container.

## Teardown

Terminate the EC2 instance. Nothing else was created in AWS.
