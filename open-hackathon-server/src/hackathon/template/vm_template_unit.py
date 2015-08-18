# -*- coding: utf-8 -*-
"""
Copyright (c) Microsoft Open Technologies (Shanghai) Co. Ltd.  All rights reserved.
 
The MIT License (MIT)
 
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
 
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
 
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

__author__ = 'Yifu Huang'

import sys

sys.path.append("..")
from hackathon.azureformation.azure_utility_db import (
    find_unassigned_endpoints,
)
from azure.servicemanagement import (
    WindowsConfigurationSet,
    LinuxConfigurationSet,
    OSVirtualHardDisk,
    ConfigurationSet,
    ConfigurationSetInputEndpoint,
)
from threading import (
    current_thread,
)
from hackathon import Component


class VMTemplateUnit(Component):
    # template name in virtual_environment
    PROVIDER = 'provider'
    LABEL = 'label'
    SERVICE_NAME = 'service_name'
    LOCATION = 'location'
    NAME = 'name'
    PROTOCOL = 'protocol'
    PORT= 'port'

    T_CONTAINER = 'container'
    T_ROLE_NAME = 'role_name'
    T_ROLE_SIZE = 'role_size'

    T_STORAGE_ACCOUNT = 'storage_account'
    T_DESCRIPTION = 'description'
    T_URL_BASE = 'url_base'

    T_CLOUD_SERVICE = 'cloud_service'

    T_DEPLOYMENT = 'deployment'
    T_DEPLOYMENT_NAME = 'deployment_name'
    T_DEPLOYMENT_SLOT = 'deployment_slot'

    T_IMAGE = 'image'
    T_TYPE = 'type'

    T_SYSTEM_CONFIG = 'system_config'
    T_OS_FAMILY = 'os_family'
    T_HOST_NAME = 'host_name'
    T_USER_NAME = 'user_name'
    T_USER_PASSWORD = 'user_password'

    T_NETWORK_CONFIG = 'network_config'
    T_CONFIGURATION_SET_TYPE = 'configuration_set_type'
    T_INPUT_ENDPOINTS = 'input_endpoints'
    T_LOCAL_PORT = 'local_port'

    T_REMOTE = 'remote'
    T_INPUT_ENDPOINT_NAME = 'input_endpoint_name'

    # image type name
    OS = 'os'
    VM = 'vm'
    # os family name
    WINDOWS = 'Windows'
    LINUX = 'Linux'

    # remote parameter name
    RP_DISPLAYNAME = 'displayname'
    RP_HOSTNAME = 'hostname'
    RP_USERNAME = 'username'
    RP_PASSWORD = 'password'

    # other constants
    BLOB_BASE = '%s-%s-%s-%s-%s-%s-%s-%s.vhd'
    MEDIA_BASE = 'https://%s.%s/%s/%s'

    def __init__(self, virtual_environment):
        self.virtual_environment = virtual_environment

    def get_image_type(self):
        return self.virtual_environment[self.T_IMAGE][self.T_TYPE]

    def is_vm_image(self):
        return self.get_image_type() == self.VM

    def get_vm_image_name(self):
        """
        Return None if image type is not vm
        :return:
        """
        return self.virtual_environment[self.T_IMAGE][self.NAME] if self.is_vm_image() else None

    def get_image_name(self):
        return self.virtual_environment[self.T_IMAGE][self.NAME]

    def get_system_config(self):
        """
        Return None if image type is vm
        :return:
        """
        if self.is_vm_image():
            return None
        sc = self.virtual_environment[self.T_SYSTEM_CONFIG]
        # check whether virtual machine is Windows or Linux
        if sc[self.T_OS_FAMILY] == self.WINDOWS:
            system_config = WindowsConfigurationSet(computer_name=sc[self.NAME],
                                                    admin_password=sc[self.T_USER_PASSWORD],
                                                    admin_username=sc[self.T_USER_NAME])
            system_config.domain_join = None
            system_config.win_rm = None
        else:
            system_config = LinuxConfigurationSet(host_name=sc[self.T_HOST_NAME],
                                                  user_name=sc[self.T_USER_NAME],
                                                  user_password=sc[self.T_USER_PASSWORD],
                                                  disable_ssh_password_authentication=False)
        return system_config

    def get_os_virtual_hard_disk(self):
        """
        Return None if image type is vm
        Media link should be unique
        :return:
        """
        if self.is_vm_image():
            return None
        i = self.virtual_environment[self.T_IMAGE]
        sa = self.virtual_environment[self.T_STORAGE_ACCOUNT]
        c = self.virtual_environment[self.T_CONTAINER]
        now = self.util.get_now()
        blob = self.BLOB_BASE % (i[self.NAME],
                                 str(now.year),
                                 str(now.month),
                                 str(now.day),
                                 str(now.hour),
                                 str(now.minute),
                                 str(now.second),
                                 str(current_thread().ident))
        media_link = self.MEDIA_BASE % (sa[self.SERVICE_NAME],
                                        sa[self.T_URL_BASE],
                                        c,
                                        blob)
        os_virtual_hard_disk = OSVirtualHardDisk(i[self.NAME], media_link)
        return os_virtual_hard_disk

    def get_network_config(self, service, update):
        """
        Return None if image type is vm and not update
        Public endpoint should be assigned in real time
        :param service:
        :return:
        """
        if self.is_vm_image() and not update:
            return None
        cs = self.virtual_environment[self.T_CLOUD_SERVICE]
        nc = self.virtual_environment[self.T_NETWORK_CONFIG]
        network_config = ConfigurationSet()
        network_config.configuration_set_type = nc[self.T_CONFIGURATION_SET_TYPE]
        input_endpoints = nc[self.T_INPUT_ENDPOINTS]
        # avoid duplicate endpoint under same cloud service
        assigned_endpoints = service.get_assigned_endpoints(cs[self.SERVICE_NAME])
        endpoints = map(lambda i: i[self.T_LOCAL_PORT], input_endpoints)
        unassigned_endpoints = map(str, find_unassigned_endpoints(endpoints, assigned_endpoints))
        map(lambda (i, u): i.update({self.PORT: u}), zip(input_endpoints, unassigned_endpoints))
        for input_endpoint in input_endpoints:
            network_config.input_endpoints.input_endpoints.append(
                ConfigurationSetInputEndpoint(
                    input_endpoint[self.NAME],
                    input_endpoint[self.PROTOCOL],
                    input_endpoint[self.PORT],
                    input_endpoint[self.T_LOCAL_PORT]
                )
            )
        return network_config

    def get_storage_account_name(self):
        return self.virtual_environment[self.T_STORAGE_ACCOUNT][self.NAME]

    def get_storage_account_description(self):
        return self.virtual_environment[self.T_STORAGE_ACCOUNT][self.T_DESCRIPTION]

    def get_storage_account_label(self):
        return self.virtual_environment[self.T_STORAGE_ACCOUNT][self.LABEL]

    def get_storage_account_location(self):
        return self.virtual_environment[self.T_STORAGE_ACCOUNT][self.LOCATION]

    def get_cloud_service_name(self):
        return self.virtual_environment[self.T_CLOUD_SERVICE][self.NAME]

    def get_cloud_service_label(self):
        return self.virtual_environment[self.T_CLOUD_SERVICE][self.LABEL]

    def get_cloud_service_location(self):
        return self.virtual_environment[self.T_CLOUD_SERVICE][self.LOCATION]

    def get_deployment_slot(self):
        return self.virtual_environment[self.T_DEPLOYMENT][self.T_DEPLOYMENT_SLOT]

    def get_deployment_name(self):
        return self.virtual_environment[self.T_DEPLOYMENT][self.NAME]

    def get_virtual_machine_name(self):
        return self.virtual_environment[self.T_ROLE_NAME]

    def get_virtual_machine_label(self):
        return self.virtual_environment[self.LABEL]

    def get_virtual_machine_size(self):
        return self.virtual_environment[self.T_ROLE_SIZE]

    def get_remote_provider_name(self):
        return self.virtual_environment[self.T_REMOTE][self.PROVIDER]

    def get_remote_port_name(self):
        return self.virtual_environment[self.T_REMOTE][self.T_INPUT_ENDPOINT_NAME]

    def get_remote_paras(self, name, hostname, port):
        r = self.virtual_environment[self.T_REMOTE]
        sc = self.virtual_environment[self.T_SYSTEM_CONFIG]
        remote = {
            self.NAME: name,
            self.RP_DISPLAYNAME: r[self.T_INPUT_ENDPOINT_NAME],
            self.RP_HOSTNAME: hostname,
            self.PROTOCOL: r[self.PROTOCOL],
            self.PORT: port,
            self.RP_USERNAME: sc[self.T_USER_NAME],
            self.RP_PASSWORD: sc[self.T_USER_PASSWORD]
        }
        return remote