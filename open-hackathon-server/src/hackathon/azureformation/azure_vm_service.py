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
    AZURE_FORMATION,
    VIRTUAL_MACHINE_TICK,
    commit_azure_log,
    commit_azure_deployment,
    commit_azure_virtual_machine,
    commit_azure_endpoint,
    commit_virtual_environment,
    contain_azure_deployment,
    contain_azure_virtual_machine,
    delete_azure_deployment,
    delete_azure_virtual_machine,
    get_azure_virtual_machine_status,
    update_azure_virtual_machine_status,
    update_azure_virtual_machine_public_ip,
    update_azure_virtual_machine_private_ip,
    update_virtual_environment_status,
    update_virtual_environment_remote_paras,

)
from hackathon.constants import (
    AZURE_RESOURCE_TYPE,
    ALOperation,
    ALStatus,
    ADStatus,
    AVMStatus,
    VE_PROVIDER,
    VERemoteProvider,
    VEStatus,
)
import json
from werkzeug.exceptions import InternalServerError, BadRequest
from hackathon import Context, RequiredFeature, Component


# todo take care of resource check
# todo support batch operations
class AzureVMService(Component):
    scheduler = RequiredFeature("scheduler")
    azure_adapter = RequiredFeature("azure_adapter")
    subscription = RequiredFeature("azure_subscription_service")

    SIZE_CORE_MAP = {
        'a0': 1,
        'basic_a0': 1,
        'a1': 1,
        'basic_a1': 1,
        'a2': 2,
        'basic_a2': 2,
        'a3': 4,
        'basic_a3': 4,
        'a4': 8,
        'basic_a4': 8,
        'extra small': 1,
        'small': 1,
        'medium': 2,
        'large': 4,
        'extra large': 8,
        'a5': 2,
        'a6': 4,
        'a7': 8,
        'a8': 8,
        'a9': 16,
        'standard_d1': 1,
        'standard_d2': 2,
        'standard_d3': 4,
        'standard_d4': 8,
        'standard_d11': 2,
        'standard_d12': 4,
        'standard_d13': 8,
        'standard_d14': 16,
        'standard_ds1': 1,
        'standard_ds2': 2,
        'standard_ds3': 4,
        'standard_ds4': 8,
        'standard_ds11': 2,
        'standard_ds12': 4,
        'standard_ds13': 8,
        'standard_ds14': 16,
        'standard_g1': 2,
        'standard_g2': 4,
        'standard_g3': 8,
        'standard_g4': 16,
        'standard_g5': 32,
    }

    # def __init__(self, azure_key_id):
    #     super(AzureVMService, self).__init__(azure_key_id)

    # --------------------------------------------- create vm functions ---------------------------------------------#

    def create_virtual_machine(self, context):
        """create a vm in azure

        :type : context | Context
        :param: context contains azure_key_id, experiment_id, template_unit

        0. Prerequisites: a. storage account and cloud service exist in both azure and database;
                          b. input parameters are correct;
        1. If deployment not exist in azure subscription, then create virtual machine with deployment
           Else reuse deployment in azure subscription
        2. If virtual machine not exist in azure subscription, then add virtual machine to deployment
           Else reuse virtual machine in azure subscription
        :return:
        """
        self.log.debug("create a new vm")
        context = self.__generate_create_vm_context(context)

        self.__check_available_cores(context)

        # avoid duplicate deployment in azure subscription
        if self.azure_adapter.deployment_exists(context.azure_key_id,
                                                context.cloud_service_name,
                                                context.deployment_slot):
            # use deployment name from azure subscription
            deployment_name = self.azure_adapter.get_deployment_name(context.azure_key_id,
                                                                     context.cloud_service_name,
                                                                     context.deployment_slot)
            self.__check_deployment_in_db(context)

            # avoid duplicate virtual machine in azure subscription
            if self.azure_adapter.virtual_machine_exists(context.azure_key_id,
                                                         context.cloud_service_name,
                                                         deployment_name,
                                                         context.virtual_machine_name):
                self.__check_vm_exist_in_db(context)
            else:
                # delete old azure virtual machine, cascade delete old azure endpoint
                delete_azure_virtual_machine(context.cloud_service_name, deployment_name, context.virtual_machine_name)
                self.__azure_service_create_vm(deployment_name, context)
        else:
            # delete old azure deployment, cascade delete old azure virtual machine and azure endpoint
            delete_azure_deployment(context.cloud_service_name, context.deployment_slot)
            # use deployment name from template
            context.deployment_name = context.template_unit.get_deployment_name()
            context.virtual_machine_label = context.template_unit.get_virtual_machine_label()
            self.__azure_service_create_vm_with_deployment(context)

        return True

    def create_virtual_machine_async_true_1(self, azure_key_id, experiment_id, template_unit):
        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()
        # query virtual machine status
        args_context = Context(
            azure_key_id=azure_key_id,
            cloud_service_name=cloud_service_name,
            deployment_name=self.azure_adapter.get_deployment_name(azure_key_id,
                                                                   cloud_service_name,
                                                                   deployment_slot),
            virtual_machine_name='%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id),
            status=AVMStatus.READY_ROLE,
            feature='azure_vm_service',
            true_method='create_virtual_machine_vm_true_1',
            method_args_context=self.__generate_base_context(azure_key_id, experiment_id, template_unit)
        )
        self.scheduler.add_once(feature='azure_service',
                                method='query_virtual_machine_status',
                                context=args_context,
                                seconds=3)

    def create_virtual_machine_async_true_2(self, azure_key_id, experiment_id, template_unit):
        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()
        # query virtual machine status
        args_context = Context(
            cloud_service_name=cloud_service_name,
            deployment_name=self.azure_adapter.get_deployment_name(cloud_service_name, deployment_slot),
            virtual_machine_name='%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id),
            status=AVMStatus.READY_ROLE,
            feature='azure_vm_service',
            true_method='create_virtual_machine_vm_true_2',
            method_args_context=self.__generate_base_context(azure_key_id, experiment_id, template_unit)
        )
        self.scheduler.add_once(feature='azure_service',
                                method='query_virtual_machine_status',
                                context=args_context,
                                seconds=3)

    def create_virtual_machine_async_true_3(self, azure_key_id, experiment_id, template_unit):
        args_context = Context(
            azure_key_id=azure_key_id,
            cloud_service_name=template_unit.get_cloud_service_name(),
            deployment_name=template_unit.get_deployment_name(),
            feature='azure_vm_service',
            true_method='create_virtual_machine_dm_true',
            method_args_context=self.__generate_base_context(azure_key_id, experiment_id, template_unit)
        )
        self.scheduler.add_once(feature='azure_service',
                                method='query_deployment_status',
                                context=args_context,
                                seconds=3)

    def create_virtual_machine_async_false_1(self, experiment_id, template_unit):
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id)
        m = '%s [%s] wait for async fail' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name)
        commit_azure_log(experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.FAIL, m, 2)
        self.log.error(m)

    def create_virtual_machine_async_false_2(self, experiment_id, template_unit):
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id)
        m = '%s [%s] wait for async fail (update network config)' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE,
                                                                     virtual_machine_name)
        commit_azure_log(experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.FAIL, m, 3)
        self.log.error(m)

    def create_virtual_machine_async_false_3(self, experiment_id, template_unit):
        deployment_slot = template_unit.get_deployment_slot()
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id)
        m = '%s [%s] wait for async fail' % (AZURE_RESOURCE_TYPE.DEPLOYMENT, deployment_slot)
        commit_azure_log(experiment_id, ALOperation.CREATE_DEPLOYMENT, ALStatus.FAIL, m, 2)
        self.log.error(m)
        m = '%s [%s] wait for async fail' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name)
        commit_azure_log(experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.FAIL, m, 2)
        self.log.error(m)

    def create_virtual_machine_vm_true_1(self, azure_key_id, experiment_id, template_unit):
        # check updating network_config operation
        if template_unit.is_vm_image():
            cloud_service_name = template_unit.get_cloud_service_name()
            deployment_slot = template_unit.get_deployment_slot()
            deployment_name = self.azure_adapter.get_deployment_name(cloud_service_name, deployment_slot)
            virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id)
            network_config = template_unit.get_network_config(self.azure_adapter, True)
            result = self.azure_adapter.update_virtual_machine_network_config(cloud_service_name,
                                                                              deployment_name,
                                                                              virtual_machine_name,
                                                                              network_config)
            query_context = Context(
                request_id=result.id,
                azure_key_id=azure_key_id,
                feature='azure_vm_service',
                true_method='create_virtual_machine_async_true_2',
                false_method='create_virtual_machine_async_false_2',
                method_args_context=self.__generate_base_context(azure_key_id, experiment_id, template_unit)
            )
            self.scheduler.add_once(feature='azure_service',
                                    method='query_async_operation_status',
                                    context=query_context,
                                    seconds=3)
        else:
            self.__create_virtual_machine_helper(azure_key_id, experiment_id, template_unit)

    def create_virtual_machine_vm_true_2(self, azure_key_id, experiment_id, template_unit):
        self.__create_virtual_machine_helper(azure_key_id, experiment_id, template_unit)

    def create_virtual_machine_dm_true(self, azure_key_id, experiment_id, template_unit):
        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()
        deployment_name = template_unit.get_deployment_name()
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id)
        m = '%s [%s] created' % (AZURE_RESOURCE_TYPE.DEPLOYMENT, deployment_slot)
        commit_azure_deployment(deployment_name,
                                deployment_slot,
                                ADStatus.RUNNING,
                                cloud_service_name,
                                experiment_id)
        commit_azure_log(experiment_id, ALOperation.CREATE_DEPLOYMENT, ALStatus.END, m, 0)
        self.log.debug(m)
        # query virtual machine status
        args_context = Context(
            cloud_service_name=cloud_service_name,
            deployment_name=deployment_name,
            virtual_machine_name=virtual_machine_name,
            status=AVMStatus.READY_ROLE,
            feature='azure_vm_service',
            true_method='create_virtual_machine_async_true_2',
            method_args_context=self.__generate_base_context(azure_key_id, experiment_id, template_unit)
        )
        self.scheduler.add_once(feature='azure_service',
                                method='query_virtual_machine_status',
                                context=args_context,
                                seconds=3)

    # --------------------------------------------- stop vm functions ---------------------------------------------#

    def stop_virtual_machine(self, azure_key_id, experiment_id, template_unit, action):
        """
        0. Prerequisites: a. virtual machine exist in both azure and database
                          b. input parameters are correct
        :param experiment_id:
        :param template_unit:
        :param action: AVMStatus.STOPPED or AVMStatus.STOPPED_DEALLOCATED
        :return:
        """
        commit_azure_log(experiment_id, ALOperation.STOP_VIRTUAL_MACHINE, ALStatus.START)
        # need_status: AVMStatus.STOPPED_VM or AVMStatus.STOPPED_DEALLOCATED
        need_status = AVMStatus.STOPPED_VM if action == AVMStatus.STOPPED else AVMStatus.STOPPED_DEALLOCATED
        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()
        deployment_name = self.azure_adapter.get_deployment_name(cloud_service_name, deployment_slot)
        deployment = self.azure_adapter.get_deployment_by_name(cloud_service_name, deployment_name)
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(),
                                          experiment_id)
        now_status = self.azure_adapter.get_virtual_machine_instance_status(deployment, virtual_machine_name)
        if need_status == AVMStatus.STOPPED_VM and now_status == AVMStatus.STOPPED_DEALLOCATED:
            m = '%s [%s] need status %s but now status %s' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE,
                                                              virtual_machine_name,
                                                              AVMStatus.STOPPED_VM,
                                                              AVMStatus.STOPPED_DEALLOCATED)
            commit_azure_log(experiment_id, ALOperation.STOP_VIRTUAL_MACHINE, ALStatus.FAIL, m, 1)
            self.log.error(m)
            return False
        elif need_status == now_status:
            db_status = get_azure_virtual_machine_status(cloud_service_name, deployment_name, virtual_machine_name)
            if db_status == need_status:
                m = '%s [%s] %s and by %s before' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE,
                                                     virtual_machine_name,
                                                     need_status,
                                                     AZURE_FORMATION)
                commit_azure_log(experiment_id, ALOperation.STOP_VIRTUAL_MACHINE, ALStatus.END, m, 1)
            else:
                m = '%s [%s] %s but not by %s before' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE,
                                                         virtual_machine_name,
                                                         need_status,
                                                         AZURE_FORMATION)
                self.__stop_virtual_machine_helper(experiment_id, template_unit, need_status)
                commit_azure_log(experiment_id, ALOperation.STOP_VIRTUAL_MACHINE, ALStatus.END, m, 2)
            self.log.debug(m)
        else:
            try:
                result = self.azure_adapter.stop_virtual_machine(cloud_service_name,
                                                                 deployment_name,
                                                                 virtual_machine_name,
                                                                 action)
            except Exception as e:
                m = '%s [%s] %s' % (
                    AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name, e.message)
                commit_azure_log(experiment_id, ALOperation.STOP_VIRTUAL_MACHINE, ALStatus.FAIL, 0)
                self.log.error(m)
                self.log.error(e)
                return False
            # query async operation status
            method_args_context = self.__generate_base_context(azure_key_id, experiment_id, template_unit)
            method_args_context.need_status = need_status
            query_context = Context(
                request_id=result.id,
                azure_key_id=azure_key_id,
                feature='azure_vm_service',
                true_method='stop_virtual_machine_async_true',
                false_method='stop_virtual_machine_async_false',
                method_args_context=method_args_context
            )
            self.scheduler.add_once(feature='azure_service',
                                    method='query_async_operation_status',
                                    context=query_context,
                                    seconds=3)
        return True

    def stop_virtual_machine_async_true(self, azure_key_id, experiment_id, template_unit, need_status):
        method_args_context = self.__generate_base_context(azure_key_id, experiment_id, template_unit)
        method_args_context.need_status = need_status

        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()
        query_context = Context(
            cloud_service_name=cloud_service_name,
            deployment_slot=deployment_slot,
            deployment_name=self.azure_adapter.get_deployment_name(azure_key_id, cloud_service_name, deployment_slot),
            virtual_machine_name='%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id),
            status=need_status,
            feature='azure_vm_service',
            true_method='stop_virtual_machine_vm_true',
            method_args_context=method_args_context,
        )
        self.scheduler.add_once(feature='azure_service',
                                method='query_virtual_machine_status',
                                context=query_context,
                                seconds=VIRTUAL_MACHINE_TICK)

    def stop_virtual_machine_async_false(self, azure_key_id, experiment_id, template_unit, need_status):
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id)
        m = '%s [%s] %s wait for async fail' % (
            AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name, need_status)
        commit_azure_log(experiment_id, ALOperation.STOP_VIRTUAL_MACHINE, ALStatus.FAIL, 2)
        self.log.error(m)

    def stop_virtual_machine_vm_true(self, azure_key_id, experiment_id, template_unit, need_status):
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(),experiment_id)
        self.__stop_virtual_machine_helper(experiment_id, template_unit, need_status)
        m = '%s [%s] %s' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name, need_status)
        commit_azure_log(experiment_id, ALOperation.STOP_VIRTUAL_MACHINE, ALStatus.END, m, 0)
        self.log.debug(m)

    # --------------------------------------------- start vm functions ---------------------------------------------#

    def start_virtual_machine(self, azure_key_id, experiment_id, template_unit):
        """
        0. Prerequisites: a. virtual machine exist in both azure and database
                          b. input parameters are correct
        :param experiment_id:
        :param template_unit:
        :return:
        """
        commit_azure_log(experiment_id, ALOperation.START_VIRTUAL_MACHINE, ALStatus.START)
        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()
        deployment_name = self.azure_adapter.get_deployment_name(cloud_service_name, deployment_slot)
        deployment = self.azure_adapter.get_deployment_by_name(cloud_service_name, deployment_name)
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(),experiment_id)
        status = self.azure_adapter.get_virtual_machine_instance_status(deployment, virtual_machine_name)
        if status == AVMStatus.READY_ROLE:
            db_status = get_azure_virtual_machine_status(cloud_service_name, deployment_name, virtual_machine_name)
            if db_status == status:
                m = '%s [%s] started by %s before' % (
                    AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name, AZURE_FORMATION)
                commit_azure_log(experiment_id, ALOperation.START_VIRTUAL_MACHINE, ALStatus.END, m, 1)
            else:
                m = '%s [%s] started but not by %s before' % (
                    AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name, AZURE_FORMATION)
                self.__start_virtual_machine_helper(experiment_id, template_unit)
                commit_azure_log(experiment_id, ALOperation.START_VIRTUAL_MACHINE, ALStatus.END, m, 2)
            self.log.debug(m)
        else:
            try:
                result = self.azure_adapter.start_virtual_machine(cloud_service_name,
                                                                  deployment_name,
                                                                  virtual_machine_name)
            except Exception as e:
                m = '%s [%s] %s' % (
                    AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name, e.message)
                commit_azure_log(experiment_id, ALOperation.START_VIRTUAL_MACHINE, ALStatus.FAIL, 0)
                self.log.error(e)
                return False

            # query async operation status
            query_context = Context(
                request_id=result.id,
                azure_key_id=azure_key_id,
                feature='azure_vm_service',
                true_method='start_virtual_machine_async_true',
                false_method='start_virtual_machine_async_false',
                method_args_context=self.__generate_base_context(azure_key_id, experiment_id, template_unit)
            )
            self.scheduler.add_once(feature='azure_service',
                                    method='query_async_operation_status',
                                    context=query_context,
                                    seconds=3)
        return True

    def start_virtual_machine_async_true(self, azure_key_id, experiment_id, template_unit):
        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()

        query_context = Context(
            cloud_service_name=cloud_service_name,
            deployment_slot=deployment_slot,
            deployment_name=self.azure_adapter.get_deployment_name(azure_key_id, cloud_service_name, deployment_slot),
            virtual_machine_name='%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id),
            status=AVMStatus.READY_ROLE,
            feature='azure_vm_service',
            true_method='start_virtual_machine_vm_true',
            method_args_context=self.__generate_base_context(azure_key_id, experiment_id, template_unit)
        )
        self.scheduler.add_once(feature='azure_service',
                                method='query_virtual_machine_status',
                                context=query_context,
                                seconds=VIRTUAL_MACHINE_TICK)

    def start_virtual_machine_async_false(self, azure_key_id, experiment_id, template_unit):
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(),experiment_id)
        m = '%s [%s] wait for async fail' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name)
        commit_azure_log(experiment_id, ALOperation.START_VIRTUAL_MACHINE, ALStatus.FAIL, 1)
        self.log.error(m)

    def start_virtual_machine_vm_true(self, azure_key_id, experiment_id, template_unit):
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(),experiment_id)
        self.__start_virtual_machine_helper(experiment_id, template_unit)
        m = '%s [%s] started' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name)
        commit_azure_log(experiment_id, ALOperation.START_VIRTUAL_MACHINE, ALStatus.END, m, 0)
        self.log.debug(m)

    # todo delete virtual machine
    def delete_virtual_machine(self):
        raise NotImplementedError

    # --------------------------------------------- helper function ---------------------------------------------#

    def __create_virtual_machine_helper(self, azure_key_id, experiment_id, template_unit):
        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()
        deployment_name = self.azure_adapter.get_deployment_name(azure_key_id, cloud_service_name, deployment_slot)
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(), experiment_id)
        public_ip = self.azure_adapter.get_virtual_machine_public_ip(azure_key_id,
                                                                     cloud_service_name,
                                                                     deployment_name,
                                                                     virtual_machine_name)
        remote_port_name = template_unit.get_remote_port_name()
        remote_port = self.azure_adapter.get_virtual_machine_public_endpoint(azure_key_id,
                                                                             cloud_service_name,
                                                                             deployment_name,
                                                                             virtual_machine_name,
                                                                             remote_port_name)
        remote_paras = template_unit.get_remote_paras(virtual_machine_name,
                                                      public_ip,
                                                      remote_port)
        virtual_environment = commit_virtual_environment(VE_PROVIDER.AZURE,
                                                         virtual_machine_name,
                                                         template_unit.get_image_name(),
                                                         VEStatus.RUNNING,
                                                         VERemoteProvider.Guacamole,
                                                         json.dumps(remote_paras),
                                                         experiment_id)
        dns = self.azure_adapter.get_deployment_dns(azure_key_id, cloud_service_name, deployment_slot)
        private_ip = self.azure_adapter.get_virtual_machine_private_ip(azure_key_id,
                                                                       cloud_service_name,
                                                                       deployment_name,
                                                                       virtual_machine_name)
        virtual_machine_label = template_unit.get_virtual_machine_label()
        virtual_machine = commit_azure_virtual_machine(virtual_machine_name,
                                                       virtual_machine_label,
                                                       AVMStatus.READY_ROLE,
                                                       dns,
                                                       public_ip,
                                                       private_ip,
                                                       cloud_service_name,
                                                       deployment_name,
                                                       experiment_id,
                                                       virtual_environment)
        network_config = self.azure_adapter.get_virtual_machine_network_config(azure_key_id,
                                                                               cloud_service_name,
                                                                               deployment_name,
                                                                               virtual_machine_name)
        for input_endpoint in network_config.input_endpoints.input_endpoints:
            commit_azure_endpoint(input_endpoint.name,
                                  input_endpoint.protocol,
                                  input_endpoint.port,
                                  input_endpoint.local_port,
                                  virtual_machine)
        m = '%s [%s] created' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, virtual_machine_name)
        commit_azure_log(experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.END, m, 0)
        self.log.debug(m)

    def __stop_virtual_machine_helper(self, experiment_id, template_unit, need_status):
        """
        Update status of azure virtual machine and virtual environment
        :param experiment_id:
        :param template_unit:
        :param need_status:
        :return:
        """
        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()
        deployment_name = self.azure_adapter.get_deployment_name(cloud_service_name, deployment_slot)
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(),
                                          experiment_id)
        virtual_machine = update_azure_virtual_machine_status(cloud_service_name,
                                                              deployment_name,
                                                              virtual_machine_name,
                                                              need_status)
        update_virtual_environment_status(virtual_machine, VEStatus.STOPPED)

    def __start_virtual_machine_helper(self, experiment_id, template_unit):
        """
        Update status of azure virtual machine and virtual environment
        Update private ip of azure virtual machine
        :param experiment_id:
        :param template_unit:
        :return:
        """
        cloud_service_name = template_unit.get_cloud_service_name()
        deployment_slot = template_unit.get_deployment_slot()
        deployment_name = self.azure_adapter.get_deployment_name(cloud_service_name, deployment_slot)
        virtual_machine_name = '%s-%d' % (template_unit.get_virtual_machine_name(),
                                          experiment_id)
        virtual_machine = update_azure_virtual_machine_status(cloud_service_name,
                                                              deployment_name,
                                                              virtual_machine_name,
                                                              AVMStatus.READY_ROLE)
        public_ip = self.azure_adapter.get_virtual_machine_public_ip(cloud_service_name,
                                                                     deployment_name,
                                                                     virtual_machine_name)
        update_azure_virtual_machine_public_ip(virtual_machine, public_ip)
        private_ip = self.azure_adapter.get_virtual_machine_private_ip(cloud_service_name,
                                                                       deployment_name,
                                                                       virtual_machine_name)
        update_azure_virtual_machine_private_ip(virtual_machine, private_ip)
        update_virtual_environment_status(virtual_machine, VEStatus.RUNNING)
        remote_port_name = template_unit.get_remote_port_name()
        remote_port = self.azure_adapter.get_virtual_machine_public_endpoint(cloud_service_name,
                                                                             deployment_name,
                                                                             virtual_machine_name,
                                                                             remote_port_name)
        remote_paras = template_unit.get_remote_paras(virtual_machine_name,
                                                      public_ip,
                                                      remote_port)
        update_virtual_environment_remote_paras(virtual_machine, json.dumps(remote_paras))

    # ----------------------------------------------refactor usage ----------------------------------------------#

    def __generate_base_context(self, azure_key_id, experiment_id, template_unit):
        return Context(
            azure_key_id=azure_key_id,
            experiment_id=experiment_id,
            template_unit=template_unit
        )

    def __generate_create_vm_context(self, context):
        context.deployment_slot = context.template_unit.get_deployment_slot()
        context.virtual_machine_name = '%s-%d' % (
        context.template_unit.get_virtual_machine_name(), context.experiment_id)
        context.virtual_machine_size = context.template_unit.get_virtual_machine_size()
        context.cloud_service_name = context.template_unit.get_cloud_service_name()
        context.vm_image_name = context.template_unit.get_vm_image_name()
        context.system_config = context.template_unit.get_system_config()
        context.os_virtual_hard_disk = context.template_unit.get_os_virtual_hard_disk()
        context.network_config = context.template_unit.get_network_config(context.azure_key_id, False)
        return context

    def __check_available_cores(self, context):
        if self.subscription.get_available_core_count(context.azure_key_id) < self.SIZE_CORE_MAP[context.virtual_machine_size.lower()]:
            m = '%s [%s] subscription not enough' % (AZURE_RESOURCE_TYPE.DEPLOYMENT, context.deployment_slot)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_DEPLOYMENT, ALStatus.FAIL, m, 1)
            self.log.error(m)
            m = '%s [%s] subscription not enough' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, context.virtual_machine_name)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.FAIL, m, 1)
            self.log.error(m)
            raise BadRequest("available cores is not enough")

    def __check_deployment_in_db(self, context):
        # use deployment name from azure subscription
        if contain_azure_deployment(context.cloud_service_name, context.deployment_slot):
            m = '%s [%s] exist and created by %s before' % (AZURE_RESOURCE_TYPE.DEPLOYMENT,
                                                            context.deployment_name,
                                                            AZURE_FORMATION)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_DEPLOYMENT, ALStatus.END, m, 1)
        else:
            m = '%s [%s] exist but not created by %s before' % (AZURE_RESOURCE_TYPE.DEPLOYMENT,
                                                                context.deployment_name,
                                                                AZURE_FORMATION)
            commit_azure_deployment(context.deployment_name,
                                    context.deployment_slot,
                                    ADStatus.RUNNING,
                                    context.cloud_service_name,
                                    context.experiment_id)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_DEPLOYMENT, ALStatus.END, m, 2)
        self.log.debug(m)

    def __check_vm_exist_in_db(self, context):
        if contain_azure_virtual_machine(context.cloud_service_name, context.deployment_name,
                                         context.virtual_machine_name):
            m = '%s [%s] exist and created by %s before' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE,
                                                            context.virtual_machine_name,
                                                            AZURE_FORMATION)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.END, m, 1)
            self.log.debug(m)
        else:
            m = '%s [%s] exist but not created by %s before' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE,
                                                                context.virtual_machine_name,
                                                                AZURE_FORMATION)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.FAIL, m, 4)
            self.log.error(m)
            raise BadRequest("VM already exist")

    def __azure_service_create_vm(self, deployment_name, context):
        commit_azure_log(context.experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.START)
        try:
            result = self.azure_adapter.add_virtual_machine(context.cloud_service_name,
                                                            deployment_name,
                                                            context.virtual_machine_name,
                                                            context.system_config,
                                                            context.os_virtual_hard_disk,
                                                            context.network_config,
                                                            context.virtual_machine_size,
                                                            context.vm_image_name)
        except Exception as e:
            m = '%s [%s] %s' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, context.virtual_machine_name, e.message)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.FAIL, m, 0)
            self.log.error(e)
            raise InternalServerError("Azure service create vm failed")
        # query async operation status
        query_context = Context(
            request_id=result.id,
            azure_key_id=context.azure_key_id,
            feature='azure_vm_service',
            true_method='create_virtual_machine_async_true_1',
            false_method='create_virtual_machine_async_false_1',
            method_args_context=self.__generate_base_context(context.azure_key_id, context.experiment_id,
                                                             context.template_unit)
        )
        self.scheduler.add_once(feature='azure_service',
                                method='query_async_operation_status',
                                context=query_context,
                                seconds=3)

    def __azure_service_create_vm_with_deployment(self, context):
        commit_azure_log(context.experiment_id, ALOperation.CREATE_DEPLOYMENT, ALStatus.START)
        commit_azure_log(context.experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.START)
        try:
            result = self.azure_adapter.create_virtual_machine_deployment(context.cloud_service_name,
                                                                          context.deployment_name,
                                                                          context.deployment_slot,
                                                                          context.virtual_machine_label,
                                                                          context.virtual_machine_name,
                                                                          context.system_config,
                                                                          context.os_virtual_hard_disk,
                                                                          context.network_config,
                                                                          context.virtual_machine_size,
                                                                          context.vm_image_name)
        except Exception as e:
            m = '%s [%s] %s' % (AZURE_RESOURCE_TYPE.DEPLOYMENT, context.deployment_slot, e.message)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_DEPLOYMENT, ALStatus.FAIL, m, 0)
            m = '%s [%s] %s' % (AZURE_RESOURCE_TYPE.VIRTUAL_MACHINE, context.virtual_machine_name, e.message)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_VIRTUAL_MACHINE, ALStatus.FAIL, m, 0)
            self.log.error(e)
            raise InternalServerError("Azure create vm with deployment failed")

        # query async operation status
        query_context = Context(
            request_id=result.id,
            azure_key_id=context.azure_key_id,
            feature='azure_vm_service',
            true_method='create_virtual_machine_async_true_3',
            false_method='create_virtual_machine_async_false_3',
            method_args_context=self.__generate_base_context(context.azure_key_id, context.experiment_id,
                                                             context.template_unit)
        )
        self.scheduler.add_once(feature='service',
                                method='query_async_operation_status',
                                context=query_context,
                                seconds=3)
