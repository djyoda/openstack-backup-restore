#!/usr/bin/env python

import sys
import utils


#########################################################################
class Restore(object):
    """Class for restoring volume backup"""

    #--------------------------------------------------------------------
    def __init__(self, server_id, backups):
        """
        Constructor

        :param server_id: vm instance id
        :type server_id: str
        :param backups: List of backup id's
        :type backups: list
        """
        self.server_id = server_id
        self.backups = backups

    #----------------------------------------------------------------
    def do_restore_backup(self):
        """
        Performs a restore from volume backup

        :returns: device map to restored volume id
        :rtype: dict
        """
        restored_volumes = {}

        for backup in self.backups:
            restore = utils.restore_volume_backup(backup)
            volume = utils.get_device_mapping(backup, restore)
            restored_volumes.update(volume)

        return restored_volumes

    #----------------------------------------------------------------
    def do_restore_vm(self):
        """
        Create new vm instance with attache restored volumes from backup.

        :returns: returns new vm instance id
        :rtype: str
        """
        device_map = self.do_restore_backup()

        new_vm = utils.create_vm(self.server_id, device_map)

        return new_vm


def main():
    server_id = sys.argv[1]
    backups_id = sys.argv[2:]
    restore = Restore(server_id, backups_id)
    restore.do_restore_vm()

if __name__ == "__main__":
    main()