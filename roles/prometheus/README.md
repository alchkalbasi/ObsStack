# Prometheus role

Deploys a pinned Prometheus container with Docker Compose and builds its scrape
targets entirely from Ansible inventory. The role supports deterministic hashmod
sharding, HA replica labels, Alertmanager endpoints, remote write, static and
inventory-defined alert rules, and optional TLS/basic-auth web configuration.

The role provisions the Prometheus server only. Exporters and Alertmanager are
managed elsewhere.

## Requirements

- Linux with Docker Engine and the Docker Compose v2 plugin
- Ansible Core 2.16 or newer
- `community.docker` collection 5.2.0 (see `collections/requirements.yml`)
- Privilege escalation for `/opt/observability` and `/var/lib/prometheus`
- Network access to the configured image registry, unless the image is preloaded
- `pytest` on the Molecule controller for filter-plugin unit tests

This role is container-only: it does not install a Prometheus binary, package,
or systemd unit, and it does not manage an existing native Prometheus service.
It keeps the existing `/var/lib/prometheus` data and, by default, recursively
assigns that tree to `prometheus_runtime_user`. Set
`prometheus_manage_data_ownership: false` only when storage permissions are
managed outside this role.

## How target discovery works

`prometheus_scrape_jobs` is the only target-definition mechanism. Each job names
one or more inventory groups and a port; the role resolves each host address in
this order:

1. `hostvars[host].prom_address`
2. `hostvars[host].ansible_host`
3. the inventory hostname

The optional `enabled_key` is matched against the host's `exporters_enabled`
mapping. This connects Prometheus discovery to the existing exporters role, so a
host is included only when that exporter is actually enabled. Omit `enabled_key`
for jobs managed outside that role.

```yaml
prometheus_scrape_jobs:
  node_exporter:
    port: 9100
    inventory_groups: [all]
    enabled_key: node_exporter
    labels:
      job_type: system
    per_host_labels:
      env: prom_env
      role: prom_role
      dc: prom_datacenter
```

Every host becomes one YAML `file_sd` entry with `instance_host`, static job
labels, and only the per-host labels whose source variables exist. Hosts shared
by multiple groups are deduplicated and targets are sorted. A YAML file is
generated for every job, including an empty list when no hosts match. Obsolete
YAML files and legacy JSON discovery files are pruned.

Target files never notify a handler: Prometheus watches them at the configured
refresh interval (30 seconds by default). Every shard receives identical files.
Hashmod relabeling in `prometheus.yml` assigns each address to exactly one shard,
and HA replicas with the same shard index scrape identical targets.

## Exporter jobs and rules

Defaults include jobs and generic alert files for every service currently
implemented by `roles/exporters`: Node Exporter, cAdvisor, Blackbox Exporter,
SNMP Exporter, PostgreSQL Exporter, Heplify, Promtail, and MKTXP. The files are
selected through `prometheus_rule_files`; remove a name in inventory to disable
that rule set. `prometheus-self.yml` is also provided but is opt-in because a
self-scrape job must first be defined in inventory.

Rule files are global and use labels such as `env`, `role`, and `dc`; do not fork
them by environment. Alertmanager should route severity using those labels. Put
site-specific rules in `prometheus_extra_rules`:

```yaml
prometheus_extra_rules:
  - name: api-slo
    rules:
      - alert: HighErrorRate
        expr: >-
          sum(rate(http_requests_total{code=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m])) > 0.02
        for: 10m
        labels:
          severity: page
        annotations:
          summary: Error rate above 2 percent for 10 minutes
```

The role stages `prometheus.yml`, web configuration, and all selected rules. It
runs the image's own `promtool` in short-lived containers for `check config`,
`check web-config` when applicable, `check rules`, and each configured rule unit
test before copying files to the live tree. Only promoted config/rule changes
notify the Compose SIGHUP reload handler. Compose or environment changes recreate
the container through `community.docker.docker_compose_v2`.

## Variables

### Installation and paths

| Variable | Default | Purpose |
| --- | --- | --- |
| `prometheus_version` | `3.14.0` | Version used by the default image tag |
| `prometheus_image` | `quay.io/prometheus/prometheus:v3.14.0` | Prometheus container image |
| `prometheus_container_name` | `prometheus` | Container name |
| `prometheus_runtime_user` | `65534:65534` | Numeric container UID and GID |
| `prometheus_pull_policy` | `missing` | Compose image pull policy |
| `prometheus_compose_wait_timeout` | `120` | Compose health wait timeout in seconds |
| `prometheus_observability_dir` | `/opt/observability` | Shared observability root |
| `prometheus_dir` | `<observability_dir>/prometheus` | Compose project directory |
| `prometheus_owner` / `prometheus_group` | `ansible_user` | Host ownership for project files |
| `prometheus_config_dir` | `<prometheus_dir>/config` | Host configuration directory |
| `prometheus_rules_dir` | `<config_dir>/rules` | Live rule files |
| `prometheus_file_sd_dir` | `<config_dir>/file_sd` | Live YAML discovery files |
| `prometheus_staging_dir` | `<config_dir>/.staging` | Validation tree |
| `prometheus_data_dir` | `/var/lib/prometheus` | TSDB data |
| `prometheus_manage_data_ownership` | `true` | Recursively make existing TSDB data writable by the container UID/GID |
| `prometheus_restart_policy` | `unless-stopped` | Container restart policy |

### Runtime and topology

| Variable | Default | Purpose |
| --- | --- | --- |
| `prometheus_bind_ip` | `127.0.0.1` | Host address for the published HTTP port |
| `prometheus_web_listen_address` | `<bind_ip>:9090` | Published host address and port |
| `prometheus_external_url` | empty | Public URL when served behind a proxy |
| `prometheus_retention_time` | `30d` | Time-based TSDB retention |
| `prometheus_retention_size` | empty | Optional size-based TSDB retention |
| `prometheus_scrape_interval` | `30s` | Global scrape interval |
| `prometheus_evaluation_interval` | `30s` | Global rule interval |
| `prometheus_scrape_timeout` | `10s` | Global scrape timeout |
| `prometheus_file_sd_refresh_interval` | `30s` | File-based discovery refresh interval |
| `prometheus_shard_count` | `1` | Total scrape shards |
| `prometheus_shard_index` | `0` | Zero-based shard assigned to this host |
| `prometheus_replica` | `a` | HA replica label unique within a shard |
| `prometheus_cluster` | `observability` | Global-layer cluster label |
| `prometheus_region` | `default` | Global-layer region label |
| `prometheus_extra_flags` | `[]` | Extra Prometheus CLI flags |

### Configuration data

| Variable | Default | Purpose |
| --- | --- | --- |
| `prometheus_alertmanagers` | `[]` | Existing Alertmanager `host:port` endpoints |
| `prometheus_scrape_jobs` | Eight exporter jobs | Inventory-driven job definitions |
| `prometheus_rule_files` | Eight exporter rule files | Static role rule selection |
| `prometheus_extra_rules` | `[]` | Site-specific rule groups rendered to one file |
| `prometheus_remote_write` | `[]` | Remote-write mappings for Mimir/Thanos Receive |
| `prometheus_web_config` | `{}` | Prometheus web config; bcrypt hashes required |
| `prometheus_basic_auth_users` | `{}` | Basic-auth users rendered under `basic_auth_users`; bcrypt hashes required |
| `prometheus_rule_test_dir` | empty | Remote directory searched recursively for rule tests |
| `prometheus_rule_test_files` | `[]` | Additional remote files passed to `promtool test rules` |

Each job requires `port` and `inventory_groups`. Optional keys are `enabled_key`,
`labels`, `per_host_labels`, `metrics_path`, `scrape_interval`, `scrape_timeout`,
and `scheme`.

Enable Prometheus basic auth by setting bcrypt password hashes in inventory:

```yaml
prometheus_basic_auth_users:
  admin: "$2y$12$replace_with_bcrypt_hash"
```

When either `prometheus_web_config` or `prometheus_basic_auth_users` is set, the
role renders `web-config.yml`, validates it with `promtool check web-config`,
and starts Prometheus with `--web.config.file=/etc/prometheus/web-config.yml`.

## Day-to-day operations

| Operation | Edit only | Change |
| --- | --- | --- |
| Add/remove a host | `inventory.yml` | Membership in a job's inventory group |
| Enable an exporter on a host | `group_vars` or `host_vars` | Matching `exporters_enabled` key |
| Add an exporter type | `group_vars` | One `prometheus_scrape_jobs` block |
| Add a generic alert | `roles/prometheus/files/rules/<name>.yml` | Add/select one reusable static rule file |
| Add a site-specific alert | `group_vars` | Add a group under `prometheus_extra_rules` |
| Add a shard or HA replica | inventory and its `host_vars` | Add host, shard index, and replica label |
| Change a target label | `group_vars` or `host_vars` | Job label mapping or source hostvar |
| Tune a scrape interval | `group_vars` | Global variable or job override |

## Example and execution

The [`example/`](example/) directory contains a two-shard, two-replica inventory,
group variables, host variables, remote write, exporter enablement, and custom
rules.

```bash
ansible-playbook \
  -i roles/prometheus/example/inventory.yml \
  roles/prometheus/example/playbook.yml
```

The consuming play should use `serial: 1` or `serial: "50%"` so HA replicas and
shards are never reloaded simultaneously.

Run filter tests and the full Molecule scenario with:

```bash
python3 -m pytest roles/prometheus/filter_plugins/tests
cd roles/prometheus && molecule test
```
