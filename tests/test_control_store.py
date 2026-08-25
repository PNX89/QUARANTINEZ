"""The endpoint this repository assumes, against the compose file that has to serve it.

Two files describing one port is the shape that goes quietly wrong: the compose file is edited
to dodge a collision, the constant keeps the old number, and every connection afterwards fails
somewhere far away from the edit.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest
import yaml

from quarantinez import control_store

REPO = pathlib.Path(__file__).resolve().parent.parent
COMPOSE = REPO / "compose.yaml"


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    parsed: dict[str, Any] = yaml.safe_load(COMPOSE.read_text("utf-8"))
    return parsed


def published(compose: dict[str, Any], service: str) -> tuple[str, int, int]:
    ports = compose["services"][service]["ports"]
    assert len(ports) == 1, f"{service} publishes {len(ports)} ports, and this reads one"
    interface, host, container = str(ports[0]).split(":")
    return interface, int(host), int(container)


def test_the_compose_file_publishes_the_port_this_module_assumes(
    compose: dict[str, Any],
) -> None:
    _, host, container = published(compose, "postgres")
    assert host == control_store.HOST_PORT
    assert container == control_store.CONTAINER_PORT
    assert f":{host}/" in control_store.DEFAULT_URL


def test_the_published_port_is_not_the_one_a_sibling_repository_took(
    compose: dict[str, Any],
) -> None:
    """The rule is do not collide, which is not the same as add one.

    Written as its own test because the obvious edit, changing this back to container plus one,
    is exactly the change that would make two repositories in this toolset unable to run at the
    same time, and nothing else here would notice.
    """
    _, host, container = published(compose, "postgres")
    assert host > container + 1, "back to the port a sibling repository already publishes"


def test_the_service_is_bound_to_the_loopback_interface(compose: dict[str, Any]) -> None:
    """A published port with no interface is offered to every network the host is on."""
    interface, _, _ = published(compose, "postgres")
    assert interface == "127.0.0.1"


def test_no_named_volume_keeps_state_between_runs(compose: dict[str, Any]) -> None:
    """The crash proof creates its own state, and state that outlives it is state that drifted."""
    assert "volumes" not in compose
    assert "volumes" not in compose["services"]["postgres"]


def test_the_environment_overrides_the_endpoint() -> None:
    chosen = control_store.ControlStore.from_env(
        {control_store.URL_VAR: "postgresql://elsewhere/x"}
    )
    assert chosen.url == "postgresql://elsewhere/x"


def test_an_empty_environment_variable_falls_back_rather_than_connecting_to_nothing() -> None:
    """An unset variable and one set to the empty string are the same intention."""
    chosen = control_store.ControlStore.from_env({control_store.URL_VAR: ""})
    assert chosen.url == control_store.DEFAULT_URL
