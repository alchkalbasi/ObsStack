# Exporters role

Deploys Node Exporter, cAdvisor, Blackbox Exporter, SNMP Exporter, PostgreSQL
Exporter, Heplify, Promtail, and MKTXP. The containerized services use Docker Compose;
Heplify uses the upstream standalone Linux binary and systemd.

For each containerized service, the role installs a static `compose.yml` and
renders host-specific values into a separate `.env` file. For Heplify, it
installs the executable, renders `heplify.json`, and manages a systemd unit.

All directories and files managed by the containerized exporters use the
Ansible connection user and group by default. Override `exporters_owner` or
`exporters_group` when the connection user's primary group has a different name.
Heplify's binary, configuration, data directory, and systemd unit remain owned
by `root`.

## Requirements

- Linux host with systemd
- Docker Engine and the Docker Compose v2 plugin for containerized exporters
- `community.docker` Ansible collection
- Privilege escalation, because the role writes under `/opt` and talks to Docker

Install the pinned collection dependency with:

```bash
ansible-galaxy collection install -r collections/requirements.yml
```

Node Exporter uses the host network, PID, and UTS namespaces and mounts `/`
read-only. These settings are required for a containerized exporter to report the
host rather than its own container namespaces.

cAdvisor runs privileged and mounts the host root filesystem, runtime state,
sysfs, Docker data, and `/dev/kmsg`. These are required to discover containers
and collect their resource metrics.

Blackbox Exporter runs with only the `NET_RAW` capability in addition to its
read-only filesystem. The capability is required by the default ICMP probe module.

SNMP Exporter runs as an unprivileged user with a read-only filesystem and all
Linux capabilities dropped. Its generated configuration is installed with
group-read-only permissions because it can contain SNMP authentication data.

PostgreSQL Exporter uses host networking so it can reach a PostgreSQL server
bound to the host loopback interface. It runs as the upstream unprivileged
UID/GID 65534 with a read-only filesystem and no Linux capabilities. The role
writes the database password to a group-readable file and configures
`DATA_SOURCE_PASS_FILE`; the password is never put in the container environment.

Heplify is installed from a pinned, SHA-256-verified upstream binary for amd64
or arm64. A controller-local binary can be used instead for offline deployment.
Its JSON configuration is stored with mode `0600` because it can contain the
HEP authentication password.

## Node Exporter variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.node_exporter` | `false` | Enables deployment on a host |
| `exporters_node_exporter_image` | `quay.io/prometheus/node-exporter:v1.12.1` | Pinned image reference; a digest is also accepted |
| `exporters_node_exporter_bind_ip` | `127.0.0.1` | Host IP Node Exporter binds to; override per host with a private IP |
| `exporters_node_exporter_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_node_exporter_extra_args` | `[]` | Additional Node Exporter CLI arguments |
| `exporters_node_exporter_filesystem_mount_points_exclude` | Upstream-compatible regex | Filesystem mount points excluded from metrics |

Node Exporter binds to `127.0.0.1:9100` by default. Set `exporters_node_exporter_bind_ip`
to a private interface for remote scraping and enforce access with the host firewall.
Node Exporter does not enable authentication by default.

## cAdvisor variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.cadvisor` | `false` | Enables deployment on a host |
| `exporters_cadvisor_image` | `ghcr.io/google/cadvisor:v0.60.5` | Pinned image reference; a digest is also accepted |
| `exporters_cadvisor_bind_ip` | `127.0.0.1` | Host IP cAdvisor binds to; override per host with a private IP |
| `exporters_cadvisor_docker_data_dir` | `/var/lib/docker` | Docker data root mounted for container discovery |
| `exporters_cadvisor_kmsg_device` | `/dev/kmsg` | Host kernel message device passed to cAdvisor |
| `exporters_cadvisor_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_cadvisor_extra_args` | `[]` | Additional cAdvisor CLI arguments |

Restrict `exporters_cadvisor_bind_ip` to a trusted interface or with the host
firewall. cAdvisor exposes container metadata and does not enable
authentication by default.

## Blackbox Exporter variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.blackbox_exporter` | `false` | Enables deployment on a host |
| `exporters_blackbox_exporter_image` | `quay.io/prometheus/blackbox-exporter:v0.28.0` | Pinned image reference; a digest is also accepted |
| `exporters_blackbox_exporter_bind_ip` | `127.0.0.1` | Host IP Blackbox Exporter binds to; override per host with a private IP |
| `exporters_blackbox_exporter_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_blackbox_exporter_extra_args` | `[]` | Additional Blackbox Exporter CLI arguments |
| `exporters_blackbox_exporter_modules` | HTTP, TCP, ICMP, DNS, and TLS modules | Complete probe module mapping rendered under `modules` |

`blackbox_modules` is accepted as an inventory-compatible alias for
`exporters_blackbox_exporter_modules`.

Restrict `exporters_blackbox_exporter_bind_ip` to Prometheus or another
trusted network. Customize `exporters_blackbox_exporter_modules` when probes need
TLS, authentication, DNS, or protocol-specific settings.

## SNMP Exporter variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.snmp_exporter` | `false` | Enables deployment on a host |
| `exporters_snmp_exporter_image` | `quay.io/prometheus/snmp-exporter:v0.30.1` | Pinned image reference; a digest is also accepted |
| `exporters_snmp_exporter_config_src` | empty (required when enabled) | Controller-side path to a generated `snmp.yml` |
| `exporters_snmp_exporter_bind_ip` | `127.0.0.1` | Host IP SNMP Exporter binds to; override per host with a private IP |
| `exporters_snmp_exporter_module_concurrency` | `1` | Modules fetched concurrently within one scrape |
| `exporters_snmp_exporter_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_snmp_exporter_extra_args` | `[]` | Additional SNMP Exporter CLI arguments |

Generate `snmp.yml` with the generator release matching
`exporters_snmp_exporter_image`. The role intentionally does not provide a
default community string. Prefer SNMPv3 for production networks; SNMPv1 and
SNMPv2c community strings are sent without encryption.

The HTTP `/snmp` endpoint can make requests to caller-selected network targets.
Bind `exporters_snmp_exporter_bind_ip` to a private interface and
allow access only from Prometheus or another trusted scraper. If Prometheus runs
on the same host, `127.0.0.1:9116` is the safest bind address.

## PostgreSQL Exporter variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.postgres_exporter` | `false` | Enables deployment on a host |
| `exporters_postgres_exporter_image` | `quay.io/prometheuscommunity/postgres-exporter:v0.20.1` | Pinned image reference; a digest is also accepted |
| `exporters_postgres_exporter_bind_ip` | `127.0.0.1` | Host IP PostgreSQL Exporter binds to; override per host with a private IP |
| `exporters_postgres_exporter_data_source_uri` | empty (required when enabled) | Credential-free PostgreSQL target in `host:port/database?options` form |
| `exporters_postgres_exporter_data_source_user` | `postgres_exporter` | Dedicated PostgreSQL monitoring user |
| `exporters_postgres_exporter_data_source_password` | empty (required when enabled) | Monitoring-user password; store with Ansible Vault |
| `exporters_postgres_exporter_secret_group` | container user's group | Group that can read mounted PostgreSQL Exporter config and password files |
| `exporters_postgres_exporter_collection_timeout` | `10s` | Maximum duration of one database collection operation |
| `exporters_postgres_exporter_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_postgres_exporter_extra_args` | `[]` | Additional PostgreSQL Exporter CLI arguments |

Create a dedicated login instead of using the PostgreSQL superuser. PostgreSQL
10 and newer can grant the built-in monitoring role:

```sql
CREATE USER postgres_exporter WITH PASSWORD 'replace-me';
GRANT CONNECT ON DATABASE postgres TO postgres_exporter;
GRANT pg_monitor TO postgres_exporter;
```

Restrict `exporters_postgres_exporter_bind_ip` to the Prometheus network or with
the host firewall. When changing it to a specific host address,
also set `exporters_postgres_exporter_healthcheck_url` to an HTTP URL reachable
on that address. For a remote database, enable and verify PostgreSQL TLS through
the connection options in `exporters_postgres_exporter_data_source_uri`.

## Heplify variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.heplify` | `false` | Enables native Heplify deployment on a host |
| `exporters_heplify_version` | `2.0.27` | Pinned upstream release version |
| `exporters_heplify_binary_src` | empty | Optional controller-side binary; avoids downloading from GitHub |
| `exporters_heplify_binary_url` | release URL for host architecture | Remote standalone binary URL |
| `exporters_heplify_binary_checksum` | pinned SHA-256 for host architecture | Integrity check for the downloaded binary |
| `exporters_heplify_capture_device` | `any` | Interface used for packet capture |
| `exporters_heplify_capture_modes` | `SIP`, `RTCP` | Protocols captured and forwarded over HEP |
| `exporters_heplify_hep_host` | `127.0.0.1` | HOMER/HEP collector host |
| `exporters_heplify_hep_port` | `9060` | HOMER/HEP collector port |
| `exporters_heplify_hep_transport` | `udp` | HEP transport (`udp`, `tcp`, or `tls`) |
| `exporters_heplify_hep_password` | empty | HEP authentication password; store with Ansible Vault |
| `exporters_heplify_prometheus_bind_ip` | `127.0.0.1` | Address for the built-in `/metrics` endpoint |
| `exporters_heplify_prometheus_port` | `9096` | Port for the built-in `/metrics` endpoint |
| `exporters_heplify_config` | generated baseline mapping | Complete JSON configuration mapping for advanced setups |

When changing `exporters_heplify_version` or `exporters_heplify_binary_url`,
also set the matching `exporters_heplify_binary_checksum`. The native service
runs as root with only `CAP_NET_ADMIN` and `CAP_NET_RAW` retained because live
packet capture requires those capabilities. Restrict the Prometheus listen
address with the host firewall or bind it to a trusted interface.

## Promtail variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.promtail` | `false` | Enables Promtail deployment on a host |
| `exporters_promtail_image` | `grafana/promtail:3.5.8` | Pinned Promtail image reference |
| `exporters_promtail_user` | empty | Container UID/GID override; defaults to the numeric UID/GID of `exporters_owner` |
| `exporters_promtail_client_url` | empty (required when enabled) | Loki `/loki/api/v1/push` endpoint |
| `exporters_promtail_bind_ip` | `127.0.0.1` | Host IP for Promtail metrics and readiness endpoint |
| `exporters_promtail_config` | generated baseline mapping | Complete Promtail configuration for extra scrape jobs or pipeline stages |
| `exporters_promtail_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_promtail_extra_args` | `[]` | Additional Promtail CLI arguments |

The default configuration tails `/var/log/*.log` and Docker JSON logs, adding
`job` and `host` labels. It stores read positions under the exporter directory,
so a container replacement does not resend the whole log history. Promtail has
read-only access to host logs and all Linux capabilities dropped. Keep the Loki
endpoint on a private network or use HTTPS and authentication in an overridden
`exporters_promtail_config` stored with Ansible Vault.

## MKTXP variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.mktxp` | `false` | Enables MKTXP deployment on a host |
| `exporters_mktxp_image` | `ghcr.io/akpw/mktxp:1.2.20` | Pinned MKTXP image reference |
| `exporters_mktxp_bind_ip` | `127.0.0.1` | Host IP MKTXP binds to; override per host with a private IP |
| `exporters_mktxp_routers` | `[]` (required when enabled) | Router name, API endpoint, and credentials |
| `exporters_mktxp_default_router_config` | baseline collector settings | Defaults applied to each router |
| `exporters_mktxp_system_config` | baseline server settings | MKTXP exporter process configuration |
| `exporters_mktxp_pull_policy` | `missing` | Compose image pull behavior |

Each router entry requires `name`, `hostname`, `username`, and `password`;
`options` can override any MKTXP router-level setting. Store credentials in
Ansible Vault. The container runs as its upstream unprivileged UID 1000 and has
read-only access to its two configuration files with all Linux capabilities
dropped. Create a dedicated MikroTik API user with only the `api` and `read`
permissions, and limit API access to the exporter host.

## Example

```yaml
exporters_enabled:
  node_exporter: true
  cadvisor: true
  blackbox_exporter: true
  snmp_exporter: true
  postgres_exporter: true
  heplify: true
  promtail: true
  mktxp: true

exporters_node_exporter_bind_ip: "192.0.2.10"
exporters_node_exporter_extra_args:
  - --collector.systemd
exporters_cadvisor_bind_ip: "192.0.2.10"
exporters_cadvisor_extra_args:
  - --docker_only=true
exporters_blackbox_exporter_bind_ip: "192.0.2.10"
exporters_snmp_exporter_bind_ip: "192.0.2.10"
exporters_snmp_exporter_config_src: "{{ playbook_dir }}/files/snmp/snmp.yml"
exporters_postgres_exporter_bind_ip: "192.0.2.10"
exporters_postgres_exporter_healthcheck_url: "http://192.0.2.10:9187/"
exporters_postgres_exporter_data_source_uri: "127.0.0.1:5432/postgres?sslmode=disable"
exporters_postgres_exporter_data_source_password: "{{ vault_postgres_exporter_password }}"
exporters_heplify_capture_device: eth0
exporters_heplify_hep_host: "192.0.2.20"
exporters_heplify_hep_password: "{{ vault_hep_password }}"
exporters_heplify_prometheus_bind_ip: "192.0.2.10"
exporters_promtail_bind_ip: "192.0.2.10"
exporters_promtail_client_url: "https://loki.example.net/loki/api/v1/push"
exporters_mktxp_bind_ip: "192.0.2.10"
exporters_mktxp_routers:
  - name: edge-router
    hostname: "192.0.2.1"
    username: mktxp
    password: "{{ vault_mktxp_edge_router_password }}"
    options:
      use_ssl: true
      ssl_certificate_verify: true
```

Run only this exporter with:

```bash
ansible-playbook playbook.yml --tags node-exporter
```

Use `--tags cadvisor` to run only cAdvisor.

Use `--tags blackbox-exporter` to run only Blackbox Exporter.

Use `--tags snmp-exporter` to run only SNMP Exporter.

Use `--tags postgres-exporter` to run only PostgreSQL Exporter.

Use `--tags heplify` to run only Heplify.

Use `--tags promtail` to run only Promtail.

Use `--tags mktxp` to run only MKTXP.
