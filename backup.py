#!/usr/bin/env python

import os
import sys

from datetime import datetime
import time

from cinderclient.client import Client as CinderClient
from novaclient.client import Client as NovaClient

username = os.environ['OS_USERNAME']
password = os.environ['OS_PASSWORD']
tenant_id = os.environ['OS_TENANT_NAME']
auth_url = os.environ['OS_AUTH_URL']

cinder_client = CinderClient(1, username, password, tenant_id, auth_url)
nova_client = NovaClient(2, username, password, tenant_id, auth_url)

execution_datetime = datetime.now().isoformat()


########################################################################
class Backup(object):
    """Class for backup volumes attached to VM"""

    #-------------------------------------------------------------------
    def __init__(self, server_id):
        """
	Constructor

	:param server_id: VM ID
	:type server_id: string
	"""
	self.server_id = server_id

    #-------------------------------------------------------------------
    def get_attached_volumes(self):
        """
        Returns list of attached volumes

        :rtype: list
        """
        server_object = nova_client.servers.find(id=self.server_id)
        volumes = getattr(server_object, 'os-extended-volumes:volumes_attached')
        metadata = []
        for volume in volumes:
            metadata.append(self.get_volume_metadata(volume.get("id")))
        return metadata

    #-------------------------------------------------------------------
    def get_volume_metadata(self, volume_uuid):
        """
        Return dict with volume metadata
    
        :param volume_uuid: Volume ID
        :type volume_uuid: str
        :rtype: dict
        """
        volume = cinder_client.volumes.get(volume_uuid)
    
        return {
            "id": volume.id,
            "display_name": volume.display_name,
            "status": volume.status,
            "size": volume.size,
            "is_bootable": volume.bootable
        }

    #------------------------------------------------------------------
    def create_snapshots(self, volumes):
        """
        Create snapshots for volumes attached to instance

        :param volumes: List of volumes attached to instance
        :type volumes: list
	:rtype: list
        """

        metadata = []
        for volume in volumes:
            snapshot = cinder_client.volume_snapshots.create(
                volume.get("id"),
                force=True,
                display_name="snapshot_%s_%s"
                             % (volume.get("display_name"), execution_datetime),

            )
            metadata.append([snapshot.created_at, snapshot.id, snapshot.size, volume.get("display_name")])
        return metadata

    #----------------------------------------------------------------
    def get_snapshot_status(self, snapshot_id):
	"""
	Return snapshot status

	:param snapshot_id: Snapshot ID
	:type snapshot_id: str
	:rtype: str
	"""
        snap_stat = cinder_client.volume_snapshots.get(snapshot_id)
        return snap_stat.status

    #----------------------------------------------------------------
    def delete_snapshot(self, snapshot_id):
        """
        Delete snapshot

        :param snapshot_id: Snapshot ID
        :type snapshot_id: str
        """
        cinder_client.volume_snapshots.delete(snapshot_id)
        print "Deleting snapshot: %s" % snapshot_id

    #----------------------------------------------------------------
    def delete_volume(self, volume_uuid):
        """
        Delete snapshot

        :param snapshot_id: Volume UUID
        :type snapshot_id: str
        """
        cinder_client.volumes.delete(volume_uuid)
        print "Deleting volume: %s" % volume_uuid

    #---------------------------------------------------------------
    def create_temp_volume(self, snapshots):
        """
        Create temporary volumes from snapshot

        :param snapshots: List of snapshots
        :type snapshots: list
	:rtype: list
        """
        metadata = []
        for snap_id in snapshots:
            while True:
                status = self.get_snapshot_status(snap_id[1])
		volume_size = snap_id[2]
                snapshot_id = snap_id[1]
                volume_name = "temp_%s" % snap_id[3]
                if status == "available":
		    print "Creating temporary volume: %s" % volume_name
                    temp_volume = cinder_client.volumes.create(volume_size, snapshot_id=snapshot_id, 
							       display_name=volume_name)
		    metadata.append(temp_volume.id)
                    break
                elif status == "error":
                    sys.exit("Unable to create temporary volume. Snapshot status for snapshot: %s is in error state!" % snapshot_id)
                else:
                    print "Snapshot: %s is still in creating state. Waiting for 2 seconds ..." % snapshot_id
                    time.sleep(2)
        return metadata

    #--------------------------------------------------------------
    def create_backup(self, volumes_uuid):
        """
        Create backup from temporary volume
        
        :param volumes_uuid: List of temporary volume uuid
        :type volumes_uuid: list
	:rtype: list
        """
        metadata = []
        for uuid in volumes_uuid:
            while True:
                vol = self.get_volume_metadata(uuid)
                status = vol.get("status")
                backup_name = "backup%s" % vol.get("display_name").replace("temp", '')
                if status == "available":
		    print "Creating backup: %s" % backup_name
  		    backup_vol = cinder_client.backups.create(uuid, name=backup_name)
		    metadata.append([backup_vol.id, backup_vol.name, vol.get("is_bootable")])
                    break
                else:
                    print "Temporary volume: %s is still in creating state. Waiting for 5 seconds ..." % vol.get("display_name")
                    time.sleep(5)
        return metadata



if __name__ == "__main__":
    server = Backup("241876d3-5a80-44b2-b88f-93d23a20fd15")
    get_volumes = server.get_attached_volumes()
    snapshots = server.create_snapshots(get_volumes)
    create_vol = server.create_temp_volume(snapshots)
    backup = server.create_backup(create_vol)
