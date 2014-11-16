#!/usr/bin/env python

import os
import sys
import logging
import config_ini

import time

from restore import Restore

from cinderclient.client import Client as CinderClient

username = os.environ['OS_USERNAME']
password = os.environ['OS_PASSWORD']
tenant_id = os.environ['OS_TENANT_NAME']
auth_url = os.environ['OS_AUTH_URL']

cinder_client = CinderClient(1, username, password, tenant_id, auth_url)

appLogger = logging.getLogger(__name__)


#########################################################################
class Delete(object):
    """Class for deleting backup"""

    # -------------------------------------------------------------------
    def __init__(self, backups):
        """
        Constructor

        :param backups: List of backup IDs
        :type backups: list
        """
        self.backups = backups

    # -------------------------------------------------------------------
    def delete_backup(self, backup_id):
        """
        :param backup_id: Backup ID
        :type backup_id: str
        """
        status = Restore.get_backup_status(backup_id)
        if status == "available":
            cinder_client.backups.delete(backup_id)
            appLogger.info("Deleting backup: %s" % backup_id)
        else:
            appLogger.error("Unable to delete backup: %s. The backup status is %s"
                            % (backup_id, status))


def main():
    # Provide list of backup IDs
    backups = sys.argv[1:]
    # Start deleting backups
    appLogger.info("Backup deletion started.")
    bckp_del = Delete(backups)
    for bckp_id in backups:
        bckp_del.delete_backup(bckp_id)
    appLogger.info("Backup deletion finished")

if __name__ == "__main__":
    main()