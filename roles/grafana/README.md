# Grafana

Deploys `dhi.io/grafana` with Docker Compose using this host layout:

```text
/opt/services/observability/grafana/
├── .env                         # mode 0600; includes admin credentials
├── compose.yml
├── grafana-data/                 # persistent database, plugins and generated files
└── provisioning/
    ├── access-control/
    ├── dashboards/
    │   └── json/                # optional dashboard JSON files
    └── datasources/
```

Grafana binds to `127.0.0.1:3000` by default and joins the existing external
`prinet` and `pubnet` networks. The role does not install Docker or create these
networks. Docker Compose v2.18+ and the repository's `community.docker`
collection are prerequisites. Authenticate to `dhi.io` as the Docker client
user used by Ansible (`root` with the supplied become-enabled playbook).

## Usage

Add the target host to `grafana_servers` in your inventory, then set:

```yaml
grafana_tag: "YOUR_EXACT_DHI_RUNTIME_TAG"
grafana_username: admin
grafana_password: "{{ vault_grafana_password }}"
```

There is no default image tag or password. Store `vault_grafana_password` with
Ansible Vault. See [example/inventory.yml](example/inventory.yml) and
[example/group_vars/grafana_servers.yml](example/group_vars/grafana_servers.yml)
for a complete configuration with optional Prometheus and dashboard provisioning.

From the repository root:

```bash
ansible-galaxy collection install -r collections/requirements.yml
ansible-playbook -i inventories/production/hosts.yml playbook.yml \
  --limit grafana --tags grafana --ask-vault-pass
```

The root playbook selects `grafana_servers`. The limit must match your inventory
host name. The standalone `example/playbook.yml` can also be run from the
repository root with the appropriate inventory.

## Settings

See [defaults/main.yml](defaults/main.yml) for all variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `grafana_tag` | empty, required | Exact `dhi.io/grafana` runtime tag |
| `grafana_dir` | `/opt/services/observability/grafana` | Compose project and bind mounts |
| `grafana_owner`, `grafana_group` | `ansible_user` | Project and `.env` ownership |
| `grafana_port` | `3000` | Host port, always bound to loopback |
| `grafana_container_name` | `grafana` | Container name |
| `grafana_restart_policy` | `unless-stopped` | Docker restart policy |
| `grafana_pull_policy` | `missing` | Compose image pull policy |
| `grafana_network1`, `grafana_network2` | `prinet`, `pubnet` | Both external networks, in either order |
| `grafana_runtime_uid`, `grafana_runtime_gid` | `65532`, `65532` | Bind-mount ownership for the DHI runtime user |
| `grafana_manage_data_ownership` | `false` | Opt-in recursive ownership repair for existing data |
| `grafana_provisioning` | `{}` | Relative YAML filenames mapped to native provisioning documents |
| `grafana_dashboard_files` | `[]` | Controller-side JSON files to copy |
| `grafana_healthcheck_enabled` | `true` | Wait for `/api/health` and database status `ok` from the target host |

The [DHI Grafana guide](https://hub.docker.com/hardened-images/catalog/dhi/grafana/guides)
documents UID/GID `65532`, shell-free runtime images, and the default data and
provisioning paths used here. The Compose file retains the supplied `GF_PATHS_*`
variables, but DHI already sets these paths through its entrypoint. Do not rely
on those variables to change paths with DHI. `GF_INSTALL_PLUGINS` is not enabled.

The role changes the data directory's owner but leaves existing contents alone
by default. If migrating files owned by another image's UID, back up the data
and enable `grafana_manage_data_ownership` for the migration. Runtime UID/GID
settings control host permissions; they do not override the image's runtime user.
Grafana creates its database and runtime subdirectories itself.

Admin credentials initialize a **new** database. Changing `grafana_password`
does not reset an administrator password already stored in `grafana.db`.

## Provisioning

`grafana_provisioning` accepts native `apiVersion: 1` YAML documents under
`datasources/`, `dashboards/`, and `access-control/`. Only configured filenames
are written; removing an entry from inventory leaves the deployed file in place.
The same retention rule applies to dashboard JSON files. Remove obsolete files
explicitly when needed. The role does not prune existing data sources or dashboards.

Provisioning YAML uses mode `0640`, readable by the container group. Credential
rendering and provisioning output are hidden from Ansible logs and diffs. `.env`
escaping preserves literal dollar signs in administrator credentials.

Grafana itself expands `$VARIABLE` expressions inside provisioning documents;
escape literal dollar signs as `$$` in inline provisioning secrets. Refer to
[Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
for the native schema and substitution rules. Access-control provisioning depends
on the Grafana edition and features available in your selected image.

Dashboard files are copied to `provisioning/dashboards/json/` and checked for
valid JSON. Supply a dashboard provider pointing at
`/etc/grafana/provisioning/dashboards/json`, as in the example. A polling interval
of 30 seconds detects bind-mounted file changes. Prometheus URLs must be reachable
from the Grafana container; `localhost` refers to the Grafana container itself.

Provisioning YAML changes recreate Grafana so startup provisioning runs again.
Compose detects environment/image changes, while dashboard JSON updates are
picked up by the file provider. No existing files are deleted by this role.

## Tags and validation

- `grafana`: complete deployment.
- `grafana-install`: prepare directories, Compose and `.env`, then deploy.
- `grafana-provisioning`: update provisioning on a prepared host, then deploy.
- `grafana-deploy`: validate and apply an existing Compose project, then check health.

The role validates variables, inspects external networks during installation,
runs `docker compose config --quiet`, starts the service, then polls health from
the target host. Compose validation does not validate Grafana's provisioning
schema. Check mode skips deployment and health polling; it cannot establish
runtime health or fully validate files that have not yet been created.
