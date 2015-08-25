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
    add_endpoint_to_network_config,
    delete_endpoint_from_network_config,
)
from hackathon.constants import (
    AZURE_RESOURCE_TYPE,
    AVMStatus,
)
from hackathon import RequiredFeature, Component


class EndpointService(Component):
    """
    Endpoint is used for dynamic management of azure endpoint on azure cloud service
    """
    TICK = 5
    LOOP = 200

    azure_adapter = RequiredFeature("azure_adapter")

    def assign_public_endpoints(self, context):
        """
        Assign public endpoints of cloud service for private endpoints of virtual machine
        Return None if failed
        :param context: contains:
                                azure_key_id
                                cloud_service_name:
                                deployment_slot:
                                virtual_machine_name:
                                private_endpoints: a list of int or str
                                public_endpoints: a list of int
        """
        self.log.debug('private_endpoints: %s' % context.private_endpoints)
        context.assigned_endpoints = self.azure_adapter.get_assigned_endpoints(context.azure_key_id,
                                                                               context.cloud_service_name)
        self.log.debug('assigned_endpoints: %s' % context.assigned_endpoints)
        if context.assigned_endpoints is None:
            return None
        return self.__generate_endpoint(context)

    def release_public_endpoints(self, context):
        """
        Release public endpoints of cloud service according to private endpoints of virtual machine
        Return False if failed
        :param context : contains
                                azure_key_id
                                cloud_service_name:
                                deployment_slot:
                                virtual_machine_name:
                                private_endpoints: a list of int or str
        :return:
        """
        self.log.debug('private_endpoints: %s' % context.private_endpoints)
        deployment_name = self.azure_adapter.get_deployment_name(context.azure_key_id,
                                                                 context.cloud_service_name,
                                                                 context.deployment_slot)
        network_config = self.azure_adapter.get_virtual_machine_network_config(context.azure_key_id,
                                                                               context.cloud_service_name,
                                                                               deployment_name,
                                                                               context.virtual_machine_name)
        new_network_config = delete_endpoint_from_network_config(network_config, context.private_endpoints)
        if new_network_config is None:
            return False
        try:
            result = self.azure_adapter.update_virtual_machine_network_config(context.azure_key_id,
                                                                              context.cloud_service_name,
                                                                              deployment_name,
                                                                              context.virtual_machine_name,
                                                                              new_network_config)
        except Exception as e:
            self.log.error(e)
            return False
        if not self.azure_adapter.wait_for_async(context.azure_key_id, result.request_id, self.TICK, self.LOOP):
            self.log.error('wait for async fail')
            return False
        if not self.azure_adapter.wait_for_virtual_machine(context.azure_key_id,
                                                           context.cloud_service_name,
                                                           deployment_name,
                                                           context.virtual_machine_name,
                                                           self.TICK,
                                                           self.LOOP,
                                                           AVMStatus.READY_ROLE):
            self.log.error('%s [%s] not ready' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, context.virtual_machine_name))
            return False
        return True


    def __generate_endpoint(self, context):
        public_endpoints = find_unassigned_endpoints(context.private_endpoints, context.assigned_endpoints)
        self.log.debug('public_endpoints: %s' % public_endpoints)
        deployment_name = self.azure_adapter.get_deployment_name(context.azure_key_id,
                                                                 context.cloud_service_name,
                                                                 context.deployment_slot)
        network_config = self.azure_adapter.get_virtual_machine_network_config(context.azure_key_id,
                                                                               context.cloud_service_name,
                                                                               deployment_name,
                                                                               context.virtual_machine_name)
        # compose new network config to update
        new_network_config = add_endpoint_to_network_config(network_config, public_endpoints,
                                                            context.private_endpoints)
        if new_network_config is None:
            return None
        try:
            result = self.azure_adapter.update_virtual_machine_network_config(context.azure_key_id,
                                                                              context.cloud_service_name,
                                                                              deployment_name,
                                                                              context.virtual_machine_name,
                                                                              new_network_config)
        except Exception as e:
            self.log.error(e)
            return None
        if not self.azure_adapter.wait_for_async(result.request_id, self.TICK, self.LOOP):
            self.log.error('wait for async fail')
            return None
        if not self.azure_adapter.wait_for_virtual_machine(context.azure_key_id,
                                                           context.cloud_service_name,
                                                           deployment_name,
                                                           context.virtual_machine_name,
                                                           self.TICK,
                                                           self.LOOP,
                                                           AVMStatus.READY_ROLE):
            self.log.error('%s [%s] not ready' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, context.virtual_machine_name))
            return None
        return public_endpoints

    def __delete_endpoint_in_azure(self, context):
        self.log.debug('private_endpoints: %s' % context.private_endpoints)
        deployment_name = self.azure_adapter.get_deployment_name(context.azure_key_id,
                                                                 context.cloud_service_name,
                                                                 context.deployment_slot)
        network_config = self.azure_adapter.get_virtual_machine_network_config(context.azure_key_id,
                                                                               context.cloud_service_name,
                                                                               deployment_name,
                                                                               context.virtual_machine_name)
        new_network_config = delete_endpoint_from_network_config(network_config, context.private_endpoints)
        if new_network_config is None:
            return False