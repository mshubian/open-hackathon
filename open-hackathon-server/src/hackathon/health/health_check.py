# -*- coding: utf-8 -*-
#
# -----------------------------------------------------------------------------------
# Copyright (c) Microsoft Open Technologies (Shanghai) Co. Ltd.  All rights reserved.
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# -----------------------------------------------------------------------------------

import sys

sys.path.append("..")
import requests
import abc

from sqlalchemy import __version__

from hackathon.constants import HEALTH_STATUS
from hackathon import RequiredFeature, Component
from hackathon.database.models import User, AzureKey
from hackathon.azureformation.azure_adapter import AzureAdapter

__all__ = [
    "MySQLHealthCheck",
    "HostedDockerHealthCheck",
    "AlaudaDockerHealthCheck",
    "GuacamoleHealthCheck",
    "StorageHealthCheck"
]

STATUS = "status"
DESCRIPTION = "description"
VERSION = "version"


class HealthCheck(Component):
    """Base class for health check item"""
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def report_health(self):
        pass


class MySQLHealthCheck(HealthCheck):
    """Check health status of MySQL database

    Make sure MySQL is working and correctly configured by a single DB query
    """

    def report_health(self):
        """Report status of MySQL by query the count of User table

        Will return OK if no exception raised else return ERROR
        """
        try:
            self.db.count(User)
            return {
                STATUS: HEALTH_STATUS.OK,
                VERSION: __version__
            }
        except Exception as e:
            return {
                STATUS: HEALTH_STATUS.ERROR,
                VERSION: __version__,
                DESCRIPTION: e.message
            }


class HostedDockerHealthCheck(HealthCheck):
    """Report status of hostdd docker

    see more on docker/hosted_docker.py
    """

    def __init__(self):
        self.hosted_docker = RequiredFeature("hosted_docker")
        self.alauda_docker = RequiredFeature("alauda_docker")

    def report_health(self):
        return self.hosted_docker.report_health()


class AlaudaDockerHealthCheck(HealthCheck):
    """Report status of Alauda service

    see more on docker/alauda_docker.py
    """

    def __init__(self):
        self.alauda_docker = RequiredFeature("alauda_docker")

    def report_health(self):
        return self.alauda_docker.report_health()


class GuacamoleHealthCheck(HealthCheck):
    """Check the status of Guacamole Server by request its homepage"""

    def __init__(self):
        self.guacamole_url = self.util.get_config("guacamole.host") + '/guacamole'

    def report_health(self):
        try:
            req = requests.get(self.guacamole_url)
            self.log.debug(req.status_code)
            if req.status_code == 200:
                return {
                    STATUS: HEALTH_STATUS.OK
                }
        except Exception as e:
            self.log.error(e)
        return {
            STATUS: HEALTH_STATUS.ERROR
        }


class AzureHealthCheck(HealthCheck):
    """Check the status of azure to make sure config is right and azure is available"""

    def report_health(self):
        azure_key = self.db.find_first_object(AzureKey)
<<<<<<< HEAD
        azure = AzureAdapter(azure_key.id)
=======
        if not azure_key:
            return {
                STATUS: HEALTH_STATUS.WARNING,
                DESCRIPTION: "No Azure key found"
            }
        azure = Service(azure_key.id)
>>>>>>> msopentech/master
        if azure.ping():
            return {
                STATUS: HEALTH_STATUS.OK
            }
        else:
            return {
                STATUS: HEALTH_STATUS.ERROR
            }

class StorageHealthCheck(HealthCheck):
    """Check the status of storage"""

    def report_health(self):
        self.storage.report_health()

    def __init__(self):
        self.storage = RequiredFeature("storage")

