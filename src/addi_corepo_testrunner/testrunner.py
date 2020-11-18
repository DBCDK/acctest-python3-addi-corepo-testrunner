#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""
:mod:`acceptance_tester.testsuite_runners.addi_corepo.testrunner` -- Testrunner for addi-corepo
===============================================================================================

======================
Addi-corepo Testrunner
======================

This class executes xml test files of type 'addi-corepo'.
"""
import logging
import os
from nose.tools import nottest

from acceptance_tester.abstract_testsuite_runner.test_runner import TestRunner as AbstractTestRunner

from os_python.common.utils.init_functions import NullHandler
from os_python.common.utils.cleanupstack import CleanupStack

from os_python.addiservice.addi_parser import AddiParser
from os_python.hive.hive_parser import HiveParser
from os_python.connectors.hive import HiveDockerConnector

from os_python.connectors.corepo import CorepoContentService
from os_python.corepo.corepo import Corepo
from os_python.corepo.corepo_parser import CorepoParser

### define logger
logger = logging.getLogger( "dbc." + __name__ )
logger.addHandler( NullHandler() )


class TestRunner( AbstractTestRunner ):

    @nottest
    def run_test( self, test_xml, build_folder, resource_manager ):
        """
        Runs a 'addi-corepo' test.

        This method runs a test and puts the result into the
        failure/error lists accordingly.

        :param test_xml:
            Xml object specifying test.
        :type test_xml:
            lxml.etree.Element
        :param build_folder:
            Folder to use as build folder.
        :type build_folder:
            string
        :param resource_manager:
            Class used to secure reources.
        :type resource_manager:
            class that inherits from
            acceptance_tester.abstract_testsuite_runner.resource_manager

        """

        container_suite = resource_manager.container_pool.take(log_folder=self.logfolder)
        try:
            corepo_db = container_suite.get("corepo-db", build_folder)
            corepo_content_service = container_suite.get("corepo-content-service", build_folder)
            hive = container_suite.get("hive", build_folder)
            addi_service = container_suite.get("addi-service", build_folder)

            ### Connectors
            ingest_tool = os.path.join(resource_manager.resource_folder, 'corepo-ingest.jar')
            corepo_content_service_connector = CorepoContentService("http://%s:8080" % corepo_content_service.get_ip())
            corepo_connector = Corepo(corepo_db, corepo_content_service, ingest_tool, os.path.join(build_folder, 'ingest'))

            hive_connector = HiveDockerConnector(hive)

            ### Setup parser
            repository_parser = CorepoParser(self.base_folder, corepo_connector)
            hive_parser = HiveParser(self.base_folder, hive_connector)
            addi_parser = AddiParser(self.base_folder, addi_service, corepo_connector)

            stop_stack = CleanupStack.getInstance()
            try:
                for pf in [repository_parser.parser_functions, hive_parser.parser_functions, addi_parser.parser_functions]:
                    self.parser_functions.update(pf)

                stop_stack.addFunction(self.save_service_logfiles, corepo_connector, 'corepo')
                corepo_connector.start()

                ### run the test
                self.parse( test_xml )

            finally:
                stop_stack.callFunctions()

        except Exception as err:
            logger.error( "Caught error during testing: %s"%str(err))
            raise

        finally:
            resource_manager.container_pool.release(container_suite)



