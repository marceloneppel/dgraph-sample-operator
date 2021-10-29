# Copyright 2021 Marcelo Henrique Neppel
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import Mock, patch, MagicMock
import urllib

from charm import DgraphOperatorCharm
from ops.model import ActiveStatus
from ops.testing import Harness


class TestCharm(unittest.TestCase):

    def setUp(self):
        self.harness = Harness(DgraphOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_dgraph_layer(self):
        # Test with empty config.
        self.assertEqual(self.harness.charm.config["whitelist"], "")
        expected_1 = {
            "summary": "dgraph layer",
            "description": "pebble config layer for dgraph",
            "services": {
                "zero": {
                    "override": "replace",
                    "summary": "zero",
                    "command": """bash -c \"set -ex; cd /data;
                               dgraph zero --my=$(hostname -f):5080\"""",
                    "startup": "enabled",
                },
                "alpha": {
                    "override": "replace",
                    "summary": "alpha",
                    "command": """bash -c \"set -ex; cd /data;
                               dgraph alpha --my=$(hostname -f):7080
                               --zero $(hostname -f):5080\"""",
                    "startup": "enabled",
                }
            },
        }
        self.assertEqual(self.harness.charm._dgraph_layer(), expected_1)
        # And now test with a different value in the whitelist config option.
        # Disable hook firing first.
        self.harness.disable_hooks()
        self.harness.update_config({"whitelist": "192.168.1.16"})
        expected_2 = {
            "summary": "dgraph layer",
            "description": "pebble config layer for dgraph",
            "services": {
                "zero": {
                    "override": "replace",
                    "summary": "zero",
                    "command": """bash -c \"set -ex; cd /data;
                               dgraph zero --my=$(hostname -f):5080\"""",
                    "startup": "enabled",
                },
                "alpha": {
                    "override": "replace",
                    "summary": "alpha",
                    "command": """bash -c \"set -ex; cd /data;
                               dgraph alpha --my=$(hostname -f):7080
                               --zero $(hostname -f):5080 --security whitelist=192.168.1.16\"""",
                    "startup": "enabled",
                }
            },
        }
        self.assertEqual(self.harness.charm._dgraph_layer(), expected_2)

    @patch('urllib.request.urlopen')
    def test_on_config_changed(self, mock_urlopen):
        cm = MagicMock()
        cm.getcode.return_value = 200
        mock_urlopen.return_value = cm

        plan = self.harness.get_container_pebble_plan("dgraph")
        self.assertEqual(plan.to_dict(), {})
        # Trigger a config-changed hook. Since there was no plan initially, the
        # "dgraph" service in the container won't be running so we'll be
        # testing the `is_running() == False` codepath.
        with patch('ops.model.Container.exec'):
            self.harness.update_config({"whitelist": "test"})
        plan = self.harness.get_container_pebble_plan("dgraph")
        # Get the expected layer from the dgraph_layer method (tested above)
        expected = self.harness.charm._dgraph_layer()
        expected.pop("summary", "")
        expected.pop("description", "")
        # Check the plan is as expected
        self.assertEqual(plan.to_dict(), expected)
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
        container = self.harness.model.unit.get_container("dgraph")
        self.assertEqual(container.get_service("alpha").is_running(), True)
        self.assertEqual(container.get_service("zero").is_running(), True)

        # Now test again with different config, knowing that the "dgraph"
        # service is running (because we've just tested it above), so we'll
        # be testing the `is_running() == True` codepath.
        with patch('ops.model.Container.exec'):
            self.harness.update_config({"whitelist": "192.168.1.16"})
        plan = self.harness.get_container_pebble_plan("dgraph")
        # Adjust the expected plan
        expected = self.harness.charm._dgraph_layer()
        expected.pop("summary", "")
        expected.pop("description", "")
        self.assertEqual(plan.to_dict()["services"]["alpha"], expected["services"]["alpha"])
        self.assertEqual(plan.to_dict()["services"]["zero"], expected["services"]["zero"])
        self.assertEqual(container.get_service("alpha").is_running(), True)
        self.assertEqual(container.get_service("zero").is_running(), True)
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
        self.assertEqual(plan.to_dict()["services"]["alpha"], expected["services"]["alpha"])

        # And finally test again with the same config to ensure we exercise
        # the case where the plan we've created matches the active one. We're
        # going to mock the container.stop and container.start calls to confirm
        # they were not called.
        with patch('ops.model.Container.exec'):
            self.harness.charm.on.config_changed.emit()
        with patch('ops.model.Container.start') as _start:
            _start.assert_not_called()
        with patch('ops.model.Container.stop') as _stop:
            _stop.assert_not_called()

    @patch("charm.DgraphOperatorCharm._fetch_data")
    def test_on_install(self, _fetch_data):
        self.harness.charm._on_install("mock_event")
        _fetch_data.assert_called_once

    @patch('urllib.request.urlopen')
    def test_export_action(self, mock_urlopen):
        magic_mock = MagicMock()
        magic_mock.getcode.return_value = 200
        magic_mock.read.return_value = urllib.parse.urlencode({"data": {"export": {"response":
                                                              {"message": "Export completed.",
                                                               "code": "Success"}}}}).encode(
                                                                   "utf-8")
        mock_urlopen.return_value = magic_mock

        mock_event = Mock()
        self.harness.charm._export_action(mock_event)
        mock_event.called_once_with({"result": "database exported"})
