#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# engine_page.py - Copyright (C) 2012 Red Hat, Inc.
# Written by Fabian Deutsch <fabiand@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.
from ovirt.node import plugins, valid, ui, utils, exceptions
from ovirt.node.config.defaults import NodeConfigFileSection
from ovirt.node.plugins import ChangesHelper

"""
Configure Engine
"""


class Plugin(plugins.NodePlugin):
    _widgets = None

    def name(self):
        return "oVirt Engine"

    def rank(self):
        return 100

    def model(self):
        model = {
            "vdsm.address": "",
            "vdsm.port": "7634",
            "vdsm.connect_and_validate": False,
            "vdsm.password": "",
            "vdsm.password_confirmation": "",
        }
        return model

    def validators(self):
        same_as_password = plugins.Validator.SameAsIn(self, "vdsm.password",
                                                      "Password")
        return {
                "vdsm.address": valid.FQDNOrIPAddress() | valid.Empty(),
                "vdsm.port": valid.Port(),
                "vdsm.password": valid.Text(),
                "vdsm.password_confirmation": same_as_password,
            }

    def ui_content(self):
        widgets = [
            ("header", ui.Header("oVirt Engine Configuration")),

            ("vdsm.address", ui.Entry("Management Server:")),
            ("vdsm.port", ui.Entry("Management Server Port:")),

            ("divider[1]", ui.Divider()),

            ("vdsm.connect_and_validate", ui.Checkbox(
                    "Connect to oVirt Engine and Validate Certificate")),

            ("divider[0]", ui.Divider()),
            ("vdsm.password._label", ui.Label(
                    "Optional password for adding Node through oVirt " +
                    "Engine UI")),

            ("vdsm.password", ui.PasswordEntry("Password:")),
            ("vdsm.password_confirmation",
             ui.PasswordEntry("Confirm Password:")),
        ]
        # Save it "locally" as a dict, for better accessability
        self._widgets = plugins.WidgetsHelper(dict(widgets))

        page = ui.Page(widgets)
        return page

    def on_change(self, changes):
        pass

    def on_merge(self, effective_changes):
        self.logger.info("Saving engine stuff")
        changes = plugins.ChangesHelper(self.pending_changes(False))
        m = dict(self.model())
        m.update(effective_changes)
        effective_model = plugins.ChangesHelper(m)
        self.logger.info("Effective model %s" % effective_model)
        self.logger.info("Effective changes %s" % effective_changes)
        self.logger.info("All changes %s" % changes)

        txs = utils.Transaction("Configuring oVirt Engine")

        vdsm_keys = ["vdsm.address", "vdsm.port"]
        if changes.any_key_in_change(vdsm_keys):
            values = effective_model.get_key_values(vdsm_keys)
            self.logger.debug("Setting VDSM server and port (%s)" % values)

            # Use the VDSM class below to build a transaction
            model = VDSM()
            model.update(*values)
            txs += model.transaction()

        if changes.any_key_in_change(["vdsm.password_confirmation"]):
            self.logger.debug("Setting engine password")
            txs += [SetEnginePassword()]

        if changes.any_key_in_change(["vdsm.connect_and_validate"]):
            self.logger.debug("Connecting to engine")
            txs += [ActivateVDSM()]

        progress_dialog = ui.TransactionProgressDialog(txs, self)
        progress_dialog.run()

        # Acts like a page reload
        return self.ui_content()


class VDSM(NodeConfigFileSection):
    """Class to handle VDSM configuration

    >>> from ovirt.node.config.defaults import ConfigFile, SimpleProvider
    >>> fn = "/tmp/cfg_dummy"
    >>> cfgfile = ConfigFile(fn, SimpleProvider)
    >>> n = VDSM(cfgfile)
    >>> n.update("engine.example.com", "1234")
    >>> sorted(n.retrieve().items())
    [('port', '1234'), ('server', 'engine.example.com')]
    """
    keys = ("OVIRT_MANAGEMENT_SERVER",
            "OVIRT_MANAGEMENT_PORT")

    @NodeConfigFileSection.map_and_update_defaults_decorator
    def update(self, server, port):
        (valid.Empty() | valid.FQDNOrIPAddress())(server)
        (valid.Empty() | valid.Port())(port)

    def transaction(self):
        cfg = dict(self.retrieve())
        server, port = (cfg["server"], cfg["port"])

        class ConfigureVDSM(utils.Transaction.Element):
            title = "Setting VDSM server and port"

            def commit(self):
                self.logger.info("Setting: %s:%s" % (server, port))

        tx = utils.Transaction("Configuring VDSM")
        tx.append(ConfigureVDSM())

        return tx


class ActivateVDSM(utils.Transaction.Element):
    title = "Activating VDSM"

    def __init__(self):
        super(ActivateVDSM, self).__init__()
        self.vdsm = VDSM()

    def prepare(self):
        """Ping the management server before we try to activate
        the connection to it
        """
        cfg = dict(self.vdsm.retrieve())
        server, port = (cfg["server"], cfg["port"])
        retval = utils.process.system("ping -c 1 '%s'" % server)
        self.logger.debug("Pinged server with %s" % retval)
        if retval != 0:
            raise RuntimeError("Unable to reach given server: %s" %
                               server)

    def commit(self):
        self.logger.info("Connecting to VDSM server")


class SetEnginePassword(utils.Transaction.Element):
    title = "Setting Engine password"

    def commit(self):
        self.logger.info("Setting Engine password")