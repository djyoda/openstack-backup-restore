#!/usr/bin/env python

import os
import sys

from datetime import datetime
import time

from cinderclient.client import Client as CinderClient
from novaclient.client import Client as NovaClient

from backup import Backup

username = os.environ['OS_USERNAME']
password = os.environ['OS_PASSWORD']
tenant_id = os.environ['OS_TENANT_NAME']
auth_url = os.environ['OS_AUTH_URL']

cinder_client = CinderClient(1, username, password, tenant_id, auth_url)
nova_client = NovaClient(2, username, password, tenant_id, auth_url)

execution_datetime = datetime.now().isoformat()


# #######################################################################
class Restore(object):
    """Class for restore VM from volume backup"""

    # -------------------------------------------------------------------
    def __init__(self, server_id, backup):
        """
        Constructor
        :param server_id: VM ID
        :type server_id: str
        :param backup: List of backup ids
        :type backup: list
        """
        self.server_id = server_id
        self.backup = backup

    # -------------------------------------------------------------------
    def get_backup_status(self, backup_id):
        """
        Returns backup status
        :param backup_id: Backup ID
        :type backup_id: str
        :rtype: str
        """
        backup = cinder_client.backups.get(backup_id)
        status = backup.status
        return status

    # -------------------------------------------------------------------
    def get_flavor(self, server_id):
        """
        Returns Flavor ID
        :rtype: class
        """
        vm_instance = nova_client.servers.get(server_id)
        return nova_client.flavors.get(vm_instance.flavor.get("id"))

    #-------------------------------------------------------------------
    def restore_backup(self):
        """
        Restore backup from backup volume
        :rtype: dict
        """
        metadata = {}
        for bckp_id in self.backup:
            status = self.get_backup_status(bckp_id)
            if status == "available":
                print "Restoring the backup: %s" % bckp_id
                restore = cinder_client.restores.restore(bckp_id)
                volume = Backup.get_volume_metadata(restore.volume_id)
                volume_status = volume.get("status")

                if volume_status == "error_restoring":
                    sys.exit("There was some problem with restoring the backup."
                             "The new volume: %s has state: %s." % (restore.volume_id, volume_status))

                while volume_status == "restoring-backup":
                    print "Restoring backup is in progress ..."
                    time.sleep(10)
                    volume = Backup.get_volume_metadata(restore.volume_id)
                    volume_status = volume.get("status")

                volume_name = volume.get("display_name")
                metadata[str(volume_name)] = str(restore.volume_id)
            elif status == "error":
                sys.exit("Backup %s is in error state!" % bckp_id)
        return metadata

    #-------------------------------------------------------------------
    def get_dev_mapping(self):
        """
        Returns device mapping for volumes attached to vm
        :rtype: dict
        """
        metadata = {}
        volumes = Backup(self.server_id)
        attached_volumes = volumes.get_attached_volumes()
        for uuid in attached_volumes:
            volume_uuid = uuid.get("id")
            volume = cinder_client.volumes.get(volume_uuid)
            device = volume.attachments.pop()
            device_map = str(device.get("device"))
            metadata[str(uuid.get("display_name"))] = {device_map: str(volume_uuid)}
        return metadata

    #-------------------------------------------------------------------
    def get_dev_remapping(self, old_map, dev_map):
        """
        :param old_map: Dictionary returned from restore_backup.
        :type old_map: dict
        :param dev_map: Dictionary returned from get_dev_mapping.
        :type dev_map: dict
        :rtype: dict
         """
        new_dev_map, new_map = {}, {}
        for k, v in old_map.iteritems():
            new_map[k.replace('backup_', '')] = v
        for key in new_map.keys():
            dev_map[key][dev_map[key].keys()[0]] = new_map[key]
        for k, v in dev_map.iteritems():
            new_dev_map.update(v)
        return new_dev_map

    #-------------------------------------------------------------------
    def create_vm(self, device_map):
        """
        Create VM instance
        :rtype: str
        """
        flavor = self.get_flavor(self.server_id)
        old_vm = nova_client.servers.get(self.server_id)
        vm_name = old_vm.name
        new_vm = nova_client.servers.create(vm_name, '', flavor, block_device_mapping=device_map)
        status = new_vm.status
        while status == "BUILD":
            time.sleep(5)
            instance = nova_client.servers.get(new_vm.id)
            status = instance.status
            print "Restoring vm: %s from backup has been completed with status: %s" % (new_vm.id, status)
        return new_vm.id


def main():
    # Provide server id
    server_id = sys.argv[1]
    # Provide list of backup IDs
    backups = sys.argv[2:]
    vm = Restore(server_id, backups)
    # Restore backups
    restoring_bckp = vm.restore_backup()
    # Get device mapping from current vm instance
    dev_mapping = vm.get_dev_mapping()
    # Do device remapping for new vm instance
    dev_remap = vm.get_dev_remapping(restoring_bckp, dev_mapping)
    # Create new vm instance
    vm.create_vm(dev_remap)


if __name__ == "__main__":
    main()
