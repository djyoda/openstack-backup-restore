#!/usr/bin/env python

####1###

####2###

import os
import time
import sys
import logging
import config_ini

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

appLogger = logging.getLogger(__name__)


#-------------------------------------------------------------------
def get_attached_volumes(server_id):
    """
    Returns attached volumes for specified vm instance

    :param server_id: vm instance id
    :type server_id: str
    :returns: list of class 'Volume'
    :rtype: list
    """
    try:
        volumes = nova_client.volumes.get_server_volumes(server_id)
    except novaclient.exceptions.NotFound, err:
        appLogger.exception(err)
        sys.exit()

    return volumes


#-------------------------------------------------------------------
def get_snapshot_info(snapshot_id):
    """
    Returns snapshot info

    :param snapshot_id: snapshot ID
    :type snapshot_id: str
    :returns: snapshot info dict
    :rtype: dict
    """
    try:
        snapshot = cinder_client.volume_snapshots.get(snapshot_id)
    except cinderclient.exceptions.NotFound, err:
        appLogger.exception(err)
        sys.exit()

    return {
        'created_at': snapshot.created_at,
        'size': snapshot.size,
        'volume_id': snapshot.volume_id
    }


#------------------------------------------------------------------
def get_snapshot_status(snapshot_id):
    """
    Return snapshot status

    :param snapshot_id: snapshot id
    :type snapshot_id: str
    :returns: snapshot status
    :rtype: str
    """
    try:
        snapshot = cinder_client.volume_snapshots.get(snapshot_id)
    except cinderclient.exceptions.NotFound, err:
        appLogger.exception(err)
        sys.exit()

    return snapshot.status


#-------------------------------------------------------------------
def create_snapshot(volume_id):
    """
    Create snapshot from volume

    :param: volume id
    :type volume_id: str
    :returns: snapshot id
    :rtype: str
    """
    try:
        snapshot = cinder_client.volume_snapshots.create(
            volume_id, force=True, display_name='snapshot_from_volume_%s' % volume_id)
    except cinderclient.exceptions.OverLimit, err:
        appLogger.exception(err)
        sys.exit()

    appLogger.info('Creating temporary snapshot %s' % snapshot.id)
    status = get_snapshot_status(snapshot.id)

    while status == 'creating':
        time.sleep(2)
        status = get_snapshot_status(snapshot.id)

    if status == 'error':
        sys.exit()
    elif status == 'available':
        appLogger.info('Snapshot %s completed' % snapshot.id)

    appLogger.debug('Temporary snapshot id: %s' % snapshot.id)

    return snapshot.id


#-------------------------------------------------------------------
def delete_temp_snapshot(snapshot_id):
    """
    Delete temporary snapshot

    :param snapshot_id: snapshot id
    :type snapshot_id: str
    """
    while True:
        status = get_snapshot_status(snapshot_id)

        if status == 'available':
            appLogger.info('Deleting temporary snapshot: %s' % snapshot_id)
            cinder_client.volume_snapshots.delete(snapshot_id)
            break
        else:
            time.sleep(5)


#-------------------------------------------------------------------
def get_volume_info(volume_id):
    """
    Return volume info

    :param volume_id: volume id
    :type volume_id: str
    :returns: volume info dict
    :rtype: dict
    """
    try:
        volume = cinder_client.volumes.get(volume_id)
    except cinderclient.exceptions.NotFound, err:
        appLogger.exception(err)
        sys.exit()

    return {
        'id': volume.id,
        'display_name': volume.display_name,
        'status': volume.status,
        'size': volume.size,
        'bootable': volume.bootable,
        'snapshot_id': volume.snapshot_id,
        'attachments': volume.attachments,
        'metadata': volume.metadata
    }


#-------------------------------------------------------------------
def create_temp_volume(snapshot_id):
    """
    Create temporary volume from snapshot

    :param snapshot_id: snapshot id
    :type snapshot_id: str
    :returns: volume id
    :rtype: str
    """
    volume_size = get_snapshot_info(snapshot_id).get('size')
    volume_name = 'Backup volume_%s' % get_snapshot_info(snapshot_id).get('volume_id')

    try:
        temporary_volume = cinder_client.volumes.create(volume_size, snapshot_id=snapshot_id,
                                                        display_name=volume_name)
    except cinderclient.exceptions.OverLimit, err:
        appLogger.exception(err)
        sys.exit()

    appLogger.info('Creating temporary volume from snapshot %s' % snapshot_id)
    status = get_volume_info(temporary_volume.id).get('status')

    while status == 'creating':
        time.sleep(5)
        status = get_volume_info(temporary_volume.id).get('status')

        if status == 'error':
            appLogger.error('Volume %s hs error status' % temporary_volume.id)
            sys.exit()
        elif status == 'available':
            appLogger.info('Temporary volume %s completed'
                           % temporary_volume.id)

    appLogger.debug('Temporary volume id: %s' % temporary_volume.id)

    return temporary_volume.id


#-------------------------------------------------------------------
def delete_temporary_volume(volume_id):
    """
    Delete temporary volume

    :param volume_id: volume ID
    :type volume_id: str
    """
    while True:
        status = get_volume_info(volume_id).get('status')

        if status == 'available':
            appLogger.info('Deleting temporary volume: %s' % volume_id)
            cinder_client.volumes.delete(volume_id)
            break
        else:
            time.sleep(5)


#-------------------------------------------------------------------
def get_backup_info(backup_id):
    """
    Returns backup info

    :param backup_id: backup id
    :type backup_id: str
    :returns: backup info dict
    :rtype: dict
    """
    try:
        backup_info = cinder_client.backups.get(backup_id)
    except cinderclient.exceptions.NotFound, err:
        appLogger.exception(err)
        sys.exit()

    return {
        'name': backup_info.name,
        'status': backup_info.status,
        'description': backup_info.description
    }


#-------------------------------------------------------------------
def create_volume_backup(volume_id, bckp_desc):
    """
    Create backup from temporary volume

    :param volume_id: temporary volume id
    :type volume_id: str
    :param bckp_desc: backup description
    :type bckp_desc: str
    :returns: backup id
    :rtype: str
    """
    backup_id = None
    status = get_volume_info(volume_id).get('status')
    backup_name = 'Backup_created_from_volume_%s' % volume_id

    while True:
        if status == 'available':
            try:
                backup_volume = cinder_client.backups.create(volume_id, name=backup_name,
                                                             description=bckp_desc)
            except cinderclient.exceptions.NotFound, err:
                appLogger.exception(err)
                sys.exit()
            appLogger.info('Creating backup from temporary volume %s' % volume_id)
            backup_id = backup_volume.id
            break
        else:
            sys.exit()

    appLogger.debug("Backup id: %s" % backup_id)

    return backup_id


#-------------------------------------------------------------------
def restore_volume_backup(backup_id):
    """
    Restore volume from backup

    :param backup_id: backup id
    :type backup_id: str
    :returns: volume id
    :rtype: str
    """
    volume_id = None
    status = get_backup_info(backup_id).get('status')

    if status == 'available':
        try:
            restore = cinder_client.restores.restore(backup_id)
        except cinderclient.exceptions.OverLimit, err:
            appLogger.exception(err)
            sys.exit()

        appLogger.info('Restoring volume from backup %s' % backup_id)
        volume_status = get_volume_info(restore.volume_id).get('status')
        volume_id = restore.volume_id

        if volume_status == 'error_restoring':
            sys.exit()

        while volume_status == 'restoring-backup':
            time.sleep(10)
            volume_status = get_volume_info(restore.volume_id).get('status')
    elif status == 'error':
        sys.exit()

    appLogger.debug('Restored volume id %s: ' % volume_id)

    return volume_id


#-------------------------------------------------------------------
def delete_backup(backup_id):
    """
    :param backup_id: backup id
    :type backup_id: str
    """
    status = get_backup_info(backup_id).get('status')

    if status == 'available':
        cinder_client.backups.delete(backup_id)
        appLogger.info('Deleting backup: %s' % backup_id)
    else:
        appLogger.error('Unable to delete backup: %s. The backup status is %s'
                        % (backup_id, status))


#-------------------------------------------------------------------
def get_device_mapping(backup_id, volume_id):
    """
    Restore volume from backup

    :param backup_id: backup id
    :type backup_id: str
    :param volume_id: volume id
    :type volume_id: str
    :returns: device mapping dict
    :rtype: dict
    """
    backup_description = get_backup_info(backup_id).get('description')

    return {
        str(backup_description): str(volume_id)
    }


#-------------------------------------------------------------------
def get_instance_info(server_id):
    """
    Get info from vm instance
    :param server_id: vm instance id
    :type server_id: str
    :returns: vm instance info dict
    :rtype: dict
    """
    try:
        vm_instance = nova_client.servers.get(server_id)
    except novaclient.exceptions.NotFound, err:
        appLogger.exception(err)
        sys.exit()

    return {
        'name': vm_instance.name,
        'flavor_id': vm_instance.flavor.get('id'),
        'flavor': nova_client.flavors.get(vm_instance.flavor.get('id')),
        'status': vm_instance.status
    }


#--------------------------------------------------------------------
def create_vm(server_id, device_map):
    """
    Create new vm instance using restored volumes
    :param server_id: vm instance id
    :type server_id: str
    :returns: vm instance id
    :rtype: str
    """
    vm_instance = get_instance_info(server_id)
    vm_name = 'Restored_%s' % vm_instance.get('name')
    flavor = vm_instance.get('flavor')

    try:
        new_vm = nova_client.servers.create(vm_name, None, flavor, block_device_mapping=device_map)
    except NameError, err:
        appLogger.exception(err)
        sys.exit()

    status = new_vm.status
    appLogger.info('Creating new vm instance %s' % new_vm.id)

    while status == 'BUILD':
        time.sleep(5)
        current_instance = nova_client.servers.get(new_vm.id)
        status = current_instance.status

    appLogger.info('New vm instance: %s completed' % new_vm.id)
    appLogger.debug('New vm instance id: %s' % new_vm.id)

    return new_vm.id
