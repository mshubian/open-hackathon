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
import uuid

sys.path.append("..")
from hackathon.database.models import Template, DockerHostServer
from hackathon.hackathon_response import bad_request, not_found, internal_server_error, ok
from datetime import timedelta
import time
from hackathon.enum import TEMPLATE_STATUS
from hackathon.template.docker_template_unit import DockerTemplateUnit
from hackathon.template.docker_template import DockerTemplate
from hackathon.template.base_template import BaseTemplate
from hackathon.scheduler import scheduler
from hackathon import Component, RequiredFeature, g
import requests


class TemplateManager(Component):
    hackathon_manager = RequiredFeature("hackathon_manager")
    file_service = RequiredFeature("file_service")

    def get_template_list(self, hackathon_name):
        hackathon = self.hackathon_manager.get_hackathon_by_name(hackathon_name)
        if hackathon is None:
            return not_found('hackathon not found')
        hack_id = hackathon.id
        templates = self.db.find_all_objects_by(Template, hackathon_id=hack_id)
        return map(lambda u: u.dic(), templates)


    def get_template_by_id(self, id):
        return self.db.find_first_object(Template, Template.id == id)


    def validate_created_args(self, args):
        if "name" not in args:
            return False, bad_request("template name invalid")

        template = self.db.find_first_object(Template, Template.name == args['name'])
        if template is not None:
            return False, bad_request("template aready exist")

        return True, "pass"


    def save_args_to_file(self, args):
        try:
            docker_template_units = [DockerTemplateUnit(ve) for ve in args[BaseTemplate.VIRTUAL_ENVIRONMENTS]]
            docker_template = DockerTemplate(args[BaseTemplate.EXPR_NAME], docker_template_units)
            file_path = docker_template.to_file()
            self.log.debug("save template as file :" + file_path)
            return file_path
        except Exception as ex:
            self.log.error(ex)
            return None


    def upload_template_to_azure(self, path):
        template_container = self.util.safe_get_config("storage.template_container", "templates")

        try:
            real_name = g.hackathon.name + "/" + str(uuid.uuid1())[0:9] + time.strftime("%Y%m%d%H%M%S") + ".js"
            return self.file_service.upload_file_to_azure_from_path(path, template_container, real_name)
        except Exception as ex:
            self.log.error(ex)
            return None


    def create_template(self, args):
        # create template step one : args validate
        status, return_info = self.validate_created_args(args)
        if not status:
            return return_info

        # create template step two : parse args and trans to file
        local_path = self.save_args_to_file(args)
        if local_path is None:
            return internal_server_error("save template as local file failed")

        # create template step Three : upload template file to Azure
        url = self.upload_template_to_azure(local_path)
        if url is None:
            return internal_server_error("upload template file failed")

        # create template step Four : insert into DB
        try:
            self.log.debug("create template: %r" % args)
            args['url'] = url
            args['creator_id'] = g.user.id
            args['update_time'] = self.util.get_now()
            args['hackathon_id'] = g.hackathon.id
            args['status'] = TEMPLATE_STATUS.ONLINE
            return self.db.add_object_kwargs(Template, **args)
        except Exception as ex:
            self.log.error(ex)
            return internal_server_error("insert record into template DB failed")


    def update_template(self, args):
        if "name" not in args:
            return bad_request("template name invalid")
        template = self.db.find_first_object(Template, Template.name == args['name'])

        if template is None:
            return bad_request("template doesn't exist")
        try:
            self.log.debug("update template: %r" % args)
            args['update_time'] = self.util.get_now()
            update_items = dict(dict(args).viewitems() - template.dic().viewitems())
            self.log.debug("update a exist hackathon :" + str(args))
            self.db.update_object(template, **update_items)
            return ok("update template success")
        except Exception as ex:
            self.log.error(ex)
            return internal_server_error("update template failed :" + ex.message)


    def delete_template(self, id):
        self.log.debug("delete or disable a exist template")
        try:
            template = self.get_template_by_id(id)
            args = {}
            args['status'] = TEMPLATE_STATUS.OFFLINE
            args['update_time'] = self.util.get_now()
            self.db.update_object(template, args)
            return ok("delete or disable template success")
        except Exception as ex:
            self.log.error(ex)
            return internal_server_error("disable or delete failed")


    def pull_images(self, image_name):
        hosts = self.db.find_all_objects(DockerHostServer, DockerHostServer.hackathon_id == g.hackathon.id)
        docker_host_api = map(lambda x: x.public_docker_api_port, hosts)
        for api in docker_host_api:
            url = api + "/images/create?fromImage=" + image_name
            exec_time = self.util.get_now() + timedelta(seconds=2)
            self.log.debug(" send request to pull image:" + url)
            # use requests.post instead of post_to_remote, because req.contect can not be json.loads()
            scheduler.add_job(requests.post, 'date', run_date=exec_time, args=[url])


            # template_manager.create_template({
            # "expr_name": "test",
            # "virtual_environments": [
            # {}, {}
            # ]
            # })