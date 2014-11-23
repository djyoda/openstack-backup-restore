#!/usr/bin/env python

import sys
import utils


#########################################################################
class Delete(object):
    """Class for deleting backup"""

    #--------------------------------------------------------------------
    def __init__(self, backups):
        """
        Constructor

        :param backups: list of backup id's
        :type backups: list
        """
        self.backups = backups

    #--------------------------------------------------------------------
    def do_delete_backup(self):
        """
        Delete volume backup
        """

        for backup_id in self.backups:
            utils.delete_backup(backup_id)


def main():
    backups = sys.argv[1:]
    bckp_del = Delete(backups)
    bckp_del.do_delete_backup()

if __name__ == "__main__":
    main()
