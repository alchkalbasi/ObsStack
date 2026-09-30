# Wazuh

Deploys a single-node Wazuh stack (manager, indexer, dashboard) with Docker
Compose. It follows the official
[wazuh-docker single-node](https://github.com/wazuh/wazuh-docker/tree/main/single-node)
layout, so the upstream Docker docs apply directly on the host.

```text
/opt/services/security/wazuh/
├── .env                              # mode 0600; versions, ports and passwords
├── compose.yml                       # manager, indexer, dashboard (+ one-shot cert job)
└── config/
    ├── certs.yml                     # input for the certificate generator
    ├── wazuh_indexer_ssl_certs/      # generated once, never overwritten
    ├── wazuh_cluster/wazuh_manager.conf
    ├── wazuh_indexer/{wazuh.indexer.yml,internal_users.yml}
    └── wazuh_dashboard/{opensearch_dashboards.yml,wazuh.yml}
```

Everything runs in containers. Docker's restart policy (`unless-stopped`)
brings the stack back after a reboot; there is no systemd unit. Persistent data
lives in named Docker volumes (`wazuh_*`).

## Requirements

- Linux host with Docker Engine and Docker Compose v2 already installed.
- At least 4 CPUs and 8 GiB RAM for a small deployment.
- Internet access from the host on the first run: the certificate generator
  downloads the Wazuh cert tool.
- On the controller: the `community.docker` collection, plus `passlib` and
  `bcrypt<5`. `password_hash('bcrypt')` needs these to hash the indexer
  passwords:

  ```bash
  pip install passlib 'bcrypt<5'
  ```

## Usage

```yaml
wazuh_indexer_password: "{{ vault_wazuh_indexer_password }}"
wazuh_dashboard_password: "{{ vault_wazuh_dashboard_password }}"
wazuh_api_password: "{{ vault_wazuh_api_password }}"
```

Passwords must be 8–64 characters long and contain upper case, lower case, a
digit and a symbol. They must not contain `$` or `&`. See
[example/](example/) for an inventory, playbook and group vars.

```bash
ansible-playbook -i inventories/production/hosts.yml roles/wazuh/example/playbook.yml --ask-vault-pass
```

The dashboard is at `https://<host>/`; log in as `admin` with
`wazuh_indexer_password`.

## Settings

See [defaults/main.yml](defaults/main.yml).

| Variable | Default | Purpose |
| --- | --- | --- |
| `wazuh_version` | `4.14.8` | Image tag for manager, indexer and dashboard |
| `wazuh_certs_generator_tag` | `0.0.4` | `wazuh/wazuh-certs-generator` tag for that release |
| `wazuh_dir` | `/opt/services/security/wazuh` | Compose project directory |
| `wazuh_indexer_heap` | `1g` | Indexer JVM heap |
| `wazuh_agent_listen` | `0.0.0.0:1514` | Agent events |
| `wazuh_enrollment_listen` | `0.0.0.0:1515` | Agent enrollment |
| `wazuh_api_listen` | `127.0.0.1:55000` | Manager API |
| `wazuh_indexer_listen` | `127.0.0.1:9200` | Indexer API |
| `wazuh_dashboard_listen` | `0.0.0.0:443` | Dashboard (HTTPS) |
| `wazuh_indexer_password` | required | Indexer `admin` user (dashboard login) |
| `wazuh_dashboard_password` | required | Indexer `kibanaserver` user |
| `wazuh_api_password` | required | Manager API `wazuh-wui` user |
| `wazuh_manager_config` | bundled upstream `ossec.conf` | Controller path of the manager config |
| `wazuh_manage_sysctl` | `true` | Set `vm.max_map_count=262144` |
| `wazuh_restart_policy`, `wazuh_pull_policy`, `wazuh_compose_wait_timeout` | `unless-stopped`, `missing`, `600` | Compose behaviour |

## What the role does

1. Validates settings and password strength.
2. Sets `vm.max_map_count` and writes `compose.yml`, `.env` and the component configs.
3. Runs the official certificate generator (`docker compose run --rm wazuh.certs`)
   only when `config/wazuh_indexer_ssl_certs/root-ca.pem` is missing.
4. Runs `docker compose up` and waits until every container is healthy.
   Containers are recreated when a bind-mounted config file changes.
5. Runs `securityadmin.sh` inside the indexer when `internal_users.yml` changes,
   so indexer password changes also reach a running cluster.

## Operations

```bash
cd /opt/services/security/wazuh
docker compose ps                   # status and health
docker compose logs -f wazuh.manager
docker compose restart wazuh.dashboard
docker compose down                 # stop; data volumes are kept
```

- **Upgrade:** back up the volumes, then change `wazuh_version` and the matching
  `wazuh_certs_generator_tag` and re-run the role. Read the Wazuh release notes
  first.
- **Rotate certificates:** remove `config/wazuh_indexer_ssl_certs/` and re-run
  the role. Agents that pin the old CA must be updated.
- **Change the API password:** `wazuh-wui` is created from `API_PASSWORD` when
  the manager volumes are first initialised. Later changes may not reach the
  existing user, so change the password through the Wazuh API first, then
  update `wazuh_api_password`. The manager health check fails if the two
  don't match.
- **Custom manager config:** copy
  `files/wazuh/config/wazuh_cluster/wazuh_manager.conf`, edit it, and point
  `wazuh_manager_config` at your copy.
