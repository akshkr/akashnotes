# Docker & Compose Basics

From [Day 26: Vector Search with pgvector](../Phase_3_RAG/Day_026_pgvector_search/pgvector_search.md) onward, Atlas stores Orbit's docs in Postgres with the pgvector extension. Installing a database by hand differs on every OS and leaves your laptop in a state nobody else can reproduce. With Docker, one command gives everyone the same Postgres, and one `compose.yaml` file starts Atlas and its database together.

## Who this is for

- **Read this if** you have never typed `docker run`, or "image", "volume" and "port mapping" feel fuzzy. Read it the day before Day 26; it takes about 35 minutes.
- **Skip it if** you can answer the five [Self-Check](#self-check) questions without peeking.
- **You need:** a terminal ([Terminal, Git & GitHub](A01_terminal_git_github.md)), a little SQL ([SQL & Postgres](A07_sql_postgres.md)), Python 3.11+ with uv, and Docker installed and running ([Get Docker](https://docs.docker.com/get-started/get-docker/)). On a work machine, check Docker Desktop's licence terms. Everything here runs locally and costs nothing.
- **New terms:** image, container, port mapping, volume, Compose.

> **Coming from Software Engineering?** An image is to a container what a class is to an instance: one immutable artifact, many running copies. A Dockerfile is the build script for that artifact, and a registry such as Docker Hub is a package index for images, like PyPI for wheels. Compose is a declarative file that starts your local stack already wired together. Daily Docker users can skim to the compose file, then do the Self-Check.

## Images and containers

**The problem.** You install Postgres 16 with Homebrew; your teammate has Postgres 14 from apt. The pgvector extension builds on one machine and fails on the other, and "works on my machine" helps nobody.

**The intuition.** Think of a recipe card and a cooked meal. The card never changes; each time you cook from it you get a fresh meal you can eat, spill or throw away, and everyone with the same card gets the same meal. In Docker, the card is an **image** and each meal is a **container**.

**A tiny example.** Run this command twice. You get Python 3.12 without installing it.

```bash
docker run --rm python:3.12-slim python -c "import sys; print(sys.version)"
```

```text
Unable to find image 'python:3.12-slim' locally
3.12-slim: Pulling from library/python
...
3.12.x (main, ...) [GCC ...]
```

The first run pulls (downloads) the image; the second starts in about a second because the image is cached. Your patch version will differ. `--rm` deletes the container when the command finishes; the image stays.

**Name the parts.**

| Term | Plain meaning | Example |
|---|---|---|
| image | a read-only bundle of OS files, runtime, libraries and code | `python:3.12-slim` |
| container | a running (or stopped) copy of an image, with its own process, disk layer and network | what `docker run` starts |
| tag | the label after the colon that names a version of an image | `pg17`, `0.8.7-pg17` |
| registry | a server that stores images; `docker pull` downloads from it | Docker Hub |
| Dockerfile | a text file of build steps that produces an image | `FROM`, `COPY`, `RUN` |

```mermaid
flowchart LR
    DF["Dockerfile (recipe)"] -->|docker build| IMG["Image (read-only)"]
    REG["Registry (Docker Hub)"] -->|docker pull| IMG
    IMG -->|docker push| REG
    IMG -->|docker run| C1["Container A"]
    IMG -->|docker run| C2["Container B"]
    C1 -->|docker rm| GONE["Container deleted, image kept"]
```

**Common mistake.** Treating a container as permanent. Anything written inside its own filesystem disappears when it is removed, so data goes in a volume (next section) and code goes into the image. Also, `latest` is a moving label, not a version: pin a tag such as `pgvector/pgvector:0.8.7-pg17` when you need repeatable builds.

## Running Postgres with `docker run`: ports, env vars and volumes

**The problem.** Try `docker run pgvector/pgvector:pg17`. The container exits at once and prints:

```text
Error: Database is uninitialized and superuser password is not specified.
       You must specify POSTGRES_PASSWORD to a non-empty value for the
       superuser. For example, "-e POSTGRES_PASSWORD=password" on "docker run".
```

Fix that, and your laptop's Python still can't reach the database, and a replacement container starts empty.

**The intuition.** A container is a sealed box with its own network and disk. An **environment variable** is a setting you hand the box at start. **Port mapping** cuts a hole for one port, so traffic to your laptop reaches the process inside. A **volume** is a drawer outside the box, so its contents survive when the box is thrown away.

**A tiny example.** Port mappings read `host:container`: with `-p 5433:5432`, port 5433 on your laptop reaches port 5432 inside the container. Many containers can listen on 5432 inside their own boxes, but each needs its own host port.

The full command for Atlas's database:

```bash
docker run -d --name orbit-db \
  -e POSTGRES_PASSWORD=devpass \
  -p 5432:5432 \
  -v orbit_pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg17
docker ps          # orbit-db should show "Up"
docker logs orbit-db   # wait for "database system is ready to accept connections"
```

| Flag | What it does |
|---|---|
| `-d` | detached: run in the background |
| `--name orbit-db` | a fixed name for later commands, instead of a random ID |
| `-e KEY=value` | set an environment variable inside the container |
| `-p 5432:5432` | publish container port 5432 on host port 5432 |
| `-v orbit_pgdata:/var/lib/postgresql/data` | mount the named volume `orbit_pgdata` where Postgres keeps its files |

`devpass` is a throwaway password for a laptop-only database; keep real secrets in a Git-ignored `.env` file ([Project setup & secrets](A02_project_setup_secrets.md)). The volume path suits `pg17` and older images; from PostgreSQL 18 the official image expects `/var/lib/postgresql`.

Now query it from your laptop. The script enables pgvector and asks for the distance between two 2-D vectors that form a 3-4-5 triangle, so you can check the answer in your head.

```python
# script_id: primer_a08/check_db
# Install: uv add "psycopg[binary]"
# Env: DATABASE_URL=postgresql://postgres:devpass@localhost:5432/postgres
# Services: the orbit-db container started with `docker run` above
import os

import psycopg

with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    version = conn.execute("SHOW server_version").fetchone()[0]
    pgvector = conn.execute(
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    ).fetchone()[0]
    # [1,2] -> [4,6] moves 3 across and 4 up, so the straight-line distance is 5.
    distance = conn.execute("SELECT '[1,2]'::vector <-> '[4,6]'::vector").fetchone()[0]

print(f"Postgres {version} | pgvector {pgvector}")
print(f"distance([1,2], [4,6]) = {distance}")
```

```text
Postgres 17.x (Debian ...) | pgvector 0.8.7
distance([1,2], [4,6]) = 5.0
```

Your version numbers will differ. Run `docker volume ls` and you'll see `orbit_pgdata`. It outlives `docker rm -f orbit-db`, and a new container started with the same `-v` flag picks up the same database files.

**Break it.** Two failures cause most first-day trouble:

- **Port already taken.** If a Homebrew Postgres or an older container holds 5432, `docker run` fails with an error ending in `port is already allocated` (another container) or `address already in use` (another program). Stop it, or map `-p 5433:5432` and use port 5433 in `DATABASE_URL`.
- **Connecting too early.** Postgres needs a few seconds on first start, so an early run fails with `connection to server at "127.0.0.1", port 5432 failed`. Wait for the "ready to accept connections" log line, or let Compose wait for you.

## Packaging Atlas with a Dockerfile

**The problem.** The database runs in a container, but the app still runs on your laptop's Python, and "install Python 3.12 and these packages first" drifts within a week. The app needs its own recipe card.

**The intuition.** A Dockerfile is that recipe card written down: start from this base, install these packages, copy this code, run this command. Docker saves each step as a **layer**, a cached filesystem snapshot, and reuses it when that step and every step above it are unchanged.

**A tiny example.** Below, `pip install` comes before `COPY app.py .`. Edit `app.py` and rebuild: the install layer comes from cache and only the copy reruns, so the build takes about a second. Swap the two lines and every code edit reinstalls psycopg.

The app is a tiny Atlas health service on the standard library's HTTP server:

```python
# script_id: primer_a08/app
# Atlas health service: GET /health reports whether Postgres and pgvector answer.
# Install: uv add "psycopg[binary]" (the Dockerfile installs it inside the image)
# Env: DATABASE_URL. Services: Postgres + pgvector (the `db` service in compose.yaml)
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]
PORT = int(os.environ.get("PORT", "8000"))
SQL = "SELECT extversion FROM pg_extension WHERE extname = 'vector'"


def db_status() -> dict[str, str]:
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
            row = conn.execute(SQL).fetchone()
        return {"db": "ok", "pgvector": row[0] if row else "not installed"}
    except psycopg.OperationalError as exc:
        # Report the failure instead of crashing, so a healthcheck can see it.
        return {"db": "down", "error": str(exc).splitlines()[0]}


class Health(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            return self.send_error(404)
        status = db_status()
        self.send_response(200 if status["db"] == "ok" else 503)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"service": "atlas", **status}).encode())


if __name__ == "__main__":
    # Bind 0.0.0.0: inside a container, 127.0.0.1 is unreachable from your laptop.
    print(f"atlas listening on 0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Health).serve_forever()
```

Save it as `app.py` next to this `Dockerfile`:

```dockerfile
FROM python:3.12-slim
# Without this, Python buffers print() and `docker logs` can stay empty.
ENV PYTHONUNBUFFERED=1
WORKDIR /app
# Dependencies before code, so this layer stays cached while you edit app.py.
RUN pip install --no-cache-dir "psycopg[binary]==3.3.*"
COPY app.py .
EXPOSE 8000
CMD ["python", "app.py"]
```

and a `.dockerignore`, which keeps files out of the **build context** (the folder Docker sends to the builder). The `.env` line matters most: a secret copied into an image ships to everyone who pulls it.

```text
.env
.venv/
.git/
__pycache__/
```

**Name the parts.** `FROM` picks the base image, `WORKDIR` sets the working folder, `RUN` executes a build-time command and saves a layer, `COPY` adds files from the build context, and `CMD` is what the container runs at start. `EXPOSE` only documents a port; you still need `-p` to publish it.

Build it and run it against `orbit-db`:

```bash
docker build -t atlas-app:dev .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql://postgres:devpass@localhost:5432/postgres \
  atlas-app:dev
# in a second terminal:
curl -s localhost:8000/health
```

```text
{"service": "atlas", "db": "down", "error": "connection failed: connection to server at \"127.0.0.1\", port 5432 failed: Connection refused"}
```

**Break it: the `localhost` trap.** This URL worked from your laptop a minute ago. Inside a container, `localhost` is the container itself, and Postgres lives in a different box. (Exact wording varies by platform.) The clean fix is to put both containers on one network and address the database by name, which is what Compose does. Press Ctrl+C to stop the app.

## Docker Compose: Atlas and Postgres in one file

**The problem.** Two long `docker run` commands must now run in order, share a network and wait for the database. Every teammate will type them slightly differently.

**The intuition.** A `compose.yaml` file is a written plan for your local stack: its services, open ports and volumes. `docker compose up` makes reality match the plan, and rerunning it changes only what differs.

**A tiny example.** Compose puts a project's services on one private network where each is reachable by its service name. The app connects to host `db`, not `localhost`, which fixes the previous section's bug.

The project folder looks like this:

```text
atlas-docker/
├── .env            # POSTGRES_PASSWORD=devpass  (listed in .gitignore)
├── .dockerignore
├── Dockerfile
├── app.py
└── compose.yaml
```

```yaml
services:
  db:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 10

  app:
    build: .
    environment:
      DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/postgres
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      # Slim images ship without curl, so the check uses Python's urllib.
      test: ["CMD", "python", "-c", "import urllib.request as u; u.urlopen('http://localhost:8000/health', timeout=3)"]
      interval: 10s
      retries: 3

volumes:
  pgdata:
```

**Name the parts.**

| Key | Plain meaning |
|---|---|
| `services` | the containers; each name is also its hostname on the shared network |
| `image` / `build` | pull a ready image, or build one from the Dockerfile in this folder |
| `${POSTGRES_PASSWORD:?...}` | read it from `.env` or your shell; refuse to start if it's missing |
| `healthcheck` | a command Docker runs inside the container on a timer; exit code 0 means healthy |
| `depends_on` + `service_healthy` | don't start `app` until `db` passes its healthcheck |
| `volumes` | named volumes Compose creates and keeps between runs |

```mermaid
sequenceDiagram
    participant You
    participant Compose
    participant DB as db (pgvector)
    participant App as app (Atlas)
    You->>Compose: docker compose up -d --build
    Compose->>Compose: build image, create network and volume
    Compose->>DB: start container
    loop every 5 seconds
        Compose->>DB: pg_isready
        DB-->>Compose: not ready yet, then ready
    end
    Compose->>App: start container, db is healthy
    You->>App: GET localhost:8000/health
    App->>DB: query using host "db"
    App-->>You: 200 with db ok
```

Start the stack. Free port 5432 first, since `orbit-db` still holds it:

```bash
cd atlas-docker
docker rm -f orbit-db
docker compose up -d --build
docker compose ps
curl -s localhost:8000/health
```

```text
NAME                 IMAGE                    ...   STATUS
atlas-docker-app-1   atlas-docker-app         ...   Up 12 seconds (healthy)
atlas-docker-db-1    pgvector/pgvector:pg17   ...   Up 18 seconds (healthy)
{"service": "atlas", "db": "ok", "pgvector": "not installed"}
```

If a status reads `(health: starting)`, wait ten seconds and retry. pgvector reads "not installed" because Compose created a fresh volume, `atlas-docker_pgdata`, so this is a brand-new database; the next section fixes that.

**Break it.** Rename `.env` and rerun `docker compose up`. Compose refuses to start: `required variable POSTGRES_PASSWORD is missing a value: set POSTGRES_PASSWORD in .env`. The `:?` guard blocks a silent empty password.

## Healthchecks, logs, exec and cleaning up

**The problem.** The app answers 503, or a container keeps exiting. You need to look inside a running box without rebuilding, and later tidy up without losing data you meant to keep.

**The intuition.** These are tools for a box you can't open by hand: a status light (`ps`, healthchecks), a window (`logs`), gloves that reach inside (`exec`) and a bin (`down`).

**Healthchecks.** Docker runs the `test` command inside the container every `interval`. Exit code 0 is a pass. After `retries` failures in a row, the status flips to `unhealthy`. Plain Docker and Compose only report that status; they don't restart the container for you.

**Logs.** Read what a container printed:

```bash
docker compose logs --tail 20 db   # last 20 lines from the database
docker compose logs -f app         # follow live; Ctrl+C stops following, not the app
```

```text
app-1  | atlas listening on 0.0.0.0:8000
app-1  | 127.0.0.1 - - [06/Nov/2026 10:15:02] "GET /health HTTP/1.1" 200 -
```

The second line is the app's own healthcheck calling it every ten seconds. If the first line never appears, check the Dockerfile for `PYTHONUNBUFFERED=1`.

**Exec.** `exec` runs a command inside a container that is already running. Use it to create the missing extension, then check the app again:

```bash
docker compose exec db psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
curl -s localhost:8000/health
docker compose exec app sh    # a shell inside the app container; type exit to leave
```

```text
CREATE EXTENSION
{"service": "atlas", "db": "ok", "pgvector": "0.8.7"}
```

**Cleaning up.** Containers, images and volumes pile up, and they differ in how much they hurt to lose:

| Command | What it removes | Named volumes (your data) |
|---|---|---|
| `docker compose stop` | nothing; containers stop and can start again | kept |
| `docker compose down` | the project's containers and network | kept |
| `docker compose down -v` | containers, network **and named volumes** | **deleted** |
| `docker image prune` | dangling images (old untagged builds) | kept |

```mermaid
stateDiagram-v2
    [*] --> Running: docker run or compose up
    Running --> Exited: process ends, or stop
    Exited --> Running: start
    Exited --> Removed: rm, or compose down
    Running --> Removed: rm -f
    Removed --> [*]
    note right of Removed: named volumes survive unless you pass -v
```

**Common mistake.** Running `docker compose down -v` to "reset things" and losing your index. After Day 26 that volume holds embedded Orbit docs, and rebuilding means paying for embedding calls again. Use plain `down`; add `-v` only when you mean "delete the database".

## Self-Check

1. You run `docker rm orbit-db`. What is gone, and what is still on your machine?

<details><summary>Answer</summary>

The container (its process and writable layer) is gone. The image is still cached, and the named volume `orbit_pgdata` still holds the database files, so the same `docker run` command brings your data back.

</details>

2. A compose file says `ports: ["5433:5432"]`. Which port does Postgres listen on inside the container, and which port goes in `DATABASE_URL` for a script on your laptop?

<details><summary>Answer</summary>

Postgres listens on 5432 inside the container (the right side). Your laptop script uses 5433 (the left side, the host port). Containers in the same Compose project still use `db:5432`.

</details>

3. A script on your laptop connects to `localhost:5432`, but the same URL fails with "Connection refused" inside the app container. Why, and what is the fix?

<details><summary>Answer</summary>

Inside a container, `localhost` is the container itself, and Postgres runs in a different container. Run both in one Compose project and use the service name as the host: `postgresql://postgres:...@db:5432/postgres`.

</details>

4. Why does the Dockerfile run `pip install` before `COPY app.py .`?

<details><summary>Answer</summary>

Layer caching. Docker reuses a layer when that step and every step above it are unchanged. With dependencies installed first, a code edit only invalidates `COPY` and later steps, so rebuilds take seconds.

</details>

5. What does `depends_on` with `condition: service_healthy` wait for, and how does `docker compose down` differ from `docker compose down -v`?

<details><summary>Answer</summary>

It waits until the `db` healthcheck (`pg_isready`) passes before starting `app`. `down` removes containers and the network but keeps named volumes; `down -v` also deletes the volumes, and with them your database.

</details>

## Learn More

- [Docker: Get started](https://docs.docker.com/get-started/): the official hands-on guide to images, containers, Dockerfiles and Compose.
- [Docker Compose quickstart](https://docs.docker.com/compose/gettingstarted/): builds a two-service Python app (Flask plus Redis), the same shape as this primer's stack.
- [Control startup order in Compose](https://docs.docker.com/compose/how-tos/startup-order/): the official page on `depends_on` and healthchecks, with a Postgres example.
- [pgvector on GitHub](https://github.com/pgvector/pgvector): the README covers the Docker image, distance operators and the indexes you'll use on Day 26.
