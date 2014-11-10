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
    @classmethod
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
            "is_bootable": volume.bootable,
	    "snapshot_id": volume.snapshot_id,
	    "attachments": volume.attachments
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
                             % (volume.get("display_name"), execution_datetime)

            )
            status = self.get_snapshot_status(snapshot.id)
	    while status == "creating":
		print "Snapshot: %s has creating status, wait for 2 sec ..." % snapshot.id
	 	time.sleep(2)
 		status = self.get_snapshot_status(snapshot.id)
	    if status == "error":
		sys.exit("Snapshot: %s has error state!" % snapshot.id)
	    elif status == "available":
		print "Snapshot: %s has been created." % snapshot.id
	        metadata.append({"created": snapshot.created_at, "id": snapshot.id, 
			         "size": snapshot.size, 
			         "display_name": volume.get("display_name")})
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
            snapshot_id = snap_id.get("id")
	    volume_size = snap_id.get("size")
            volume_name = "backup_%s" % snap_id.get("display_name")
            temp_volume = cinder_client.volumes.create(volume_size, snapshot_id=snapshot_id, 
						       display_name=volume_name)
            print "Creating temporary volume: %s" % volume_name
	    vol = self.get_volume_metadata(temp_volume.id)
	    status = vol.get("status")
	    while status == "creating":
		print "Temporary volume: %s has creating status. wait for 5 seconds ... " % temp_volume.id
		time.sleep(5)
	 	vol = self.get_volume_metadata(temp_volume.id)
            	status = vol.get("status")
		if status == "error":
		    sys.exit("Temporary volume: %s has error status!") % temp_volume.id  
		elif status == "available":
		    print "Temporary volume: %s has been created." % temp_volume.id
		    metadata.append(temp_volume.id)
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
		volume_name = vol.get("display_name")
                backup_name = volume_name.replace("backup_", "backup_of_")
                if status == "available":
		    print "Creating backup: %s" % backup_name
  		    backup_vol = cinder_client.backups.create(
			uuid, name=backup_name)
		    metadata.append({"id": backup_vol.id, 
				     "boot": vol.get('is_bootable')})
                    break
		else:
		    sys.exit("Unable to create backup of temporary volume %s. " 
			     "Temporary volume: %s has no available state. The state is %s: !" % volume_name, status)
        return metadata

    #--------------------------------------------------------------
    def delete_temp_volume(self, volumes_uuid):
        """
        Delete temporary volume and snapshot

        :param volumes_uuid: List of temporary volume uuid
        :type volumes_uuid: list
        """
	for uuid in volumes_uuid:
	    try:
	        volume = self.get_volume_metadata(uuid)
	    except:
		print "There is no volume with uuid %s" % uuid
		pass
	    else:
		while True:
		    volume = self.get_volume_metadata(uuid)
		    status = volume.get("status")
		    if status == "available":
		        self.delete_volume(uuid)
		        break
		    else:
		        print "Volume is not available, wait for 5 sec ..."
			time.sleep(5)

if __name__ == "__main__":
    server = Backup("f5b56c67-8695-493a-931d-c26aa068d23b")
    get_volumes = server.get_attached_volumes()
    snapshots = server.create_snapshots(get_volumes)
    create_vol = server.create_temp_volume(snapshots)
    backup = server.create_backup(create_vol)
    server.delete_temp_volume(create_vol)
   # print backup
#server = Backup("f5b56c67-8695-493a-931d-c26aa068d23b")
#server.delete_temp_volume(['14b2f461-37d1-4de7-9bf4-faeded405294', '2b32d6f7-9380-4887-aaef-9e6794084899'])
