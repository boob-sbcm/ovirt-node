#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# cim_page.py - Copyright (C) 2012 Red Hat, Inc.
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
from ovirt.node import plugins, valid, ui, utils
import cim_model
from ovirt.node.plugins import Changeset

"""
Configure CIM
"""


class Plugin(plugins.NodePlugin):
    _model = None

    def __init__(self, app):
        super(Plugin, self).__init__(app)
        self._model = {}

    def has_ui(self):
        return True

    def name(self):
        return "CIM"

    def rank(self):
        return 45

    def model(self):
        cfg = cim_model.CIM().retrieve()
        self.logger.debug(cfg)
        model = {"cim.enabled": True if cfg["enabled"] else False,
                 "cim.password": "",
                 }
        return model

    def validators(self):
        return {"cim.password": valid.Text()}

    def ui_content(self):
        ws = [ui.Header("header[0]", "CIM"),
              ui.Checkbox("cim.enabled", "Enable CIM"),
              ui.Divider("divider[0]"),
              ui.Header("header[1]", "CIM Password"),
              ui.ConfirmedEntry("cim.password", "Password:",
                                is_password=True)
              ]

        page = ui.Page("page", ws)
        self.widgets.add(ws)
        return page

    def on_change(self, changes):
        if changes.contains_any(["cim.password"]):
            self._model.update(changes)

    def on_merge(self, effective_changes):
        self.logger.debug("Saving CIM page")
        changes = Changeset(self.pending_changes(False))
        effective_model = Changeset(self.model())
        effective_model.update(effective_changes)

        self.logger.debug("Changes: %s" % changes)
        self.logger.debug("Effective Model: %s" % effective_model)

        cim_keys = ["cim.password", "cim.enabled"]

        txs = utils.Transaction("Updating CIM configuration")

        if changes.contains_any(cim_keys):
            is_enabled = effective_model["cim.enabled"]
            pw = effective_model["cim.password"]

            model = cim_model.CIM()
            model.update(is_enabled)
            txs += model.transaction(cim_password=pw)
        progress_dialog = ui.TransactionProgressDialog("dialog.txs", txs, self)
        progress_dialog.run()
        return self.ui_content()
