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

import sys

sys.path.append("..")

import abc

from hackathon import Component

__all__ = ["HostServer"]


class HostServer(Component):
    """Base for host server"""

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def create_new_vm(self, context):
        """create a new vm host

        :type context: Context
        :param context: the execution context of VM host creating

        :rtype context
        :return the context which should including the whole host server info
        """

        return

    @abc.abstractmethod
    def start(self, context):
        """start the host vm

        :type context: Context
        :param context: the execution context of vm starting

        :rtype bool
        :return True if successfully started else False
        """
        return

    @abc.abstractmethod
    def stop(self, context):
        """stop the host vm

        :type context: Context
        :param context: the execution context of vm stopping

        :rtype bool
        :return True if successfully stop else False
        """
        return

    @abc.abstractmethod
    def restart(self, context):
        """restart the host vm

        :type context: Context
        :param context: the execution context of vm restarting

        :rtype context
        :return True if successfully restarted else False
        """
        return

    @abc.abstractmethod
    def delete(self, context):
        """delete the host vm

        :type context: Context
        :param context: the execution context of vm deleting

        :rtype bool
        :return True if successfully deleted else False
        """
        return

    @abc.abstractmethod
    def report_health(self, context):
        """report health status of the VM including all required components

        :type context: Context
        :param context: the execution context of vm deleting

        :rtype bool
        :return the context which should including every required component like 'docker'

        """
        return
