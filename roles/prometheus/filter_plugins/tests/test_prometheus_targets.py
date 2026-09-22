import importlib.util
from pathlib import Path

import pytest


PLUGIN_PATH = Path(__file__).parents[1] / "prometheus_targets.py"
SPEC = importlib.util.spec_from_file_location("prometheus_targets", PLUGIN_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_deduplicates_sorts_and_applies_address_precedence():
    job = {
        "port": 9100,
        "inventory_groups": ["linux", "database"],
        "labels": {"job_type": "system"},
        "per_host_labels": {"env": "prom_env", "missing": "not_set"},
    }
    groups = {
        "linux": ["web-2", "web-1"],
        "database": ["web-1", "db-1"],
    }
    hostvars = {
        "web-1": {"prom_address": "10.0.0.1", "ansible_host": "192.0.2.1", "prom_env": "prod"},
        "web-2": {"ansible_host": "10.0.0.2", "not_set": ""},
        "db-1": {},
    }

    result = MODULE.prometheus_file_sd(job, groups, hostvars)

    assert [entry["targets"][0] for entry in result] == [
        "10.0.0.1:9100",
        "10.0.0.2:9100",
        "db-1:9100",
    ]
    assert result[0]["labels"] == {
        "job_type": "system",
        "env": "prod",
        "instance_host": "web-1",
    }


def test_missing_group_is_empty_and_enabled_key_filters_hosts():
    job = {
        "port": 9187,
        "inventory_groups": ["missing", "exporters"],
        "enabled_key": "postgres_exporter",
    }
    groups = {"exporters": ["db-1", "db-2"]}
    hostvars = {
        "db-1": {"exporters_enabled": {"postgres_exporter": "true"}},
        "db-2": {"exporters_enabled": {"postgres_exporter": "false"}},
    }

    assert MODULE.prometheus_file_sd(job, groups, hostvars) == [
        {"targets": ["db-1:9187"], "labels": {"instance_host": "db-1"}}
    ]


def test_formats_ipv6_and_stringifies_label_values():
    job = {
        "port": 8080,
        "inventory_groups": ["exporters"],
        "labels": {"production": True, "priority": 1},
    }
    result = MODULE.prometheus_file_sd(
        job,
        {"exporters": ["container-1"]},
        {"container-1": {"prom_address": "2001:db8::10"}},
    )

    assert result == [
        {
            "targets": ["[2001:db8::10]:8080"],
            "labels": {
                "production": "true",
                "priority": "1",
                "instance_host": "container-1",
            },
        }
    ]


@pytest.mark.parametrize(
    "job",
    [
        [],
        {"port": 0, "inventory_groups": []},
        {"port": 9100, "inventory_groups": "all"},
        {"port": 9100, "inventory_groups": [], "labels": []},
    ],
)
def test_rejects_invalid_job_definitions(job):
    with pytest.raises(MODULE.AnsibleFilterError):
        MODULE.prometheus_file_sd(job, {}, {})
