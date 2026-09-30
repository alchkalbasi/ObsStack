# ObsStack

An Ansible-powered observability and security stack for deploying, configuring,
and managing metrics, logs, alerts, dashboards, and host security monitoring
across your infrastructure. Every service runs in Docker Compose, except the
Heplify exporter and the systemd-mode Wazuh agent.

## Roles

| Role | Inventory group | Tags | What it deploys |
| --- | --- | --- | --- |
| [exporters](roles/exporters/) | `exporters` | `observability`, `exporters` | Node Exporter, cAdvisor, Blackbox, SNMP, PostgreSQL Exporter, Heplify, Promtail, MKTXP |
| [prometheus](roles/prometheus/) | `prometheus_servers` | `observability`, `prometheus` | Prometheus, with scrape targets built from the inventory, sharding and HA |
| [grafana](roles/grafana/) | `grafana_servers` | `observability`, `grafana` | Grafana with provisioned data sources and dashboards |
| [alertmanager](roles/alertmanager/) | `alertmanager_servers` | `observability`, `alertmanager` | Alertmanager with templated routes and receivers |
| [wazuh](roles/wazuh/) | `wazuh_servers` | `security`, `wazuh` | Single-node Wazuh manager, indexer and dashboard |
| [agents/wazuh-agent](roles/agents/wazuh-agent/) | `wazuh_agents` | `security`, `wazuh-agent` | Wazuh agent, as a systemd package or a Docker container |

Each role has a README and an `example/` directory with an inventory, group vars
and a standalone playbook.

## Requirements

- Ansible Core 2.16 or newer on the controller
- Target hosts running Linux, with Docker Engine and Docker Compose v2 installed
  for the containerized roles
- The pinned collections:

  ```bash
  ansible-galaxy collection install -r collections/requirements.yml
  ```

## Layout

```text
.
├── ansible.cfg              # project defaults; inventory = inventories/production/hosts.yml
├── playbook.yml             # runs every role against its inventory group
├── collections/requirements.yml
├── inventories/             # git-ignored; one directory per environment
│   └── production/
│       ├── hosts.yml
│       └── group_vars/
└── roles/
```

Inventories and anything under `/files/` are git-ignored because they hold
host addresses and secrets. Build your inventory from the role examples and keep
passwords in Ansible Vault.

## Usage

Put each host in the groups for the roles it should run (see the table above),
then run the root playbook:

```bash
# Everything
ansible-playbook playbook.yml --ask-vault-pass

# One component
ansible-playbook playbook.yml --tags grafana --ask-vault-pass

# All security components on one environment
ansible-playbook -i inventories/staging/hosts.yml playbook.yml --tags security --ask-vault-pass

# One host
ansible-playbook playbook.yml --limit grafana --tags grafana --ask-vault-pass
```

The plays run in dependency order: exporters, Prometheus, Grafana,
Alertmanager, then the Wazuh manager before its agents so that agents can
enroll. Prometheus and Grafana hosts are updated one at a time (`serial: 1`).

## Networking

Grafana joins the external Docker networks `prinet` (internal traffic between
services) and `pubnet` (services exposed through a reverse proxy), and creates
them if they don't exist. Other roles bind their ports to the host. See each
role's README for its listen addresses.

## License

See [LICENSE](LICENSE).
