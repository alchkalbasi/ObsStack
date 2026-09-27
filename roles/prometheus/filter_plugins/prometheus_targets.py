"""Inventory-to-file_sd filters for the Prometheus role."""

from collections.abc import Mapping, Sequence

from ansible.errors import AnsibleFilterError


def _label_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _target(address, port):
    address = str(address)
    if ":" in address and not address.startswith("["):
        address = f"[{address}]"
    return f"{address}:{port}"


def _is_enabled(value):
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def prometheus_file_sd(job, groups, hostvars):
    """Return stable file_sd entries derived from one scrape job and inventory."""
    if not isinstance(job, Mapping):
        raise AnsibleFilterError("Prometheus scrape job must be a mapping")

    inventory_groups = job.get("inventory_groups", [])
    if not isinstance(inventory_groups, Sequence) or isinstance(inventory_groups, str):
        raise AnsibleFilterError("inventory_groups must be a list")

    try:
        port = int(job["port"])
    except (KeyError, TypeError, ValueError) as error:
        raise AnsibleFilterError("scrape job port must be an integer") from error
    if not 1 <= port <= 65535:
        raise AnsibleFilterError("scrape job port must be between 1 and 65535")

    static_labels = job.get("labels", {})
    per_host_labels = job.get("per_host_labels", {})
    if not isinstance(static_labels, Mapping) or not isinstance(per_host_labels, Mapping):
        raise AnsibleFilterError("labels and per_host_labels must be mappings")

    hosts = {
        host
        for group_name in inventory_groups
        for host in groups.get(group_name, [])
    }
    entries = []
    for host in hosts:
        variables = hostvars.get(host, {})
        enabled_key = job.get("enabled_key")
        if enabled_key:
            enabled_map = variables.get("exporters_enabled", {})
            if not isinstance(enabled_map, Mapping):
                raise AnsibleFilterError(
                    f"exporters_enabled for {host} must be a mapping"
                )
            enabled = enabled_map.get(enabled_key, False)
            if not _is_enabled(enabled):
                continue

        address = variables.get("prom_address")
        if address in (None, ""):
            address = variables.get("ansible_host", host)

        labels = {str(key): _label_value(value) for key, value in static_labels.items()}
        for label_name, variable_name in per_host_labels.items():
            if variable_name in variables and variables[variable_name] not in (None, ""):
                labels[str(label_name)] = _label_value(variables[variable_name])
        labels["instance_host"] = str(host)

        entries.append({"targets": [_target(address, port)], "labels": labels})

    return sorted(entries, key=lambda entry: entry["targets"][0])


class FilterModule:
    """Expose role filters to Ansible."""

    def filters(self):
        return {"prometheus_file_sd": prometheus_file_sd}
