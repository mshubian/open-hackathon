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

import os
import sys
import uuid
import json
from werkzeug.exceptions import BadRequest, InternalServerError, Forbidden

sys.path.append("..")

from compiler.ast import (
    flatten,
)
from hackathon.database.models import (
    Template,
    DockerHostServer,
    HackathonTemplateRel,
    Experiment
)
from hackathon.hackathon_response import (
    not_found,
    internal_server_error,
    ok,
    forbidden
)
from hackathon.constants import (
    TEMPLATE_STATUS,
    VE_PROVIDER,
    FILE_TYPE,
)
from hackathon.template.docker_template_unit import (
    DockerTemplateUnit,
)
from hackathon.template.docker_template import (
    DockerTemplate,
)
from hackathon.template.base_template import (
    BaseTemplate,
)

from hackathon import (
    Component,
    RequiredFeature,
    Context
)
from flask import g, request
from sqlalchemy import (
    and_
)


class TemplateManager(Component):
    hackathon_manager = RequiredFeature("hackathon_manager")
    file_service = RequiredFeature("file_service")
    docker = RequiredFeature("docker")
    scheduler = RequiredFeature("scheduler")
    user_manager = RequiredFeature("user_manager")
    team_manager = RequiredFeature("team_manager")
    storage = RequiredFeature("storage")

    templates = {}  # template in memory {template.id: template_file_dic}

    def get_template_by_id(self, id):
        return self.db.find_first_object(Template, id=id)

    def get_template_by_name(self, template_name):
        return self.db.find_first_object_by(Template, name=template_name)

    def get_templates_by_hackathon_id(self, hackathon_id):
        htrs = self.db.find_all_objects_by(HackathonTemplateRel, hackathon_id=hackathon_id)
        return map(lambda x: x.template, htrs)

    def get_template_list(self, **kwargs):
        condition = self.__get_filter_condition(**kwargs)
        return self.db.find_all_objects(Template, condition)

    def get_user_templates(self, user, hackathon):
        template_list = self.__get_templates_by_user(user, hackathon)
        settings = []
        for template in template_list:
            template_units = []
            for ve in template['data'][BaseTemplate.VIRTUAL_ENVIRONMENTS]:
                template_units.append({
                    'name': ve[DockerTemplateUnit.NAME],
                    'type': ve[DockerTemplateUnit.TYPE] if DockerTemplateUnit.TYPE in ve else "",
                    'description': ve[DockerTemplateUnit.DESCRIPTION] if DockerTemplateUnit.DESCRIPTION in ve else "",
                })
            settings.append({
                'name': template['data'][BaseTemplate.TEMPLATE_NAME],
                'description': template['data'][BaseTemplate.DESCRIPTION] if BaseTemplate.DESCRIPTION in template[
                    'data'] else "",
                'units': template_units,
            })
        return settings

    def create_template(self, args):
        """ create template

        The whole logic contains 3 main steps:
        1 : args validate
        2 : parse args and save to storage
        3 : save to database

        :type args: dict
        :param args: description of the template that you want to create

        :return:
        """
        self.__check_create_args(args)
        context = self.__save_template_to_storage(args)
        if not context:
            return internal_server_error("save tempplate failed")
        self.log.debug("create template: %r" % args)
        self.__save_template_to_database(args, context)
        return ok("create template success")

    def create_template_by_file(self):
        """create a template by a whole template file

        The whole logic contains 4 main steps:
        1 : get template dic from PostRequest
        2 : args validate
        3 : parse args and save to storage
        4 : save to database

        :return:

        """
        template = self.__get_template_from_request()
        self.__check_create_args(template)
        context = self.__save_template_to_storage(template)
        if not context:
            return internal_server_error("save template failed")
        self.__save_template_to_database(template, context)
        return ok("create template success")

    def update_template(self, args):
        """update a exist template

        The whole logic contains 3 main steps:
        1 : args validate for update operation
        2 : parse args and save to storage
        3 : save to database

        :type args: dict
        :param args: description of the template that you want to create

        :return:
        """
        self.__check_update_args(args)
        context = self.__save_template_to_storage(args)
        if not context:
            return internal_server_error("save tempplate failed")
        self.__save_template_to_database(args, context)
        return ok("update template success")

    def delete_template(self, id):
        self.log.debug("delete template [%d]" % id)
        try:
            template = self.db.get_object(Template, id)
            if template is None:
                return ok("already removed")
            # user can only delete the template which created by himself except super admin
            if g.user.id != template.creator_id and not self.user_manager.is_super_admin(g.user):
                return forbidden()
            if len(self.db.find_all_objects_by(Experiment, template_id=id)) > 0:
                return forbidden("template already in use")

            # remove template cache , localfile, azurefile
            self.templates.pop(template.id, '')
            if os.path.exists(template.local_path):
                os.remove(template.local_path)
            container_name = self.util.safe_get_config("storage.template_container", "templates")
            blob_name = template.url.split("/")[-1]
            self.file_service.delete_file_from_azure(container_name, blob_name)

            # remove record in DB
            self.db.delete_all_objects_by(HackathonTemplateRel, template_id=template.id)
            self.db.delete_object(template)

            return ok("delete template success")
        except Exception as ex:
            self.log.error(ex)
            return internal_server_error("delete template failed")

    def load_template(self, template):
        """
        load template priority : from memory > from local file > from from azure
        :param template:
        :return:
        """
        template_id = template.id
        dic_from_memory = self.__load_template_from_memory(template_id)
        if dic_from_memory is not None:
            return dic_from_memory

        local_url = template.local_path
        dic_from_local = self.__load_template_from_local_file(template_id, local_url)
        if dic_from_local is not None:
            return dic_from_local

        remote_url = template.url
        dic_from_azure = self.__load_template_from_azure(template_id, local_url, remote_url)
        if dic_from_azure is not None:
            return dic_from_azure

        return None

    def pull_images_for_hackathon(self, context):
        hackathon_id = context.hackathon_id
        # get templates which is online and provided by docker
        templates = self.__get_templates_for_pull(hackathon_id)
        # get expected images on hackathons' templates
        images = map(lambda x: self.__get_images_from_template(x), templates)
        expected_images = flatten(images)
        self.log.debug('expected images: %s on hackathon: %s' % (expected_images, hackathon_id))
        # get all docker host server on hackathon
        hosts = self.db.find_all_objects_by(DockerHostServer, hackathon_id=hackathon_id)
        # loop to get every docker host
        for docker_host in hosts:
            download_images = self.__get_undownloaded_images_on_docker_host(docker_host, expected_images)
            self.log.debug('need to pull images: %s on host: %s' % (download_images, docker_host.vm_name))
            for dl_image in download_images:
                image = dl_image.split(':')[0]
                tag = dl_image.split(':')[1]
                context = Context(image=image,
                                  tag=tag,
                                  docker_host=docker_host)
                self.scheduler.add_once(feature="hosted_docker",
                                        method="pull_image",
                                        context=context,
                                        seconds=3)

    def add_template_to_hackathon(self, template_id, team_id=-1):
        template = self.db.find_first_object_by(Template, id=template_id)
        if template is None:
            return not_found("template does not exist")
        htr = self.db.find_first_object_by(HackathonTemplateRel,
                                           template_id=template.id,
                                           hackathon_id=g.hackathon.id,
                                           team_id=team_id)
        if htr is not None:
            return ok("already exist")
        try:
            self.db.add_object_kwargs(HackathonTemplateRel,
                                      hackathon_id=g.hackathon.id,
                                      template_id=template.id,
                                      team_id=team_id,
                                      update_time=self.util.get_now())
            return ok()
        except Exception as ex:
            self.log.error(ex)
            return internal_server_error("add a hackathon template rel record faild")

    def delete_template_from_hackathon(self, template_id, team_id=-1):
        htr = self.db.delete_all_objects_by(HackathonTemplateRel,
                                            template_id=template_id,
                                            hackathon_id=g.hackathon.id,
                                            team_id=team_id)
        #self.db.delete_object(htr)
        return ok()

    # ---------------------------------------- helper functions ---------------------------------------- #

    def __check_create_args(self, args):
        """ validate args when creating a template

        :type args: dict
        :param args: description for a template that you want to create

        :return: if validate passed return nothing else raised a BadRequest exception

        """
        if BaseTemplate.TEMPLATE_NAME not in args:
            raise BadRequest(description="template args: name invalid")
        if BaseTemplate.DESCRIPTION not in args:
            raise BadRequest(description="template args: description invalid")
        if BaseTemplate.VIRTUAL_ENVIRONMENTS_PROVIDER not in args:
            raise BadRequest(description="template args: provider invalid")
        if BaseTemplate.VIRTUAL_ENVIRONMENTS not in args:
            raise BadRequest(description="template args: virtual_environments invalid")

    def __check_update_args(self, args):
        """ validate args when updating a template

        :type args: dict
        :param args: description for a template that you want to update

        :return: if validate passed return nothing else raised a BadRequest or Forbidden exceptions

        """
        self.__check_create_args(args)
        template = self.db.find_first_object_by(Template, name=args[BaseTemplate.TEMPLATE_NAME])
        if template is None:
            raise BadRequest("template does not exist")
        # user can only modify the template which created by himself except super admin
        if g.user.id != template.creator_id and not self.user_manager.is_super_admin(g.user):
            raise Forbidden()

    def __save_template_to_storage(self, args):
        """save template to a file in storage which is chosen by configuration

        Parse out template from args and merge with default template value
        Then generate a file name, and save it to a physical file in storage

        :type args: dict
        :param args: description of template

        :return: context if no exception raised
        """
        try:
            docker_template_units = [DockerTemplateUnit(ve) for ve in args[BaseTemplate.VIRTUAL_ENVIRONMENTS]]
            docker_template = DockerTemplate(args[BaseTemplate.TEMPLATE_NAME],
                                             args[BaseTemplate.DESCRIPTION],
                                             docker_template_units)
            file_name = '%s-%s-%s.js' % (g.user.name, args[BaseTemplate.TEMPLATE_NAME], str(uuid.uuid1())[0:8])
            context = Context(
                file_name=file_name,
                file_type=FILE_TYPE.TEMPLATE,
                content=docker_template.dic
            )
            self.log.debug("save=ing template as file [%s]" % file_name)
            context = self.storage.save(context)
            return context
        except Exception as ex:
            self.log.error(ex)
            return None

    def __save_template_to_database(self, args, context):
        """save template date to db

        According to the args , find out whether it is ought to insert or update a record

        :type args : dict
        :param args: description of template that you want to insert to DB

        :type context: Context
        :param context: the context that return from self.__save_template_to_storage

        :return: if raised exception return InternalServerError else return nothing

        """
        template = self.db.find_first_object_by(Template, name=args[BaseTemplate.TEMPLATE_NAME])
        try:
            # insert record
            if template is None:
                self.log.debug("create template: %r" % args)
                provider = self.__get_provider_from_template_dic(args)
                self.db.add_object_kwargs(Template,
                                          name=args[BaseTemplate.TEMPLATE_NAME],
                                          url=context.url,
                                          local_path=context.physical_path,
                                          provider=provider,
                                          creator_id=g.user.id,
                                          status=TEMPLATE_STATUS.UNCHECKED,
                                          create_time=self.util.get_now(),
                                          update_time=self.util.get_now(),
                                          description=args[BaseTemplate.DESCRIPTION],
                                          virtual_environment_count=len(args[BaseTemplate.VIRTUAL_ENVIRONMENTS]))
            else:
                # update record
                self.db.update_object(template,
                                      url=context.url,
                                      local_path=context.physical_path,
                                      update_time=self.util.get_now(),
                                      description=args[BaseTemplate.DESCRIPTION],
                                      virtual_environment_count=len(args[BaseTemplate.VIRTUAL_ENVIRONMENTS]))
        except Exception as ex:
            self.log.error(ex)
            raise InternalServerError(description="insert or update record in db failed")

    def __upload_template_to_azure(self, path, file_name):
        try:
            template_container = self.util.safe_get_config("storage.template_container", "templates")
            return self.file_service.upload_file_to_azure_from_path(path, template_container, file_name)
        except Exception as ex:
            self.log.error(ex)
            return None

    def __load_template_from_memory(self, template_id):
        """
        get template_dic from memory
        :param template_id:
        :return:
        """
        if template_id is None or template_id not in self.templates:
            return None
        else:
            return self.templates[template_id]

    def __load_template_from_local_file(self, template_id, local_url):
        """
        get template_dic from local file
        :param template_id:
        :param local_url:
        :return:
        """
        if local_url is None or not os.path.exists(local_url):
            return None
        else:
            template_dic = json.load(file(local_url))
            self.templates[template_id] = template_dic
            return template_dic

    def __load_template_from_azure(self, template_id, local_url, remote_url):
        """
        get template_dic from azure storage
        :param template_id:
        :param local_url:
        :param remote_url:
        :return:
        """
        if remote_url is not None:
            if self.file_service.download_file_from_azure(remote_url, local_url) is not None:
                return self.__load_template_from_local_file(template_id, local_url)
        return None

    def __get_templates_by_user(self, user, hackathon):
        team = self.team_manager.get_team_by_user_and_hackathon(user, hackathon)
        if team is None:
            return []
        # get template from team
        htrs = self.db.find_all_objects_by(HackathonTemplateRel, hackathon_id=hackathon.id, team_id=team.id)
        if len(htrs) == 0:
            # get template from hackathon
            htrs = self.db.find_all_objects_by(HackathonTemplateRel, hackathon_id=hackathon.id, team_id=-1)

        templates = map(lambda x: x.template, htrs)
        data = []
        for template in templates:
            dic = template.dic()
            dic['data'] = self.load_template(template)
            data.append(dic)
        return data

    def __get_templates_for_pull(self, hackathon_id):
        hackathon = self.hackathon_manager.get_hackathon_by_id(hackathon_id)
        htrs = hackathon.hackathon_template_rels
        template_ids = map(lambda x: x.template.id, htrs)
        templates = self.db.find_all_objects(Template,
                                             Template.id.in_(template_ids),
                                             Template.provider == VE_PROVIDER.DOCKER,
                                             Template.status == TEMPLATE_STATUS.CHECK_PASS)
        return templates

    # template may have multiple images
    def __get_images_from_template(self, template):
        template_dic = self.load_template(template)
        ves = template_dic[BaseTemplate.VIRTUAL_ENVIRONMENTS]
        images = map(lambda x: x[DockerTemplateUnit.IMAGE], ves)
        return images  # [image:tag, image:tag]

    def __get_undownloaded_images_on_docker_host(self, docker_host, expected_images):
        images = []
        current_images = self.docker.hosted_docker.get_pulled_images(docker_host)
        self.log.debug('already exist images: %s on host: %s' % (current_images, docker_host.vm_name))
        for ex_image in expected_images:
            if ex_image not in current_images:
                images.append(ex_image)
        return flatten(images)

    def __get_filter_condition(self, **kwargs):
        """parse args and transfer to condition that can be used to query in DB

        :type  kwargs: dict
        :param kwargs: filter conditions

        :return: condition for query in DB
        """
        condition = Template.status != -1
        if kwargs['status'] is not None and kwargs['status'] >= 0:
            condition = and_(condition, Template.status == kwargs['status'])

        if kwargs['name'] is not None and len(kwargs['name']) > 0:
            condition = and_(condition, Template.name.like('%' + kwargs['name'] + '%'))

        if kwargs['description'] is not None and len(kwargs['description']) > 0:
            condition = and_(condition, Template.description.like('%' + kwargs['description'] + '%'))

        return condition

    def __get_provider_from_template_dic(self, template):
        """get the provider from template

        :type template: dict
        :param template: dict object of template

        :return: provider value , if not exist in template return None
        """
        try:
            if BaseTemplate.VIRTUAL_ENVIRONMENTS_PROVIDER in template:
                return template[BaseTemplate.VIRTUAL_ENVIRONMENTS_PROVIDER]
            return template[BaseTemplate.VIRTUAL_ENVIRONMENTS][0][BaseTemplate.VIRTUAL_ENVIRONMENTS]
        except Exception as e:
            self.log.error(e)
            return None

    def __get_template_from_request(self):
        """ get template dic from http post request

        get file from request , then json load it to a dic

        :return: template dic , if load file failed raise BadRequest exception
        """
        for file_name in request.files:
            try:
                template = json.load(request.files[file_name])
                self.log.debug("create template: %r" % template)
                return template
            except Exception as ex:
                self.log.error(ex)
                raise BadRequest(description="invalid template file")