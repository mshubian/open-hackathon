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
    commit_azure_storage_account,
    contain_azure_storage_account,
    delete_azure_storage_account,
)

from hackathon.constants import (
    AZURE_RESOURCE_TYPE,
    ALOperation,
    ALStatus,
    ASAStatus,
)

from hackathon import Component, RequiredFeature, Context
from werkzeug.exceptions import InternalServerError, BadRequest


class StorageAccount(Component):
    """
    Storage account is used by azure virtual machines to store their disks
    """
    scheduler = RequiredFeature("scheduler")
    azure_adapter = RequiredFeature("azure_adapter")
    subscription = RequiredFeature("azure_subscription_service")

    def create_storage_account(self, context):
        """
        :param context : azure_key_id, experiment_id, template_unit

        If storage account not exist in azure subscription, then create it
        Else reuse storage account in azure subscription
        :return:
        """
        args_context = self.__generate_create_storage_account_context(context)

        # avoid duplicate storage account in azure subscription
        if not self.azure_adapter.storage_account_exists(context.azure_key_id, args_context.name):
            self.__check_creation_requirement(args_context)
            # delete old azure storage account in database
            delete_azure_storage_account(args_context.name)
            self.__create_storage_account_in_azure_service(context, args_context)
        else:
            self.__check_storage_account_in_db(args_context)
            # create cloud service
            self.scheduler.add_once(feature='azure_cloud_service',
                                    method='create_cloud_service',
                                    context=context,
                                    seconds=3)
        return True

    def create_storage_account_async_true(self, context):
        name = context.template_unit.get_storage_account_name()
        description = context.template_unit.get_storage_account_description()
        label = context.template_unit.get_storage_account_label()
        location = context.template_unit.get_storage_account_location()
        # make sure storage account exist
        if not self.azure_adapter.storage_account_exists(context.azure_key_id, name):
            m = '%s [%s] created but not exist' % (AZURE_RESOURCE_TYPE.STORAGE_ACCOUNT, name)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_STORAGE_ACCOUNT, ALStatus.FAIL, m, 4)
            self.log.error(m)
        else:
            m = '%s [%s] created' % (AZURE_RESOURCE_TYPE.STORAGE_ACCOUNT, name)
            commit_azure_storage_account(name, description, label, location, ASAStatus.ONLINE, context.experiment_id)
            commit_azure_log(context.experiment_id, ALOperation.CREATE_STORAGE_ACCOUNT, ALStatus.END, m, 0)
            self.log.debug(m)
            # create cloud service
            self.scheduler.add_once(feature='azure_cloud_service',
                                    method='create_cloud_service',
                                    context=context,
                                    seconds=3)

    def create_storage_account_async_false(self, experiment_id, template_unit):
        name = template_unit.get_storage_account_name()
        m = '%s [%s] wait for async fail' % (AZURE_RESOURCE_TYPE.STORAGE_ACCOUNT, name)
        commit_azure_log(experiment_id, ALOperation.CREATE_STORAGE_ACCOUNT, ALStatus.FAIL, m, 3)
        self.log.error(m)

    # todo update storage account
    def update_storage_account(self):
        raise NotImplementedError

    # todo delete storage account
    def delete_storage_account(self):
        raise NotImplementedError

    # ---------------------------------------- helper functions---------------------------------------- #

    def __generate_create_storage_account_context(self, context):
        context.name = context.template_unit.get_storage_account_name()
        context.description = context.template_unit.get_storage_account_description()
        context.label = context.template_unit.get_storage_account_label()
        context.location = context.template_unit.get_storage_account_location()
        return context

    def __check_creation_requirement(self, args_context):
        # avoid name already taken by other azure subscription
        if not self.azure_adapter.check_storage_account_name_availability(args_context.azure_key_id,
                                                                          args_context.name).result:
            m = '%s [%s] name not available' % (AZURE_RESOURCE_TYPE.STORAGE_ACCOUNT, args_context.name)
            commit_azure_log(args_context.experiment_id, ALOperation.CREATE_STORAGE_ACCOUNT, ALStatus.FAIL, m, 1)
            self.log.error(m)
            raise BadRequest("storage account name not available")
        # avoid no available subscription remained
        if self.subscription.get_available_storage_account_count(args_context.azure_key_id) < 1:
            m = '%s [%s] subscription not enough' % (AZURE_RESOURCE_TYPE.STORAGE_ACCOUNT, args_context.name)
            commit_azure_log(args_context.experiment_id, ALOperation.CREATE_STORAGE_ACCOUNT, ALStatus.FAIL, m, 2)
            self.log.error(m)
            raise BadRequest("storage account subscription not enough")

    def __create_storage_account_in_azure_service(self, context, args_context):
        try:
            commit_azure_log(args_context.experiment_id, ALOperation.CREATE_STORAGE_ACCOUNT, ALStatus.START)
            result = self.azure_adapter.create_storage_account(args_context.azure_key_id,
                                                               args_context.name,
                                                               args_context.description,
                                                               args_context.label,
                                                               args_context.location)
        except Exception as e:
            m = '%s [%s] %s' % (AZURE_RESOURCE_TYPE.STORAGE_ACCOUNT, args_context.name, e.message)
            commit_azure_log(args_context.experiment_id, ALOperation.CREATE_STORAGE_ACCOUNT, ALStatus.FAIL, m, 0)
            self.log.error(e)
            raise InternalServerError("azure service raised a exception when create storage account")
        # query async operation status
        query_context = Context(
            request_id=result.id,
            azure_key_id=context.azure_key_id,
            feature='azure_storage_account_service',
            true_method='create_storage_account_async_true',
            false_method='create_storage_account_async_false',
            method_args_context=context
        )
        self.scheduler.add_once(feature='azure_adapter',
                                method='query_async_operation_status',
                                context=query_context,
                                seconds=3)

    def __check_storage_account_in_db(self, args_context):
        # check whether storage account created by azure formation before
        if contain_azure_storage_account(args_context.name):
            m = '%s [%s] exist and created by %s before' % (AZURE_RESOURCE_TYPE.STORAGE_ACCOUNT,
                                                            args_context.name,
                                                            AZURE_FORMATION)
            commit_azure_log(args_context.experiment_id, ALOperation.CREATE_STORAGE_ACCOUNT, ALStatus.END, m, 1)
        else:
            m = '%s [%s] exist but not created by %s before' % (AZURE_RESOURCE_TYPE.STORAGE_ACCOUNT,
                                                                args_context.name,
                                                                AZURE_FORMATION)
            commit_azure_storage_account(args_context.name,
                                         args_context.description,
                                         args_context.label,
                                         args_context.location,
                                         ASAStatus.ONLINE,
                                         args_context.experiment_id)
            commit_azure_log(args_context.experiment_id, ALOperation.CREATE_STORAGE_ACCOUNT, ALStatus.END, m, 2)
        self.log.debug(m)
