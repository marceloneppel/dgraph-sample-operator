#!/usr/bin/env python3
# Copyright 2021 Marcelo Henrique Neppel
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class DgraphOperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.dgraph_pebble_ready, self._on_dgraph_pebble_ready)

    def _on_dgraph_pebble_ready(self, event):
        """Define and start a workload using the Pebble API."""
        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload
        # Define an initial Pebble layer configuration
        pebble_layer = {
            "summary": "dgraph layer",
            "description": "pebble config layer for dgraph",
            "services": {
                "zero": {
                    "override": "replace",
                    "summary": "zero",
                    "command": "bash -c \"set -ex; dgraph zero --my=$(hostname -f):5080\"",
                    "startup": "enabled",
                },
                "alpha": {
                    "override": "replace",
                    "summary": "alpha",
                    "command": "bash -c \"set -ex; dgraph alpha --my=$(hostname -f):7080 --zero $(hostname -f):5080 --security whitelist=0.0.0.0/0\"",
                    "startup": "enabled",
                }
            },
        }
        # Add intial Pebble config layer using the Pebble API
        container.add_layer("dgraph", pebble_layer, combine=True)
        # Autostart any services that were defined with startup: enabled
        container.autostart()
        # Learn more about statuses in the SDK docs:
        # https://juju.is/docs/sdk/constructs#heading--statuses
        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(DgraphOperatorCharm)
