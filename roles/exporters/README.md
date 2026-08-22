# Exporters role

Deploys Node Exporter, cAdvisor, Blackbox Exporter, and SNMP Exporter with
Docker Compose.

The role installs a static `compose.yml` and renders host-specific values into a
separate `.env` file.

## Requirements

- Linux host with Docker Engine and the Docker Compose v2 plugin
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

## Node Exporter variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.node_exporter` | `false` | Enables deployment on a host |
| `exporters_node_exporter_image` | `quay.io/prometheus/node-exporter:v1.12.1` | Pinned image reference; a digest is also accepted |
| `exporters_node_exporter_web_listen_address` | `0.0.0.0:9100` | Host address and port used by Node Exporter |
| `exporters_node_exporter_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_node_exporter_extra_args` | `[]` | Additional Node Exporter CLI arguments |
| `exporters_node_exporter_filesystem_mount_points_exclude` | Upstream-compatible regex | Filesystem mount points excluded from metrics |

Bind `exporters_node_exporter_web_listen_address` to a private interface or enforce access
with the host firewall. Node Exporter does not enable authentication by default.

## cAdvisor variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.cadvisor` | `false` | Enables deployment on a host |
| `exporters_cadvisor_image` | `ghcr.io/google/cadvisor:v0.60.5` | Pinned image reference; a digest is also accepted |
| `exporters_cadvisor_web_listen_address` | `0.0.0.0:8080` | Host address and port mapped to cAdvisor |
| `exporters_cadvisor_docker_data_dir` | `/var/lib/docker` | Docker data root mounted for container discovery |
| `exporters_cadvisor_kmsg_device` | `/dev/kmsg` | Host kernel message device passed to cAdvisor |
| `exporters_cadvisor_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_cadvisor_extra_args` | `[]` | Additional cAdvisor CLI arguments |

Restrict `exporters_cadvisor_web_listen_address` to a trusted interface or with
the host firewall. cAdvisor exposes container metadata and does not enable
authentication by default.

## Blackbox Exporter variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.blackbox_exporter` | `false` | Enables deployment on a host |
| `exporters_blackbox_exporter_image` | `quay.io/prometheus/blackbox-exporter:v0.28.0` | Pinned image reference; a digest is also accepted |
| `exporters_blackbox_exporter_web_listen_address` | `0.0.0.0:9115` | Host address and port mapped to Blackbox Exporter |
| `exporters_blackbox_exporter_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_blackbox_exporter_extra_args` | `[]` | Additional Blackbox Exporter CLI arguments |
| `exporters_blackbox_exporter_modules` | HTTP, TCP, ICMP, DNS, and TLS modules | Complete probe module mapping rendered under `modules` |

`blackbox_modules` is accepted as an inventory-compatible alias for
`exporters_blackbox_exporter_modules`.

Restrict `exporters_blackbox_exporter_web_listen_address` to Prometheus or another
trusted network. Customize `exporters_blackbox_exporter_modules` when probes need
TLS, authentication, DNS, or protocol-specific settings.

## SNMP Exporter variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `exporters_enabled.snmp_exporter` | `false` | Enables deployment on a host |
| `exporters_snmp_exporter_image` | `quay.io/prometheus/snmp-exporter:v0.30.1` | Pinned image reference; a digest is also accepted |
| `exporters_snmp_exporter_config_src` | empty (required when enabled) | Controller-side path to a generated `snmp.yml` |
| `exporters_snmp_exporter_web_listen_address` | `0.0.0.0:9116` | Host address and port mapped to SNMP Exporter |
| `exporters_snmp_exporter_module_concurrency` | `1` | Modules fetched concurrently within one scrape |
| `exporters_snmp_exporter_pull_policy` | `missing` | Compose image pull behavior |
| `exporters_snmp_exporter_extra_args` | `[]` | Additional SNMP Exporter CLI arguments |

Generate `snmp.yml` with the generator release matching
`exporters_snmp_exporter_image`. The role intentionally does not provide a
default community string. Prefer SNMPv3 for production networks; SNMPv1 and
SNMPv2c community strings are sent without encryption.

The HTTP `/snmp` endpoint can make requests to caller-selected network targets.
Bind `exporters_snmp_exporter_web_listen_address` to a private interface and
allow access only from Prometheus or another trusted scraper. If Prometheus runs
on the same host, `127.0.0.1:9116` is the safest bind address.

## Example

```yaml
exporters_enabled:
  node_exporter: true
  cadvisor: true
  blackbox_exporter: true
  snmp_exporter: true

exporters_node_exporter_web_listen_address: "192.0.2.10:9100"
exporters_node_exporter_extra_args:
  - --collector.systemd
exporters_cadvisor_web_listen_address: "192.0.2.10:8080"
exporters_cadvisor_extra_args:
  - --docker_only=true
exporters_blackbox_exporter_web_listen_address: "192.0.2.10:9115"
exporters_snmp_exporter_web_listen_address: "192.0.2.10:9116"
exporters_snmp_exporter_config_src: "{{ playbook_dir }}/files/snmp/snmp.yml"
```

Run only this exporter with:

```bash
ansible-playbook playbook.yml --tags node-exporter
```

Use `--tags cadvisor` to run only cAdvisor.

Use `--tags blackbox-exporter` to run only Blackbox Exporter.

Use `--tags snmp-exporter` to run only SNMP Exporter.
