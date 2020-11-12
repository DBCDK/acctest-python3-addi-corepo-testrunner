#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""
:mod:`acceptance_tester.testsuite_runners.addi_corepo.resource_manager` -- Resource manager for addi-corepo
===========================================================================================================

============================
Addi-corepo resource manager
============================

Resource Manager for addi-service/corepo-repository integration
testing.
"""
import logging
import os
import subprocess
import time

from configobj import ConfigObj

from os_python.common.net.iserver import IServer
from acceptance_tester.abstract_testsuite_runner.resource_manager import AbstractResourceManager
from os_python.common.utils.init_functions import die
from os_python.common.utils.init_functions import NullHandler
from os_python.docker.docker_container import DockerContainer
from os_python.docker.docker_container import ContainerSuitePool
from os_python.connectors.postgres import PostgresDockerConnector

from os_python.wiremock_helper import wiremock_load_rules_from_dir

### define logger
logger = logging.getLogger( "dbc."+__name__ )
logger.addHandler( NullHandler() )

class ContainerPoolImpl(ContainerSuitePool):

    def __init__(self, resource_folder):
        super(ContainerPoolImpl, self).__init__()
        self.resource_folder = resource_folder

    def create_suite(self, suite):
        suite_name = "_addi_corepo_%f" % time.time()
        corepo_db = suite.create_container("corepo-db",
                                           name="corepo-db" + suite_name,
                                           image_name=DockerContainer.secure_docker_image('corepo-postgresql-1.2'),
                                           environment_variables={"POSTGRES_USER": "corepo",
                                                                  "POSTGRES_PASSWORD": "corepo",
                                                                  "POSTGRES_DB": "corepo"},
                                           start_timeout=1200)
        addi_db = suite.create_container("addi-db",
                                         name="addi-db" + suite_name,
                                         image_name=DockerContainer.secure_docker_image('addi-service-postgres-1.0-snapshot'),
                                         start_timeout=1200)

        wiremock = suite.create_container("wiremock", 
                                          image_name=DockerContainer.secure_docker_image('os-wiremock-1.0-snapshot'),
                                          start_timeout=1200)

        corepo_db.start()
        addi_db.start()
        wiremock.start()
        addi_db.waitFor("database system is ready to accept connections")
        corepo_db.waitFor("database system is ready to accept connections")
        wiremock.waitFor("verbose:")

        corepo_db_root = "corepo:corepo@%s:5432/corepo" % corepo_db.get_ip()

        wiremock_load_rules_from_dir("http://%s:8080" % wiremock.get_ip(), self.resource_folder)
        corepo_content_service = suite.create_container("corepo-content-service", image_name=DockerContainer.secure_docker_image('corepo-content-service-1.2'),
                                                        environment_variables={"COREPO_POSTGRES_URL": corepo_db_root,
                                                                               "VIPCORE_ENDPOINT": "http://vipcore.iscrum-vip-extern-test.svc.cloud.dbc.dk/1.0/api/",
                                                                               "LOG__dk_dbc": "TRACE",
                                                                               "JAVA_MAX_HEAP_SIZE": "2G",
                                                                               "PAYARA_STARTUP_TIMEOUT": 1200},
                                                        start_timeout=1200)

        hive = suite.create_container("hive",
                                      image_name=DockerContainer.secure_docker_image('hive-app-1.0-snapshot', tag='latest'),
                                      name="hive" + suite_name,
                                      environment_variables={"REPOSITORY_URL": "jdbc:postgresql://corepo:corepo@%s:5432/corepo" % corepo_db.get_ip(),
                                                             "HARVEST_MODE": "SERVER",
                                                             "HARVEST_HARVESTER": "ESFileRecordFeeder",
                                                             "HOLDINGSDB_URL": "",
                                                             # ADDISERVICE_URL must not point to ADDI service. US1818 requires that addi jobs
                                                             # be added manually in test to be able to control order
                                                             "ADDISERVICE_URL": "",
                                                             "BATCHEXCHANGE_JDBCURL": "",
                                                             "VIPCORE_ENDPOINT": "http://vipcore.iscrum-vip-extern-test.svc.cloud.dbc.dk/1.0/api/",
                                                             "HIVE_POOLSIZE": 1,
                                                             "HARVEST_POLLINTERVAL":2,
                                                             "LOG__JavaScript_Logger": "TRACE",
                                                             "LOG__dk_dbc": "TRACE"},
                                      start_timeout=1200)

        addi_service = suite.create_container("addi-service",
                                              name="addi-service" + suite_name,
                                              image_name=DockerContainer.secure_docker_image('addi-service-webapp-1.0-snapshot'),
                                              environment_variables={"COREPO_DATABASE": corepo_db_root,
                                                                     "ADDI_DATABASE": "addi:addi@%s:5432/addi" % addi_db.get_ip(),
                                                                     "THREAD_POOL_SIZE": 1,
                                                                     "LOG__JavaScript_Logger": "TRACE",
                                                                     "LOG__dk_dbc": "TRACE",
                                                                     "JAVA_MAX_HEAP_SIZE": "2G",
                                                                     "PAYARA_STARTUP_TIMEOUT": 1200},
                                              start_timeout=1200)

        corepo_content_service.start()
        corepo_content_service.waitFor("was successfully deployed in")
        corepo_content_service.waitFor(") ready in ")

        addi_service.start()
        addi_service.waitFor("was successfully deployed in")
        addi_service.waitFor(") ready in ")
        hive.start()
        hive.waitFor("Harvesting available records")

    def on_release(self, name, container):
        if name == "corepo-db":
            logger.debug( "Release corepo-db" )
            connector = PostgresDockerConnector(container)
            connector.wipe("records", "corepo")
            connector.restart_sequence("work_id_seq", "corepo")
            connector.restart_sequence("unit_id_seq", "corepo")
        elif name == "addi-db":
            logger.debug( "Release addi-db" )
            connector = PostgresDockerConnector(container)
            connector.wipe("job", "addi")

class ResourceManager( AbstractResourceManager ):

    def __init__( self, resource_folder, tests, use_preloaded, use_config, conf_file=None ):

        logger.info( "Securing necessary resources." )
        self.tests = tests

        self.resource_folder = resource_folder
        if not os.path.exists( self.resource_folder ):
            os.mkdir( self.resource_folder )

        self.use_preloaded_resources = use_preloaded
        self.use_config_resources = use_config
        self.resource_config = ConfigObj(self.use_config_resources)

        self.container_pool = ContainerPoolImpl(resource_folder)

        self.required_artifacts = {'wiremock-rules-openagency': ['wiremock-rules-openagency.zip', 'os-wiremock-rules'], 'corepo-ingest': ['corepo-ingest.jar', 'corepo/job/master']}
        for artifact in self.required_artifacts:
            self.required_artifacts[artifact].append(self._secure_artifact(artifact, *self.required_artifacts[artifact]))

    def shutdown(self):
        self.container_pool.shutdown()

    def _secure_artifact(self, name, artifact, project, build_number=None):
        if name in self.resource_config:
            logger.debug("configured resource %s at %s" % (name, self.resource_config[name]))
            return self.resource_config[name]

        if self.use_preloaded_resources == False:
            logger.debug( "Downloading %s artifact from integration server"%artifact )
            iserv = IServer( temp_folder=self.resource_folder, project_name=project )

            return iserv.download_and_validate_artifact( self.resource_folder, artifact, build_number=build_number)

        logger.debug("Using preloaded %s artifact"%artifact)
        preloaded_artifact = os.path.join(self.resource_folder, artifact)
        preloaded_md5 = preloaded_artifact + ".md5"
        artifact_OK = self._verify_md5(preloaded_artifact, preloaded_md5)
        if not artifact_OK:
            die("artifact %s could not be verified by md5file %s"%(preloaded_artifact, preloaded_md5))

        return preloaded_artifact

