# Alertmanager role

Deploys a pinned `prom/alertmanager` container with Docker Compose. `config.yml`
is rendered from a Jinja2 template and validated with `amtool` before it
replaces the live file. Notification templates are copied from
[files/templates/](files/templates/).

```text
/opt/services/observability/alertmanager/
├── .env           # mode 0600; image, listen address, runtime flags
├── compose.yml
├── config.yml     # root:65534 0640; may contain SMTP passwords and tokens
└── templates/
    ├── common.tmpl
    ├── email.tmpl
    ├── slack.tmpl
    └── telegram.tmpl
/var/lib/alertmanager/   # silences and notification log
```

The role runs a single instance with clustering disabled.

## Requirements

- Linux with Docker Engine and the Docker Compose v2 plugin
- Ansible Core 2.16 or newer
- `community.docker` collection 5.2.0 (see `collections/requirements.yml`)
- Privilege escalation, and facts gathered before the role runs

## Usage

Add the host to your inventory and define real receivers. The defaults are
valid but only contain a `default` receiver that discards notifications.

```yaml
alertmanager_bind_ip: 172.16.154.20
alertmanager_route_receiver: team-chat
alertmanager_receivers:
  - name: team-chat
    slack_configs:
      - api_url: "{{ vault_alertmanager_mattermost_webhook }}"
        channel: "#alerts"
        send_resolved: true
```

See [example/group_vars/alertmanager_servers.yml](example/group_vars/alertmanager_servers.yml)
for routing, time intervals, Telegram, email and Mattermost receivers.

```bash
ansible-playbook -i inventories/staging/hosts.yml playbook.yml \
  --limit alertmanager --tags alertmanager --ask-vault-pass
```

Point Prometheus at it with `prometheus_alertmanagers: ["172.16.154.20:9093"]`.
Alertmanager binds to `127.0.0.1:9093` by default. A Prometheus container in
its own Compose project cannot reach the host's loopback address, so set
`alertmanager_bind_ip` to an address it can reach.

## Configuration

[templates/config.yml.j2](templates/config.yml.j2) mirrors the Alertmanager
file section by section. Each section takes its values from one group of
variables in [defaults/main.yml](defaults/main.yml):

| Section | Variables |
| --- | --- |
| `global` | `alertmanager_resolve_timeout`, `alertmanager_smtp_*`, `alertmanager_global_extra` |
| `templates` | fixed: `/etc/alertmanager/templates/*.tmpl` |
| `route` | `alertmanager_route_*` (root route), `alertmanager_routes` (child routes) |
| `inhibit_rules` | `alertmanager_inhibit_rules` |
| `time_intervals` | `alertmanager_time_intervals` |
| `receivers` | `alertmanager_receivers` |

Child routes, inhibit rules, time intervals and receivers use native
[Alertmanager syntax](https://prometheus.io/docs/alerting/latest/configuration/)
and are written out as given. Keep tokens, webhooks and passwords in Ansible Vault.

The default root route groups by `alertname`, `env` and `dc`. The default
inhibit rule mutes `severity="warning"` alerts while a `severity="page"` alert
fires for the same `env` and `instance`. These match the labels and severities
used by the prometheus role's rule files.

## Notification templates

Every `*.tmpl` file directly in `alertmanager_templates_src` (default: this
role's `files/templates/`) is copied to `templates/`. Deployed `.tmpl` files
without a source file are removed.

The shipped templates redefine Alertmanager's built-in template names
(`telegram.default.message`, `slack.default.title`, `slack.default.text`,
`email.default.subject`). Receivers therefore pick them up without setting
`message`, `title` or `text`. This matters in inventory: Go template syntax
such as `{{ template "x" . }}` would otherwise be evaluated by Ansible's Jinja2.
If you do need it in a variable, mark the value `!unsafe`.

To customize the templates, edit the files in `files/templates/`, or point
`alertmanager_templates_src` at your own controller directory.

## Validation and reload

1. The variables are checked, including that each receiver name is unique
   and that the root route's receiver exists.
2. `docker compose config --quiet` validates the Compose project.
3. The candidate `config.yml` is checked with `amtool check-config` from the
   deployed image, including every template it loads. A failing check
   leaves the live file untouched.
4. When only templates changed, the live config is checked again with the new
   templates.
5. Changes trigger `POST /-/reload` inside the container. A rejected reload
   fails the play.

Changes to `compose.yml` or `.env` recreate the container.

The project directory is mounted read-only at `/etc/alertmanager`, not
`config.yml` on its own. Ansible replaces files atomically, and a single-file
bind mount would keep serving the old inode.

## Tags

- `alertmanager`: full deployment.
- `alertmanager-install`: directories, Compose project, `.env`, image.
- `alertmanager-config`, `alertmanager-templates`: `config.yml` and templates, then reload.
- `alertmanager-deploy`: apply the Compose project.
