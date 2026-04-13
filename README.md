# Django DRF on AWS EC2 — Deployment Guide (uv)

A minimal Django REST Framework API deployed on AWS EC2 with Gunicorn + Nginx, managed with [uv](https://docs.astral.sh/uv/).

---

## Project Structure

```
aws-practice/
├── config/
│   ├── __init__.py
│   ├── settings.py       # All secrets via env vars
│   ├── urls.py
│   └── wsgi.py           # Gunicorn entry point
├── core/
│   ├── __init__.py
│   ├── views.py          # Health-check endpoint
│   └── urls.py
├── .env.example          # Template — copy to .env, never commit .env
├── .gitignore
├── pyproject.toml        # uv project + dependencies
├── uv.lock               # Locked dependency versions
├── gunicorn.service      # systemd service file
└── nginx.conf            # Nginx reverse proxy config
```

---

## Part 1 — Local Setup

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Sync dependencies (creates `.venv` automatically)

```bash
cd aws-practice
uv sync
```

> `uv sync` reads `pyproject.toml`, creates `.venv`, and installs all locked dependencies from `uv.lock`.

### 3. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` with real values:

```
SECRET_KEY=replace-with-a-long-random-string
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

> Generate a secret key:
> ```bash
> uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

### 4. Run locally

```bash
uv run python manage.py runserver
```

Test: `http://127.0.0.1:8000/api/health/` → `{"status": "ok"}`

---

## Part 2 — AWS EC2 Setup

### 1. Launch an EC2 instance

- AMI: **Ubuntu 22.04 LTS**
- Instance type: `t2.micro` (free tier)
- Key pair: create or use existing `.pem` file
- Storage: 8 GB gp2 (default is fine)

### 2. Configure Security Groups

In the EC2 console → Security Groups → Inbound Rules, add:

| Type  | Protocol | Port | Source       | Purpose            |
|-------|----------|------|--------------|--------------------|
| SSH   | TCP      | 22   | Your IP only | Remote access      |
| HTTP  | TCP      | 80   | 0.0.0.0/0    | Public web traffic |
| HTTPS | TCP      | 443  | 0.0.0.0/0    | SSL (optional)     |

> **Never open port 22 to `0.0.0.0/0`** — restrict SSH to your IP only.

### 3. Connect to your EC2 instance

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

---

## Part 3 — Server Setup on EC2

### 1. Update the system and install Nginx

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install nginx -y
```

### 2. Install uv on the server

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### 3. Clone your project

```bash
cd /home/ubuntu
git clone https://github.com/your-username/aws-practice.git
cd aws-practice
```

### 4. Sync dependencies with uv

```bash
uv sync
```

> This creates `.venv` and installs all packages from `uv.lock` — no manual pip or venv commands needed.

### 5. Create the `.env` file on the server

```bash
cp .env.example .env
nano .env
```

Set production values:

```
SECRET_KEY=your-real-secret-key
DEBUG=False
ALLOWED_HOSTS=<EC2-PUBLIC-IP>
```

> `DEBUG` must be `False` in production.

---

## Part 4 — Gunicorn Setup

### 1. Test Gunicorn manually

```bash
uv run gunicorn --bind 0.0.0.0:8000 config.wsgi:application
```

Visit `http://<EC2-PUBLIC-IP>:8000/api/health/` — if it responds, Gunicorn works.
Stop it with `Ctrl+C`.

### 2. Install the systemd service

```bash
sudo cp gunicorn.service /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn   # auto-start on reboot
```

### 3. Check Gunicorn status

```bash
sudo systemctl status gunicorn
```

You should see `active (running)`. If not, check logs:

```bash
sudo journalctl -u gunicorn -n 50
```

---

## Part 5 — Nginx Setup

### 1. Copy the Nginx config

```bash
sudo cp nginx.conf /etc/nginx/sites-available/aws-practice
sudo ln -s /etc/nginx/sites-available/aws-practice /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
```

### 2. Replace the placeholder in the config

```bash
sudo nano /etc/nginx/sites-available/aws-practice
```

Replace `your-ec2-public-ip` with your actual EC2 public IP.

### 3. Test and reload Nginx

```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 4. Test the live API

```
http://<EC2-PUBLIC-IP>/api/health/
```

Expected response: `{"status": "ok"}`

---

## Part 6 — How It All Connects

```
Internet
   │
   ▼
Nginx (port 80)       ← handles HTTP, acts as reverse proxy
   │
   ▼ (Unix socket)
Gunicorn              ← runs Django WSGI app, 3 worker processes
   │
   ▼
Django DRF App        ← reads secrets from .env via python-dotenv
```

- Nginx receives all public traffic on port 80
- Forwards to Gunicorn via a Unix socket (faster than TCP)
- Gunicorn runs multiple workers to handle concurrent requests
- Django reads `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` from `.env`

---

## Part 7 — Security Checklist

- [ ] `DEBUG=False` in production `.env`
- [ ] `SECRET_KEY` is long, random, and never committed to git
- [ ] `.env` is in `.gitignore`
- [ ] SSH port 22 restricted to your IP only in Security Group
- [ ] `ALLOWED_HOSTS` set to your EC2 IP / domain only
- [ ] Gunicorn bound to Unix socket, not a public port

---

## Part 8 — Useful Commands

| Task                     | Command                                               |
|--------------------------|-------------------------------------------------------|
| Sync dependencies        | `uv sync`                                             |
| Add a new package        | `uv add <package>`                                    |
| Remove a package         | `uv remove <package>`                                 |
| Run Django commands      | `uv run python manage.py <command>`                   |
| Run Gunicorn manually    | `uv run gunicorn config.wsgi:application`             |
| Restart Gunicorn         | `sudo systemctl restart gunicorn`                     |
| Restart Nginx            | `sudo systemctl restart nginx`                        |
| View Gunicorn logs       | `sudo journalctl -u gunicorn -n 50`                   |
| View Nginx error logs    | `sudo tail -f /var/log/nginx/error.log`               |
| Check Nginx config       | `sudo nginx -t`                                       |

---

## API Endpoints

| Method | URL          | Description  |
|--------|--------------|--------------|
| GET    | /api/health/ | Health check |
