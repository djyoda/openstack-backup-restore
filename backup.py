#!/usr/bin/env python

import sys
import logging
import config_ini

import utils


##########################################################################
class Backup(object):
    """Class for volume backup"""

    #--------------------------------------------------------------------
    def __init__(self, server_id):
        """
        Constructor

        :param server_id: VM instance id
        :type server_id: str
        """
        self.server_id = server_id

    #----------------------------------------------------------------
    def do_backup(self):
        """
        Performs a volume backup

        :returns: Returns list of backup id's
        :rtype: list
        """

        backups = []
        attached_volumes = utils.get_attached_volumes(self.server_id)

        for volume in attached_volumes:
            snapshot = utils.create_snapshot(volume.id)
            temporary_volume = utils.create_temp_volume(snapshot)
            backup = utils.create_volume_backup(temporary_volume, volume.device)
            backups.append(backup)
            utils.delete_temporary_volume(temporary_volume)
            utils.delete_temp_snapshot(snapshot)

        return backups


if __name__ == "__main__":
    server_id = sys.argv[1]
    backup = Backup(server_id)
    backup.do_backup()