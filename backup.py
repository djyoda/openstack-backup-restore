#!/usr/bin/env python

import sys

from utils import VolumeUtils
from utils import SnapshotUtils
from utils import BackupUtils


##########################################################################
class Backup(object):
    """Class for volume backup"""

    #--------------------------------------------------------------------
    def __init__(self, server_id):
        """
        Constructor

        :param server_id: VM ID
        :type server_id: str
        """
        self.server_id = server_id

    #----------------------------------------------------------------
    def do_backup(self):
        """
        Performs a volume backup
        """

        snapshots, volumes, backups = [], [], []
        attached_volumes = VolumeUtils.get_attached_volumes(self.server_id)

        for volume_id in attached_volumes:
            snapshot = SnapshotUtils()
            snapshot_id = snapshot.create_snapshot(volume_id.get("id"))
            snapshots.append(snapshot_id)

        for snapshot_id in snapshots:
            temporary_volume = VolumeUtils.create_temp_volume(snapshot_id)
            volumes.append(temporary_volume)

        for volume_id in volumes:
            backup_volume = BackupUtils.create_volume_backup(volume_id)
            backups.append(backup_volume)
            VolumeUtils.delete_temporary_volume(volume_id)

        for snapshot_id in snapshots:
            SnapshotUtils().delete_temp_snapshot(snapshot_id)

        return backups


#########################################################################
class Restore(object):
    """Class for volume backup"""

    #--------------------------------------------------------------------
    def __init__(self, backups):
        """
        Constructor

        :param backups: List of backup id's
        :type backups: list
        """
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
    backup = Backup(server_id)
    backup.do_backup()