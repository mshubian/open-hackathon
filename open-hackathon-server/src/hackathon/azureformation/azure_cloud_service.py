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
    commit_azure_log,
    commit_azure_cloud_service,
    contain_azure_cloud_service,
    delete_azure_cloud_service
)

from hackathon.constants import (
    AZURE_RESOURCE_TYPE,
    ALOperation,
    ALStatus,
    ACSStatus,
)

from hackathon import RequiredFeature, Component, Context
from werkzeug.exceptions import InternalServerError, BadRequest


class CloudService(Component):
    """
    Cloud service is used as DNS for azure virtual machines
    """
    scheduler = RequiredFeature("scheduler")
    azure_adapter = RequiredFeature("azure_adapter")
    subscription = RequiredFeature("azure_subscription_service")

    def create_cloud_service(self, context):
        """
        :type
        :param : context: azure_key_id, experiment_id, template_unit
        
        If cloud service not exist in azure subscription, then create it
        Else reuse cloud service in azure subscription
        :return:
        """
        args_context = self.__generate_create_cloud_service_context(context)

        if self.azure_adapter.cloud_service_exists(context.azure_key_id, args_context.name):
            self.__check_cloud_service_in_db(args_context)
        else:
            self.__check_creation_requirement(args_context)
            # delete old azure cloud service in database, cascade delete old azure deployment,
            # old azure virtual machine and old azure end point
            delete_azure_cloud_service(args_context.name)
            self.__create_cloud_service(args_context)
            # make sure cloud service is created
            self.__check_exist_after_creation(args_context)

        # create virtual machine
        self.scheduler.add_once(feature='azure_vm_service',
                                method='create_virtual_machine',
                                context=context,
                                seconds=3)
        return True

    # todo update cloud service
    def update_cloud_service(self):
        raise NotImplementedError

    # todo delete cloud service
    def delete_cloud_service(self):
        raise NotImplementedError

        # ---------------------------------------- helper functions---------------------------------------- #

    def __generate_create_cloud_service_context(self, context):
        return Context(
            azure_key_id=context.azure_key_id,
            experiment_id=context.experiment_id,
            name=context.template_unit.get_cloud_service_name(),
            label=context.template_unit.get_cloud_service_label(),
            location=context.template_unit.get_cloud_service_location()
        )

    def __check_creation_requirement(self, context):
        # avoid name already taken by other azure subscription
        if not self.azure_adapter.check_hosted_service_name_availability(context.azure_key_id, context.name).result:
            m = '%s [%s] name not available' % (AZURE_RESOURCE_TYPE.CLOUD_SERVICE, context.name)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_CLOUD_SERVICE, ALStatus.FAIL, m, 1)
            self.log.error(m)
            raise BadRequest("cloud service name not available")
        # avoid no available subscription remained
        if self.subscription.get_available_cloud_service_count(context.azure_key_id) < 1:
            m = '%s [%s] subscription not enough' % (AZURE_RESOURCE_TYPE.CLOUD_SERVICE, context.name)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_CLOUD_SERVICE, ALStatus.FAIL, m, 2)
            self.log.error(m)
            raise BadRequest("cloud service subscription not enough")
        delete_azure_cloud_service(context.name)

    def __create_cloud_service(self, context):
        try:
            commit_azure_log(context.experiment_id, ALOperation.CREATE_CLOUD_SERVICE, ALStatus.START)
            self.azure_adapter.create_hosted_service(azure_key_id=context.azure_key_id,
                                                     name=context.name,
                                                     label=context.label,
                                                     location=context.location)
        except Exception as e:
            m = '%s [%s] %s' % (AZURE_RESOURCE_TYPE.CLOUD_SERVICE, context.name, e.message)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_CLOUD_SERVICE, ALStatus.FAIL, m, 0)
            self.log.error(e)
            raise InternalServerError("azure service raised a exception when create cloud service")

    def __check_exist_after_creation(self, context):
        if not self.azure_adapter.cloud_service_exists(context.azure_key_id, context.name):
            m = '%s [%s] created but not exist' % (AZURE_RESOURCE_TYPE.CLOUD_SERVICE, context.name)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_CLOUD_SERVICE, ALStatus.FAIL, m, 3)
            self.log.error(m)
            return False
        else:
            m = '%s [%s] created' % (AZURE_RESOURCE_TYPE.CLOUD_SERVICE, context.name)
            commit_azure_cloud_service(context.name,
                                       context.label,
                                       context.location,
                                       ACSStatus.CREATED,
                                       context.experiment_id)
            commit_azure_log(context.experiment_id,
                             ALOperation.CREATE_CLOUD_SERVICE,
                             ALStatus.END, m, 0)
            self.log.debug(m)

    def __check_cloud_service_in_db(self, context):
        # check whether cloud service created by azure formation before
        if contain_azure_cloud_service(context.name):
            m = '%s [%s] exist and created by %s before' % (AZURE_RESOURCE_TYPE.CLOUD_SERVICE,
                                                            context.name,
                                                            AZURE_FORMATION)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_CLOUD_SERVICE, ALStatus.END, m, 1)
        else:
            m = '%s [%s] exist but not created by %s before' % (
            AZURE_RESOURCE_TYPE.CLOUD_SERVICE, context.name, AZURE_FORMATION)
            commit_azure_cloud_service(context.name, context.label,
                                       context.location,
                                       ACSStatus.CREATED,
                                       context.experiment_id)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_CLOUD_SERVICE, ALStatus.END, m, 2)
        self.log.debug(m)
