# Wazuh agent

Installs a Wazuh agent and enrolls it with the manager deployed by the
[wazuh](../../wazuh/) role (or any Wazuh 4.x manager). Pick one of two modes
per host with `wazuh_agent_mode`:

| Mode | How it runs | Use it when |
| --- | --- | --- |
| `systemd` (default) | Official `wazuh-agent` package from the Wazuh apt repository, `wazuh-agent.service` | Normal Debian/Ubuntu hosts. Full host visibility. |
| `docker` | Official `wazuh/wazuh-agent` image with Docker Compose; the host `/` is mounted read-only at `/host` | Hosts where you don't want to install packages, only Docker. |

Both modes render `ossec.conf` from one template
([templates/ossec.conf.j2](templates/ossec.conf.j2)), so the same variables
work in either mode. Host paths (FIM directories, log files) are written as
normal host paths; in docker mode the role prefixes them with `/host`.

## Docker mode limits

The container sees the host's files and network, but not its processes or
packages. These modules would report the container instead of the host, so
they are **off by default in docker mode**:

- syscollector (inventory, and so vulnerability detection)
- SCA, rootcheck
- active response
- command monitoring (`df`, `netstat`, `last`) and journald collection

What works in docker mode: log collection from host files, file integrity
monitoring of host paths, and centralised configuration from the manager.
Use systemd mode when you need full coverage.

```text
/opt/services/security/wazuh-agent/
├── .env              # mode 0600; image, restart policy, enrollment password
├── compose.yml
└── config/ossec.conf # copied into the container on every start
```

The named volume `wazuh-agent_wazuh_agent_etc` holds `client.keys`, so a
recreated container keeps its agent ID instead of enrolling again.

## Requirements

- `systemd` mode: Debian or Ubuntu with systemd and access to
  `packages.wazuh.com`.
- `docker` mode: Linux with Docker Engine and Compose v2, access to Docker Hub,
  and the `community.docker` collection on the controller.
- Network access from the agent to the manager on 1514/tcp (events) and
  1515/tcp (enrollment).
- Facts gathered before the role runs.

## Usage

```yaml
wazuh_agent_manager_address: 192.0.2.40
wazuh_agent_groups: [default, linux]
# wazuh_agent_mode: docker
```

See [example/](example/) for an inventory, playbook and group vars. The role
lives under `roles/agents/`, so reference it as `agents/wazuh-agent`:

```bash
ansible-playbook -i inventories/production/hosts.yml roles/agents/wazuh-agent/example/playbook.yml
```

## Settings

See [defaults/main.yml](defaults/main.yml).

| Variable | Default | Purpose |
| --- | --- | --- |
| `wazuh_agent_mode` | `systemd` | `systemd` or `docker` |
| `wazuh_agent_version` | `4.14.8` | Package version / image tag. Not newer than the manager. |
| `wazuh_agent_manager_address` | required | Manager address the agent connects to |
| `wazuh_agent_manager_port`, `wazuh_agent_enrollment_port` | `1514`, `1515` | Manager ports |
| `wazuh_agent_enrollment_address` | manager address | Enrollment (authd) address |
| `wazuh_agent_name` | `inventory_hostname` | Agent name; unique per manager |
| `wazuh_agent_groups` | `[default]` | Agent groups assigned at enrollment |
| `wazuh_agent_enrollment_password` | `""` | Only when the manager uses `<use_password>yes</use_password>` |
| `wazuh_agent_wait_for_connection`, `wazuh_agent_connection_timeout` | `true`, `180` | Fail unless the agent reports `connected` |
| `wazuh_agent_syscheck_directories`, `wazuh_agent_syscheck_ignore` | system dirs | FIM paths. An item may be `{path: /srv, attributes: {realtime: "yes"}}`. |
| `wazuh_agent_localfiles` | auth, syslog, kern, dpkg logs | Log files to collect |
| `wazuh_agent_*_enabled` | on in systemd, off in docker | syscollector, SCA, rootcheck, active response, command monitoring, journald, syscheck |
| `wazuh_agent_extra_config` | `""` | Raw XML added in an extra `<ossec_config>` block |
| `wazuh_agent_config_template` | bundled | Your own `ossec.conf` template |
| `wazuh_agent_hold_package` | `true` | Hold the apt package so upgrades are deliberate (systemd) |
| `wazuh_agent_dir`, `wazuh_agent_image`, `wazuh_agent_host_root` | `/opt/services/security/wazuh-agent`, official image, `/host` | Docker mode |
| `wazuh_agent_restart_policy`, `wazuh_agent_pull_policy` | `unless-stopped`, `missing` | Docker mode |

## What the role does

1. Validates settings and refuses to continue if an agent from the other mode is
   already on the host (two agents with one name break enrollment).
2. **systemd:** adds the Wazuh apt repository and key, installs and holds
   `wazuh-agent=<version>-1`, writes `ossec.conf` (and `authd.pass`), then enables
   and starts `wazuh-agent`. It restarts the agent when the config or package changes.
3. **docker:** writes `compose.yml`, `.env` and `config/ossec.conf`, then runs
   `docker compose up`. It recreates the container when the config changes. The
   health check passes only once the agent is connected.
4. Waits until `/var/ossec/var/run/wazuh-agentd.state` reports `connected`.

## Operations

```bash
# systemd
systemctl status wazuh-agent
tail -f /var/ossec/logs/ossec.log

# docker
cd /opt/services/security/wazuh-agent
docker compose ps
docker compose logs -f
```

- **Upgrade:** upgrade the manager first, then raise `wazuh_agent_version` and
  re-run the role. In docker mode, `/var/ossec/etc` is a volume, so files the
  new image ships there are not refreshed. If an upgrade needs them, back up
  `client.keys`, remove the volume, restore the file, then start the agent.
- **Switch modes:** remove the old agent first.
  - systemd → docker: `apt-get purge wazuh-agent && rm -rf /var/ossec`
  - docker → systemd: `docker compose down -v` and remove `wazuh_agent_dir`

  Then delete the agent on the manager
  (`/var/ossec/bin/manage_agents -r <id>`) so the name can enroll again.
- **Rename or move an agent:** delete it on the manager first. The manager
  rejects an enrollment that reuses the name of an agent that is still connected.
