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
import os
from time import sleep
import urllib

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, WaitingStatus

logger = logging.getLogger(__name__)


class DgraphOperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_install(self, _):
        # Download the data
        self._fetch_data()

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
            # Set an WaitingStatus until the DB is ready
            self.unit.status = WaitingStatus("waiting for db initialization")
            # Wait until Dgraph is ready
            state_url = "http://localhost:6080/state"
            status_code = None
            while status_code != 200:
                try:                
                    logger.info("Checking %s", state_url)
                    status_code = urllib.request.urlopen(state_url, timeout=10).getcode()
                    if status_code != 200:
                        logger.info("Dgraph not ready")
                        sleep(5)
                except Exception as e:
                    logger.info(str(e))
                    sleep(5)
            # Import the demo data
            container = self.unit.get_container("dgraph")
            while True:
                try:
                    container.exec(["dgraph", "live", "--files", "/data/import/demo.rdf", "--schema", "/data/import/demo.schema"]).wait_output()
                    break
                except Exception as e:
                    logger.info(str(e))
                    sleep(5)
            # All is well, set an ActiveStatus
            self.unit.status = ActiveStatus()
            logger.info("Dgraph is ready")
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
                    "command": "bash -c \"set -ex; cd /data; dgraph zero --my=$(hostname -f):5080\"",
                    "startup": "enabled",
                },
                "alpha": {
                    "override": "replace",
                    "summary": "alpha",
                    "command": "bash -c \"set -ex; cd /data; dgraph alpha --my=$(hostname -f):7080 --zero $(hostname -f):5080" + whitelist + "\"",
                    "startup": "enabled",
                }
            },
        }

    def _fetch_data(self):
        """Fetch demo data from Pastebin and move into import folder"""
        # Set the schema and data URLs
        schema_src = "https://pastebin.com/raw/t9t4C6Fd"
        data_src = "https://pastebin.com/raw/EazFpDcj"
        # Set maintenance status and do logging
        self.unit.status = MaintenanceStatus("Fetching data")
        logger.info("Downloading data from %s and %s", schema_src, data_src)
        # Create the import folder
        try:
            os.mkdir("/data/import")
        except:
            pass
        # Download the schema
        urllib.request.urlretrieve(schema_src, "/data/import/demo.schema")
        # Download the data
        urllib.request.urlretrieve(data_src, "/data/import/demo.rdf")
        # Set the unit status back to Active
        self.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(DgraphOperatorCharm)
