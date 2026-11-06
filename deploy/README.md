# Running Job Radar on a home server (Docker)

Job Radar runs in Docker on an always-on Ubuntu machine, reachable from any
device on your Wi-Fi at `http://<server-ip>:8000`. The server holds the one
real database. Updating it to the latest code on GitHub is one command.

- **What runs:** the web app (every page, scans, backups, Ask AI through
  Ollama's cloud). **Apply** (the pre-filled Greenhouse form) needs a browser
  window, so it's off on the server: open the posting and apply there.
- **Where your data is:** `~/job-radar/data` on the server (database,
  backups, removed-company archives). The image holds only code.
- **No login:** keep it on your home network. Don't forward port 8000 on the
  router. For access away from home, use Tailscale rather than opening ports.

Below, `you@server` is your user and the server's address (for example
`ananthu@192.168.1.50`); `~` is your home folder on the server.

## 1. Once: set up the server

On the **server** (Docker is already there for Immich and Navidrome):

```bash
# The code
git clone https://github.com/Ananthakrishnan-Jayadev/job-radar.git ~/job-radar
cd ~/job-radar
mkdir -p data

# Your user and group ids, so files in data/ stay yours
echo "UID=$(id -u)" > .env
echo "GID=$(id -g)" >> .env
```

## 2. Once: move your data over from the laptop

On the **laptop**, in the project folder. Stop `jobradar serve` first
(Ctrl+C), so nothing changes while you copy.

```bash
# A checked copy of the database (safe and consistent)
.venv/bin/jobradar backup --out /tmp/jobradar-move --note move

# Send it, your settings, and the removed-company archives
scp /tmp/jobradar-move/jobradar-backup-*-move.db you@server:~/job-radar/data/jobradar.db
scp config.local.toml you@server:~/job-radar/config.local.toml
scp data/removed-companies-* you@server:~/job-radar/data/
```

From now on the **server's database is the real one**. Don't keep using the
laptop's `data/jobradar.db` for your tracking, or the two drift apart (see
step 7 for working on a copy).

## 3. Once: Ollama's cloud key (for "Ask AI")

Make an API key at <https://ollama.com/settings/keys>. On the **server**:

```bash
cd ~/job-radar
echo "OLLAMA_API_KEY=paste-your-key-here" >> .env
chmod 600 .env
```

Then point Job Radar at the cloud: add this to `~/job-radar/config.local.toml`
on the server (the model name in the cloud may differ from the local
`gemma4:31b-cloud`; list yours with the `curl` line below):

```toml
[ollama]
url = "https://ollama.com"
model = "gemma4:31b"
```

```bash
# Which models your key can use (pick one for "model" above)
curl -s https://ollama.com/api/tags -H "Authorization: Bearer $(grep OLLAMA_API_KEY .env | cut -d= -f2)" | head -c 600
```

`.env` and `config.local.toml` are git-ignored: they never reach GitHub.

## 4. Start it

On the **server**:

```bash
cd ~/job-radar
./deploy/deploy.sh
```

The first build takes a few minutes (it builds the web UI, then the app).
When it prints `up at http://...:8000`, open that address on your laptop or
phone. Check your jobs and statuses are all there.

It restarts by itself after a crash or a reboot (`restart: unless-stopped`).

## 5. Once: scheduled scans and nightly backups

On the **server**, `crontab -e`, then paste the lines from
`deploy/crontab.example`, with `/home/YOU` changed to your home folder
(`echo $HOME` shows it):

- a scan every morning at 7:00, so new jobs are waiting for you;
- a checked copy of the database every night at 3:00, keeping the last 14
  (`BACKUP_COPY_DIR=/some/other/disk` also copies each one off the laptop's
  disk; worth it, old laptop disks fail).

What they did is logged in `~/job-radar/data/cron.log`.

## 6. Every update afterwards

After new changes are pushed to GitHub (`main`), from the **laptop**:

```bash
ssh you@server '~/job-radar/deploy/deploy.sh'
```

It backs up the database (`data/jobradar-backup-*-before-deploy.db`), pulls
the code, rebuilds, restarts, and waits until the app answers. Your data is
untouched; the database upgrades itself if a new version needs it.

**If an update goes wrong**, go back to the previous code and rebuild:

```bash
cd ~/job-radar
git log --oneline -5          # find the last good commit
git checkout <commit>
docker compose up -d --build
# later, back to the latest: git checkout main && ./deploy/deploy.sh
```

If the database itself needs restoring, stop the app, copy the
`before-deploy` backup over it, start again:

```bash
docker compose stop jobradar
cp data/jobradar-backup-<date>-before-deploy.db data/jobradar.db
rm -f data/jobradar.db-wal data/jobradar.db-shm
docker compose start jobradar
```

## 7. Working on the code with real data

To try changes on the laptop against your real jobs, use a fresh copy of
the server's database, never the other way round:

```bash
ssh you@server 'cd ~/job-radar && docker compose exec -T jobradar jobradar backup --note for-laptop'
scp "you@server:~/job-radar/data/jobradar-backup-*-for-laptop.db" /tmp/
.venv/bin/jobradar --db /tmp/jobradar-backup-<date>-for-laptop.db serve
```

Statuses you change on that copy stay on the laptop; make real decisions on
the server.

## Everyday commands (on the server, in `~/job-radar`)

```bash
docker compose ps                                      # is it running?
docker compose logs -f jobradar                        # its log (Ctrl+C to stop following)
docker compose restart jobradar                        # restart it
docker compose exec jobradar jobradar backup           # a backup now
docker compose exec jobradar jobradar scan             # a scan in the terminal
docker compose exec jobradar jobradar failing-boards   # boards that keep failing
docker compose down                                    # stop it (data stays)
```
