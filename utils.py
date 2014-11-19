#!/usr/bin/env python

import os
import time
import sys
import logging
import config_ini

from datetime import datetime

from cinderclient.client import Client as CinderClient
from novaclient.client import Client as NovaClient

import cinderclient.exceptions
import novaclient.exceptions

username = os.environ['OS_USERNAME']
password = os.environ['OS_PASSWORD']
tenant_id = os.environ['OS_TENANT_NAME']
auth_url = os.environ['OS_AUTH_URL']

cinder_client = CinderClient(1, username, password, tenant_id, auth_url)
nova_client = NovaClient(2, username, password, tenant_id, auth_url)

execution_datetime = datetime.now().isoformat()
appLogger = logging.getLogger(__name__)


#########################################################################
class VolumeUtils(object):
    """Class for getting volume info"""

    # -------------------------------------------------------------------
    def __init__(self):
        """ Constructor """

    #--------------------------------------------------------------------
    @staticmethod
    def get_volume_info(volume_id):
        """
        Return dict with volume metadata

        :rtype: dict
        """
        try:
            volume = cinder_client.volumes.get(volume_id)
        except cinderclient.exceptions.NotFound as err:
            appLogger.error(err)
            sys.exit()

        return {
            "id": volume.id,
            "display_name": volume.display_name,
            "status": volume.status,
            "size": volume.size,
            "bootable": volume.bootable,
            "snapshot_id": volume.snapshot_id,
            "attachments": volume.attachments,
            "metadata": volume.metadata
        }

    #--------------------------------------------------------------------
    @staticmethod
    def get_attached_volumes(server_id):
        """
        Returns list of attached volumes (volume id's) for vm instance

        :rtype: list
        """
        try:
            server_object = nova_client.servers.get(server_id)
        except novaclient.exceptions.NotFound as err:
            appLogger.error(err)
            sys.exit()

        attached_volumes = getattr(server_object, 'os-extended-volumes:volumes_attached')
        appLogger.debug("Attached volumes for vm instance %s: %s"
                        % (server_id, attached_volumes))

        return attached_volumes

    #--------------------------------------------------------------------
    def get_volume_device(self, volume_id):
        """
        Returns volume attached to device

        :rtype: str
        """
        volume = self.get_volume_info(volume_id)

        if not volume.get("attachments"):
            attached_device = None
        else:
            attached_device = volume.get("attachments")
            attached_device = attached_device[0]["device"]

        appLogger.debug("Volume %s is attached to %s"
                        % (volume_id, attached_device))

        return attached_device

    #--------------------------------------------------------------------
    @staticmethod
    def create_temp_volume(snapshot_id):
        """
        Create temporary volumes from snapshot

        :param snapshot_id: Snapshot ID
        :type snapshot_id: str
        :rtype: str
        """
        snapshot = SnapshotUtils()
        info = snapshot.get_snapshot_info(snapshot_id)

        volume_size = info.get("size")
        volume_name = "Temporary_volume_created_from_snapshot_%s" % snapshot_id
        volume_metadata = VolumeUtils().get_volume_device(info.get("volume_id"))

        try:
            temporary_volume = cinder_client.volumes.create(volume_size, snapshot_id=snapshot_id,
                                                            display_name=volume_name,
                                                            metadata={"device": volume_metadata})
        except cinderclient.exceptions.OverLimit as err:
            appLogger.error(err)
            sys.exit()

        appLogger.info("Creating temporary volume from snapshot %s" % snapshot_id)
        volume = VolumeUtils.get_volume_info(temporary_volume.id)
        status = volume.get("status")

        while status == "creating":
            time.sleep(5)
            volume = VolumeUtils.get_volume_info(temporary_volume.id)
            status = volume.get("status")

            if status == "error":
                sys.exit()
            elif status == "available":
                appLogger.info("Creating temporary volume %s completed"
                               % temporary_volume.id)

        appLogger.debug("Temporary volume id: %s" % temporary_volume.id)

        return temporary_volume.id

    #--------------------------------------------------------------------
    @staticmethod
    def delete_temporary_volume(volume_id):
        """
        Delete temporary volume
        :param volume_id: Volume ID
        :type volume_id: str
        """
        while True:
            volume_info = VolumeUtils.get_volume_info(volume_id)
            status = volume_info.get("status")

            if status == "available":
                appLogger.info("Deleting temporary volume: %s" % volume_id)
                cinder_client.volumes.delete(volume_id)
                break
            else:
                time.sleep(5)


#########################################################################
class SnapshotUtils(object):
    """Class for getting snapshot info"""

    #--------------------------------------------------------------------
    def __init__(self):
        """ Constructor """

    #--------------------------------------------------------------------
    @staticmethod
    def get_snapshot_info(snapshot_id):
        """
        Returns snapshot info

        :param snapshot_id: Snapshot ID
        :type snapshot_id: str
        :rtype: dict
        """
        try:
            snapshot = cinder_client.volume_snapshots.get(snapshot_id)
        except cinderclient.exceptions.NotFound as err:
            appLogger.error(err)
            sys.exit()

        return {
            "created_at": snapshot.created_at,
            "size": snapshot.size,
            "volume_id": snapshot.volume_id
        }

    #--------------------------------------------------------------------
    @staticmethod
    def get_snapshot_status(snapshot_id):
        """
        Return snapshot status

        :param snapshot_id: Snapshot ID
        :type snapshot_id: str
        :rtype: str
        """
        try:
            snapshot = cinder_client.volume_snapshots.get(snapshot_id)
        except cinderclient.exceptions.NotFound as err:
            appLogger.error(err)
            sys.exit()

        return snapshot.status

    #--------------------------------------------------------------------
    def create_snapshot(self, volume_id):
        """
        Create snapshot and returns list of snapshot id's

        :param volume_id: Volume ID
        :type volume_id: str
        :rtype: str
        """
        try:
            snapshot = cinder_client.volume_snapshots.create(
                volume_id, force=True, display_name="snapshot_%s_%s"
                                                    % (volume_id, execution_datetime))
        except cinderclient.exceptions.OverLimit as err:
            appLogger.error(err)
            sys.exit()

        appLogger.info("Creating temporary snapshot %s" % snapshot.id)
        status = self.get_snapshot_status(snapshot.id)

        while status == "creating":
            time.sleep(2)
            status = self.get_snapshot_status(snapshot.id)

        if status == "error":
            sys.exit()
        elif status == "available":
            appLogger.info("Snapshot %s completed" % snapshot.id)

        appLogger.debug("Temporary snapshot id: %s" % snapshot.id)

        return snapshot.id

    #--------------------------------------------------------------------
    def delete_temp_snapshot(self, snapshot_id):
        """
        Delete temporary snapshot

        :param snapshot_id: Snapshot ID
        :type snapshot_id: str
        """
        while True:
            status = self.get_snapshot_status(snapshot_id)

            if status == "available":
                appLogger.info("Deleting temporary snapshot: %s" % snapshot_id)
                cinder_client.volume_snapshots.delete(snapshot_id)
                break
            else:
                time.sleep(5)


#########################################################################
class BackupUtils(object):
    """Class for getting backup info"""

    #--------------------------------------------------------------------
    def __init__(self):
        """ Constructor """

    #--------------------------------------------------------------------
    @staticmethod
    def get_backup_info(backup_id):
        """
        Returns backup info

        :param backup_id: Backup ID
        :type backup_id: str
        :rtype: dict
        """
        try:
            backup_info = cinder_client.backups.get(backup_id)
        except cinderclient.exceptions.NotFound as err:
            appLogger.error(err)
            sys.exit()

        return {
            "name": backup_info.name,
            "status": backup_info.status
        }

    #--------------------------------------------------------------------
    @staticmethod
    def create_volume_backup(volume_id):
        """
        Create backup from temporary volume

        :param volume_id: Temporary volume ID
        :type volume_id: str
        :rtype: str
        """
        backup_id = None
        volume_info = VolumeUtils().get_volume_info(volume_id)
        status = volume_info.get("status")
        backup_name = "Backup_created_from_volume_%s" % volume_id

        while True:
            if status == "available":
                try:
                    backup_volume = cinder_client.backups.create(volume_id, name=backup_name)
                except cinderclient.exceptions.NotFound as err:
                    appLogger.error(err)
                    sys.exit()
                appLogger.info("Creating backup from temporary volume %s" % volume_id)
                backup_id = backup_volume.id
                break
            else:
                sys.exit()

        appLogger.debug("Backup id: %s" % backup_id)

        return backup_id

    def restore_volume_backup(self, backup_id):
        """
        Restore volume from backup

        :param backup_id: Backup ID
        :type backup_id: str
        """
        volume_id = None
        status = self.get_backup_info(backup_id).get("status")

        if status == "available":
            try:
                restore = cinder_client.restores.restore(backup_id)
            except cinderclient.exceptions.OverLimit as err:
                appLogger.error(err)
                sys.exit()

            appLogger.info("Restoring volume from backup %s" % backup_id)
            volume_status = VolumeUtils.get_volume_info(restore.volume_id).get("status")
            volume_id = restore.volume_id

            if volume_status == "error_restoring":
                sys.exit()

            while volume_status == "restoring-backup":
                time.sleep(10)
                volume_status = VolumeUtils.get_volume_info(restore.volume_id).get("status")
        elif status == "error":
            sys.exit()

        appLogger.debug("Restored volume id %s: " % volume_id)

        return volume_id


#########################################################################
class InstanceUtils(object):
    """Class for getting backup info"""

    #--------------------------------------------------------------------
    def __init__(self, server_id, volumes_id):
        """
        Constructor

        :param server_id: VM instance ID
        :type server_id: str
        :param volumes_id: Volume id's
        :type volumes_id: list
        """
        self.server_id = server_id
        self.volumes_id = volumes_id

    #--------------------------------------------------------------------
    def get_instance_info(self):
        """
        Get vm instance info
        :rtype: dict
        """
        try:
            vm_instance = nova_client.servers.get(self.server_id)
        except novaclient.exceptions.NotFound as err:
            appLogger.error(err)
            sys.exit()

        return {
            "name": vm_instance.name,
            "flavor_id": vm_instance.flavor.get("id"),
            "status": vm_instance.status
        }

    #--------------------------------------------------------------------
    def create_vm(self):
        """
        Create new vm instance using restored volumes
        :rtype: str
        """
        instance_info = self.get_instance_info()
        flavor_id = instance_info.get("flavor_id")
        flavor = nova_client.flavors.get(flavor_id)
        vm_name = "Restored_%s" % instance_info.get("name")
        device_map = {}

        for volume_id in self.volumes_id:
            volume_info = VolumeUtils().get_volume_info(volume_id)
            volume_metadata = volume_info.get("metadata")
            try:
                device_map.update({str(volume_metadata['device']): str(volume_id)})
            except KeyError as err:
                appLogger.error(err)
                sys.exit()

        try:
            new_vm = nova_client.servers.create(vm_name, None, flavor, block_device_mapping=device_map)
        except NameError as err:
            appLogger.error(err)
            sys.exit()

        status = new_vm.status
        appLogger.info("Creating new vm instance %s" % new_vm.id)

        while status == "BUILD":
            time.sleep(5)
            current_instance = nova_client.servers.get(new_vm.id)
            status = current_instance.status

        appLogger.info("New vm instance: %s completed" % new_vm.id)
        appLogger.debug("New vm instance id: %s" % new_vm.id)

        return new_vm.id