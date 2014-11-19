#!/usr/bin/env python

import sys

from utils import BackupUtils
from utils import InstanceUtils


#########################################################################
class Restore(object):
    """Class for volume backup"""

    #--------------------------------------------------------------------
    def __init__(self, server_id, backups):
        """
        Constructor

        :param server_id: VM instance ID
        :type server_id: str
        :param backups: List of backup id's
        :type backups: list
        """
        self.server_id = server_id
        self.backups = backups

    #----------------------------------------------------------------
    def do_restore(self):
        """
        Performs a restore from volume backup
        """
        restored_volumes = []

        for backup_id in self.backups:
            restore = BackupUtils().restore_volume_backup(backup_id)
            restored_volumes.append(restore)

        return restored_volumes


if __name__ == "__main__":
    server_id = sys.argv[1]
    backups_id = sys.argv[2:]
    restored_backup = Restore(server_id, backups_id)
    volumes_id = restored_backup.do_restore()
    vm = InstanceUtils(server_id, volumes_id)
    vm.create_vm()
