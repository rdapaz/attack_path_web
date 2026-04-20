# Attack Path Visualizer (Web)

A FastAPI + React port of the PySide6 desktop [attack_path_visualizer](https://github.com/rdapaz/attack_path_visualizer). Upload a PAN-OS `set`-command firewall config, parse it into a SQLite attack-path matrix, analyse host- and zone-level reachability, annotate policies, and export to Mermaid / CSV / YAML / Excel.

Designed to deploy on a single AWS EC2 free-tier instance via CloudFormation.

---

## Security model

- **The repo contains source code only.** Firewall configs and the generated SQLite database must NEVER be committed.
- Uploaded firewall configs are stored at `/var/lib/attack-path/uploads/` on the EC2 instance (on EBS).
- The SQLite DB is at `/var/lib/attack-path/attack_paths.db`.
- There is **no authentication**. Only bind this app to networks you trust, or restrict the Security Group to your own IP.

---

## Local development

### Backend

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv venv
uv pip install -e .
.venv/bin/uvicorn app.main:app --reload --port 8000
```

API docs: <http://127.0.0.1:8000/docs>

### Frontend

Requires Node 20+.

```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173  (proxies /api to :8000)
```

---

## AWS deployment (click-ops via CloudFormation)

### Prerequisites

1. An AWS account.
2. **A public GitHub repo** containing this project. The EC2 instance clones from it on first boot.
   ```bash
   cd /Users/ricdeez/Projects/attack_path_web
   git init
   git add .
   git commit -m "initial"
   gh repo create attack_path_web --public --source=. --push   # or use the GitHub UI
   ```
3. An **EC2 Key Pair** in your target region (Console → EC2 → Key Pairs → Create key pair → RSA, `.pem`). Download the `.pem` file — you'll need it for SSH.

### Deploy

1. Open the **CloudFormation** console in your region (**ap-southeast-2** Sydney or **ap-southeast-4** Melbourne).
2. Click **Create stack → With new resources (standard)**.
3. **Specify template** → *Upload a template file* → choose `infra/cloudformation.yaml`. Click **Next**.
4. **Stack name**: `attack-path`.
5. Fill in parameters:
   - **RepoUrl**: `https://github.com/<you>/attack_path_web.git`
   - **RepoBranch**: `main`
   - **KeyPairName**: select the key pair you created.
   - **YourIpCidr**: `x.y.z.w/32` (your public IP, `curl ifconfig.me`). You can leave `0.0.0.0/0` for testing but that opens SSH to the world — don't.
   - **InstanceType**: `t2.micro` (free-tier in both Sydney and Melbourne).
6. **Next → Next → Submit.**
7. Wait for `CREATE_COMPLETE` (~2 minutes for infra, then ~5 more for UserData to finish inside the instance).
8. Open the **Outputs** tab → click **WebUrl**.

### Watching the bootstrap

UserData logs to `/var/log/user-data.log` on the instance:

```bash
ssh -i KEY.pem ec2-user@<EIP>
sudo tail -f /var/log/user-data.log
```

Services:

```bash
sudo systemctl status attack-path      # FastAPI
sudo systemctl status nginx            # reverse proxy
```

### Updating the deployed app

Push changes to the GitHub repo, then on the instance:

```bash
cd /opt/attack-path/src
sudo -u ec2-user git pull

# Rebuild frontend
cd /opt/attack-path/frontend
sudo -u ec2-user npm ci && sudo -u ec2-user npm run build
sudo cp -r dist/. /var/www/attack-path/
sudo chown -R nginx:nginx /var/www/attack-path

# Reinstall backend deps if pyproject changed, then restart
cd /opt/attack-path/backend
sudo -u ec2-user .venv/bin/pip install -e .
sudo systemctl restart attack-path
```

### Tearing down

CloudFormation → select the stack → **Delete**. This removes the VPC, EC2, EIP, and EBS volume. Uploaded firewall configs and the SQLite DB are destroyed with the volume — keep local copies if you need them.

---

## Free-tier cost notes (first 12 months, us-east-1 as reference)

| Resource | Free-tier allowance | This stack uses |
|---|---|---|
| EC2 t2.micro / t3.micro | 750 hours/month (one instance 24/7) | 1 instance |
| EBS gp3 | 30 GB | 20 GB |
| Elastic IP | Free while attached to a running instance | 1 attached |
| Data transfer out | 100 GB/month | minimal |
| CloudFormation | Free | 1 stack |

**After the 12-month free period** this runs approximately $8–12/month depending on region.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  EC2 t2.micro (Amazon Linux 2023)                          │
│                                                            │
│  ┌──────────┐    proxy /api       ┌──────────────────┐    │
│  │  nginx   │ ───────────────────▶│  uvicorn :8000   │    │
│  │  :80     │                     │  FastAPI         │    │
│  │          │                     │  (systemd)       │    │
│  │  /var/www│◀── static SPA       └────────┬─────────┘    │
│  │  (dist)  │                              │              │
│  └──────────┘                              ▼              │
│                                     ┌──────────────┐      │
│                                     │  /var/lib/   │      │
│                                     │  attack-path │      │
│                                     │  attack_paths.db    │
│                                     │  uploads/*.txt      │
│                                     └──────────────┘      │
└────────────────────────────────────────────────────────────┘
          │                                     │
          ▼                                     ▼
    User browser                       [ EBS 20GB gp3 ]
```

---

## Project layout

```
attack_path_web/
├── backend/             FastAPI app
│   ├── app/
│   │   ├── main.py                 app factory + CORS + router wiring
│   │   ├── config.py               env-var config
│   │   ├── db.py                   sqlite connection helpers
│   │   ├── api/                    HTTP routes
│   │   │   ├── pipeline.py         POST /api/pipeline/build
│   │   │   ├── targets.py          GET  /api/targets
│   │   │   ├── analyze.py          POST /api/analyze
│   │   │   ├── annotations.py      CRUD /api/annotations
│   │   │   ├── exports.py          POST /api/export/*
│   │   │   └── settings.py         GET/PUT /api/settings/categories
│   │   └── services/               business logic (Qt-free, ported)
│   │       ├── pipeline.py         attack_path_pipeline.py (verbatim)
│   │       ├── mermaid.py          generate_mermaid()
│   │       ├── exports.py          CSV / YAML / Excel
│   │       └── rowcolor.py         row-highlight classifier
│   └── pyproject.toml
├── frontend/            React + Vite + TypeScript
│   ├── src/
│   │   ├── App.tsx                 sidebar nav
│   │   ├── api/client.ts           typed fetch wrappers
│   │   └── components/
│   │       ├── BuildView.tsx       firewall.txt upload + pipeline
│   │       ├── ViewerView.tsx      target grid + filters + exports
│   │       ├── AnnotationModal.tsx policy classification dialog
│   │       ├── MermaidPreview.tsx  client-side Mermaid renderer
│   │       └── SettingsView.tsx    annotation categories editor
│   └── package.json
├── deploy/              Runtime config baked into the EC2 instance
│   ├── nginx.conf
│   └── systemd/attack-path.service
├── infra/
│   └── cloudformation.yaml         single-click deploy template
└── README.md
```

---

## API reference

Once running, the full interactive OpenAPI docs are at **`/docs`**. Summary:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/pipeline/build` | Upload firewall.txt, rebuild DB |
| GET | `/api/pipeline/status` | DB presence + size |
| GET | `/api/targets?mode=host\|zone&source=exploded\|grouped` | List destinations |
| POST | `/api/analyze` | Query rows for a target |
| GET/PUT/DELETE | `/api/annotations/{policy_name}` | Policy annotations |
| GET | `/api/annotations` | List all annotations |
| POST | `/api/export/mermaid` | Mermaid diagram |
| POST | `/api/export/csv` | Pipe-delimited CSV |
| POST | `/api/export/yaml` | YAML |
| POST | `/api/export/excel` | XLSX (pass `full_policies: true` for full export) |
| GET/PUT | `/api/settings/categories` | Annotation category list |
| GET | `/api/health` | Liveness |

---

## License

Same as the parent project (see [LICENSE](LICENSE) once you copy it across).
