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
from ops.model import ActiveStatus, WaitingStatus

logger = logging.getLogger(__name__)


class DgraphOperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_config_changed(self, event):
        """Handle the config-changed event"""
        # Get the dgraph container so we can configure/manipulate it
        container = self.unit.get_container("dgraph")
        # Create a new config layer
        layer = self._dgraph_layer()

        if container.can_connect():
            # Get the current config
            services = container.get_plan().to_dict().get("services", {})
            # Check if there are any changes to services
            if services != layer["services"]:
                # Changes were made, add the new layer
                container.add_layer("dgraph", layer, combine=True)
                logging.info("Added updated layer 'dgraph' to Pebble plan")
                # Restart it and report a new status to Juju
                container.restart("zero")
                container.restart("alpha")
                logging.info("Restarted dgraph service")
            # All is well, set an ActiveStatus
            self.unit.status = ActiveStatus()
        else:
            self.unit.status = WaitingStatus("waiting for Pebble in workload container")

    def _dgraph_layer(self):
        """Returns a Pebble configration layer for Dgraph"""
        whitelist = ""
        if self.config["whitelist"] != "":
            whitelist = " --security whitelist=" + self.config["whitelist"]
        
        return {
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
                    "command": "bash -c \"set -ex; dgraph alpha --my=$(hostname -f):7080 --zero $(hostname -f):5080" + whitelist + "\"",
                    "startup": "enabled",
                }
            },
        }


if __name__ == "__main__":
    main(DgraphOperatorCharm)
