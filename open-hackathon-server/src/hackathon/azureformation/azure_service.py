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
from hackathon.constants import (
    ADStatus,
)

from hackathon.azureformation.azure_utility_db import (
    ASYNC_TICK,
    DEPLOYMENT_TICK,
    VIRTUAL_MACHINE_TICK,
    MDL_CLS_FUNC,
    run_job,
)

from hackathon.database.models import (
    AzureKey,
)
from azure.servicemanagement import (
    ServiceManagementService,
    Deployment,
)
import time
from hackathon import Component, RequiredFeature, Context


class AzureService(Component):
    """
    Wrapper of azure service management service
    """
    scheduler = RequiredFeature("scheduler")

    IN_PROGRESS = 'InProgress'
    SUCCEEDED = 'Succeeded'
    NOT_FOUND = 'Not found (Not Found)'
    NETWORK_CONFIGURATION = 'NetworkConfiguration'

    # def __init__(self, azure_key_id):
    #     self.azure_key_id = azure_key_id
    #     azure_key = self.db.get_object(AzureKey, self.azure_key_id)
    #     super(AzureService, self).__init__(azure_key.subscription_id, azure_key.pem_url, azure_key.management_host)

    azure_service = None

    def generate_azure_service(self, azure_key_id):
        azure_key = self.db.get_object(AzureKey, azure_key_id)
        if self.azure_service is not None and self.azure_service.subscription_id == azure_key.subscription_id:
            return self.azure_service
        self.azure_service = ServiceManagementService(azure_key.subscription_id, azure_key.pem_url,
                                                      azure_key.management_host)
        return self.azure_service

    # ---------------------------------------- subscription ---------------------------------------- #

    def get_subscription(self, azure_key_id):
        return self.generate_azure_service(azure_key_id).get_subscription()

    # ---------------------------------------- storage account ---------------------------------------- #

    def storage_account_exists(self, azure_key_id, name):
        """
        Check whether specific storage account exist in specific azure subscription
        :param name:
        :return:
        """
        try:
            props = self.generate_azure_service(azure_key_id).get_storage_account_properties(name)
        except Exception as e:
            if e.message != self.NOT_FOUND:
                self.log.error(e)
            return False
        return props is not None

    def check_storage_account_name_availability(self, azure_key_id, name):
        return self.generate_azure_service(azure_key_id).check_storage_account_name_availability(name)

    def create_storage_account(self, azure_key_id, name, description, label, location):
        return self.generate_azure_service(azure_key_id).create_storage_account(name, description, label,
                                                                                location=location)

    def list_storage_accounts(self, azure_key_id):
        return self.generate_azure_service(azure_key_id).list_storage_accounts()

    # ---------------------------------------- cloud service ---------------------------------------- #
    def get_hosted_service_properties(self, azure_key_id, name, detail=False):
        return self.generate_azure_service(azure_key_id).get_hosted_service_properties(name, detail)

    def cloud_service_exists(self, azure_key_id, name, detail=False):
        """
        Check whether specific cloud service exist in specific azure subscription
        :param name:
        :return:
        """
        try:
            props = self.get_hosted_service_properties(azure_key_id, name, detail)
        except Exception as e:
            if e.message != self.NOT_FOUND:
                self.log.error(e)
            return False
        return props is not None

    def check_hosted_service_name_availability(self, azure_key_id, name):
        return self.generate_azure_service(azure_key_id).check_hosted_service_name_availability(name)

    def create_hosted_service(self, azure_key_id, name, label, location):
        return self.generate_azure_service(azure_key_id).create_hosted_service(name, label, location=location)

    # ---------------------------------------- deployment ---------------------------------------- #

    def get_deployment_by_slot(self, azure_key_id, cloud_service_name, deployment_slot):
        return self.generate_azure_service(azure_key_id).get_deployment_by_slot(cloud_service_name, deployment_slot)

    def get_deployment_by_name(self, azure_key_id, cloud_service_name, deployment_name):
        return self.generate_azure_service(azure_key_id).get_deployment_by_name(cloud_service_name, deployment_name)

    def deployment_exists(self, azure_key_id, cloud_service_name, deployment_slot):
        try:
            props = self.get_deployment_by_slot(azure_key_id, cloud_service_name, deployment_slot)
        except Exception as e:
            if e.message != self.NOT_FOUND:
                self.log.error(e)
            return False
        return props is not None

    def get_deployment_name(self, azure_key_id, cloud_service_name, deployment_slot):
        try:
            props = self.get_deployment_by_slot(azure_key_id, cloud_service_name, deployment_slot)
        except Exception as e:
            self.log.error(e)
            return None
        return None if props is None else props.name

    def wait_for_deployment(self, azure_key_id, cloud_service_name, deployment_name, second_per_loop, loop,
                            status=ADStatus.RUNNING):
        count = 0
        props = self.get_deployment_by_name(azure_key_id, cloud_service_name, deployment_name)
        if props is None:
            return False
        while props.status != status:
            self.log.debug('wait for deployment [%s] loop count: %d' % (deployment_name, count))
            count += 1
            if count > loop:
                self.log.error('Timed out waiting for deployment status.')
                return False
            time.sleep(second_per_loop)
            props = self.get_deployment_by_name(azure_key_id, cloud_service_name, deployment_name)
            if props is None:
                return False
        return props.status == status

    def get_deployment_dns(self, azure_key_id, cloud_service_name, deployment_slot):
        try:
            props = self.get_deployment_by_slot(azure_key_id, cloud_service_name, deployment_slot)
        except Exception as e:
            self.log.error(e)
            return None
        return None if props is None else props.url

    # ---------------------------------------- virtual machine ---------------------------------------- #

    def create_virtual_machine_deployment(self,
                                          azure_key_id,
                                          cloud_service_name,
                                          deployment_name,
                                          deployment_slot,
                                          virtual_machine_label,
                                          virtual_machine_name,
                                          system_config,
                                          os_virtual_hard_disk,
                                          network_config,
                                          virtual_machine_size,
                                          vm_image_name):
        return self.generate_azure_service(azure_key_id).create_virtual_machine_deployment(cloud_service_name,
                                                                                           deployment_name,
                                                                                           deployment_slot,
                                                                                           virtual_machine_label,
                                                                                           virtual_machine_name,
                                                                                           system_config,
                                                                                           os_virtual_hard_disk,
                                                                                           network_config=network_config,
                                                                                           role_size=virtual_machine_size,
                                                                                           vm_image_name=vm_image_name)

    def get_virtual_machine_instance_status(self, deployment, virtual_machine_name):
        if deployment is not None and isinstance(deployment, Deployment):
            for role_instance in deployment.role_instance_list:
                if role_instance.instance_name == virtual_machine_name:
                    return role_instance.instance_status
        return None

    def wait_for_virtual_machine(self,
                                 azure_key_id,
                                 cloud_service_name,
                                 deployment_name,
                                 virtual_machine_name,
                                 second_per_loop,
                                 loop,
                                 status):
        count = 0
        props = self.get_deployment_by_name(azure_key_id, cloud_service_name, deployment_name)
        while self.get_virtual_machine_instance_status(props, virtual_machine_name) != status:
            self.log.debug('wait for virtual machine [%s] loop count: %d' % (virtual_machine_name, count))
            count += 1
            if count > loop:
                self.log.error('Timed out waiting for role instance status.')
                return False
            time.sleep(second_per_loop)
            props = self.get_deployment_by_name(azure_key_id, cloud_service_name, deployment_name)
        return self.get_virtual_machine_instance_status(props, virtual_machine_name) == status

    def update_virtual_machine_network_config(self,
                                              azure_key_id,
                                              cloud_service_name,
                                              deployment_name,
                                              virtual_machine_name,
                                              network_config):
        return self.generate_azure_service(azure_key_id).update_role(cloud_service_name,
                                                                     deployment_name,
                                                                     virtual_machine_name,
                                                                     network_config=network_config)

    def get_virtual_machine_public_endpoint(self,
                                            azure_key_id,
                                            cloud_service_name,
                                            deployment_name,
                                            virtual_machine_name,
                                            endpoint_name):
        deployment = self.get_deployment_by_name(azure_key_id, cloud_service_name, deployment_name)
        for role in deployment.role_instance_list:
            if role.role_name == virtual_machine_name:
                if role.instance_endpoints is not None:
                    for instance_endpoint in role.instance_endpoints:
                        if instance_endpoint.name == endpoint_name:
                            return instance_endpoint.public_port
        return None

    def get_virtual_machine_public_ip(self, azure_key_id, cloud_service_name, deployment_name, virtual_machine_name):
        deployment = self.get_deployment_by_name(azure_key_id, cloud_service_name, deployment_name)
        for role in deployment.role_instance_list:
            if role.role_name == virtual_machine_name:
                if role.instance_endpoints is not None:
                    return role.instance_endpoints.instance_endpoints[0].vip
        return None

    def get_virtual_machine_private_ip(self, azure_key_id, cloud_service_name, deployment_name, virtual_machine_name):
        deployment = self.get_deployment_by_name(azure_key_id, cloud_service_name, deployment_name)
        for role in deployment.role_instance_list:
            if role.role_name == virtual_machine_name:
                return role.ip_address
        return None

    def get_virtual_machine(self, azure_key_id, cloud_service_name, deployment_name, role_name):
        return self.generate_azure_service(azure_key_id).get_role(cloud_service_name, deployment_name, role_name)

    def virtual_machine_exists(self, azure_key_id, cloud_service_name, deployment_name, virtual_machine_name):
        try:
            props = self.get_virtual_machine(azure_key_id, cloud_service_name, deployment_name, virtual_machine_name)
        except Exception as e:
            if e.message != self.NOT_FOUND:
                self.log.error(e)
            return False
        return props is not None

    def add_virtual_machine(self,
                            azure_key_id,
                            cloud_service_name,
                            deployment_name,
                            virtual_machine_name,
                            system_config,
                            os_virtual_hard_disk,
                            network_config,
                            virtual_machine_size,
                            vm_image_name):
        return self.generate_azure_service(azure_key_id).add_role(cloud_service_name,
                                                                  deployment_name,
                                                                  virtual_machine_name,
                                                                  system_config,
                                                                  os_virtual_hard_disk,
                                                                  network_config=network_config,
                                                                  role_size=virtual_machine_size,
                                                                  vm_image_name=vm_image_name)

    def get_virtual_machine_network_config(self, azure_key_id, cloud_service_name, deployment_name,
                                           virtual_machine_name):
        try:
            virtual_machine = self.get_virtual_machine(azure_key_id, cloud_service_name, deployment_name,
                                                       virtual_machine_name)
        except Exception as e:
            self.log.error(e)
            return None
        if virtual_machine is not None:
            for configuration_set in virtual_machine.configuration_sets.configuration_sets:
                if configuration_set.configuration_set_type == self.NETWORK_CONFIGURATION:
                    return configuration_set
        return None

    def stop_virtual_machine(self, azure_key_id, cloud_service_name, deployment_name, virtual_machine_name, type):
        return self.generate_azure_service(azure_key_id).shutdown_role(cloud_service_name, deployment_name,
                                                                       virtual_machine_name, type)

    def start_virtual_machine(self, azure_key_id, cloud_service_name, deployment_name, virtual_machine_name):
        return self.generate_azure_service(azure_key_id).start_role(cloud_service_name, deployment_name,
                                                                    virtual_machine_name)

    # ---------------------------------------- endpoint ---------------------------------------- #

    def get_assigned_endpoints(self, azure_key_id, cloud_service_name):
        """
        Return a list of assigned endpoints of given cloud service
        :param cloud_service_name:
        :return: endpoints: a list of int
        """
        properties = self.get_hosted_service_properties(azure_key_id, cloud_service_name, True)
        endpoints = []
        for deployment in properties.deployments.deployments:
            for role in deployment.role_list.roles:
                for configuration_set in role.configuration_sets.configuration_sets:
                    if configuration_set.configuration_set_type == self.NETWORK_CONFIGURATION:
                        if configuration_set.input_endpoints is not None:
                            for input_endpoint in configuration_set.input_endpoints.input_endpoints:
                                endpoints.append(input_endpoint.port)
        return map(int, endpoints)

    # ---------------------------------------- other ---------------------------------------- #

    def get_operation_status(self, azure_key_id, request_id):
        return self.generate_azure_service(azure_key_id).get_operation_status(request_id)

    def wait_for_async(self, azure_key_id, request_id, second_per_loop, loop):
        """
        Wait for async operation, up to second_per_loop * loop
        :param request_id:
        :return:
        """
        count = 0
        result = self.get_operation_status(azure_key_id, request_id)
        while result.status == self.IN_PROGRESS:
            self.log.debug('wait for async [%s] loop count [%d]' % (request_id, count))
            count += 1
            if count > loop:
                self.log.error('Timed out waiting for async operation to complete.')
                return False
            time.sleep(second_per_loop)
            result = self.get_operation_status(azure_key_id, request_id)
        if result.status != self.SUCCEEDED:
            self.log.error(vars(result))
            if result.error:
                self.log.error(result.error.code)
                self.log.error(vars(result.error))
            self.log.error('Asynchronous operation did not succeed.')
            return False
        return True

    def ping(self, azure_key_id):
        """
        Use list storage accounts to check azure service management service health
        :return:
        """
        try:
            self.generate_azure_service(azure_key_id).list_storage_accounts()
        except Exception as e:
            self.log.error(e)
            return False
        return True

    # ---------------------------------------- call ---------------------------------------- #

    def query_async_operation_status(self, request_id, azure_key_id, feature, true_method, false_method,
                                     method_args_context):
        self.log.debug('query async operation status: request_id [%s]' % request_id)
        result = self.get_operation_status(azure_key_id, request_id)
        if result.status == self.IN_PROGRESS:
            query_context = Context(
                request_id=request_id,
                azure_key_id=azure_key_id,
                feature=feature,
                true_method=true_method,
                false_method=false_method,
                method_args_context=method_args_context
            )
            self.scheduler.add_once(feature='azure_service',
                                    method='query_async_operation_status',
                                    context=query_context,
                                    seconds=ASYNC_TICK)
        elif result.status == self.SUCCEEDED:
            self.scheduler.add_once(feature=feature, method=true_method, context=method_args_context)
        else:
            self.scheduler.add_once(feature=feature, method=false_method, context=method_args_context)

    def query_deployment_status(self,
                                azure_key_id,
                                cloud_service_name,
                                deployment_name,
                                true_mdl_cls_func,
                                true_cls_args,
                                true_func_args):
        self.log.debug('query deployment status: deployment_name [%s]' % deployment_name)
        result = self.get_deployment_by_name(azure_key_id, cloud_service_name, deployment_name)
        if result.status == ADStatus.RUNNING:
            run_job(true_mdl_cls_func, true_cls_args, true_func_args)
        else:
            # query deployment status
            run_job(MDL_CLS_FUNC[15],
                    (azure_key_id,),
                    (cloud_service_name, deployment_name,
                     true_mdl_cls_func, true_cls_args, true_func_args),
                    DEPLOYMENT_TICK)

    def query_virtual_machine_status(self,
                                     azure_key_id,
                                     cloud_service_name,
                                     deployment_name,
                                     virtual_machine_name,
                                     status,
                                     true_mdl_cls_func,
                                     true_cls_args,
                                     true_func_args):
        self.log.debug('query virtual machine status: virtual_machine_name [%s]' % virtual_machine_name)
        deployment = self.get_deployment_by_name(azure_key_id, cloud_service_name, deployment_name)
        result = self.get_virtual_machine_instance_status(deployment, virtual_machine_name)
        if result == status:
            run_job(true_mdl_cls_func, true_cls_args, true_func_args)
        else:
            # query virtual machine status
            run_job(MDL_CLS_FUNC[8],
                    (azure_key_id,),
                    (cloud_service_name, deployment_name, virtual_machine_name, status,
                     true_mdl_cls_func, true_cls_args, true_func_args),
                    VIRTUAL_MACHINE_TICK)
