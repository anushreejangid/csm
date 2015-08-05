# =============================================================================
# migrate_xr_to_exr.py - plugin for migrating classic XR to eXR/fleXR
#
# Copyright (c)  2013, Cisco Systems
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
# =============================================================================




import re
import time
import pexpect

import os
import subprocess
import requests

NOX_URL = 'http://wwwin-people.cisco.com/alextang/'
NOX_FILENAME_fetch = 'nox_linux_64bit_6.0.0v1.bin'
NOX_FILENAME = 'nox'

#"""

import sys

aut_path = os.path.join(os.path.dirname(__file__), '../../../aut')


# print aut_path
sys.path.append(aut_path)

from au.plugins.plugin import IPlugin
from au.device import Device
from au.lib import pkg_utils as pkgutils
from au.plugins.install_add import InstallAddPlugin
from au.plugins.install_commit import InstallCommitPlugin
from au.plugins.install_act import InstallActivatePlugin
from au.condor.exceptions import CommandTimeoutError
from au.plugins.plugin import PluginError




# waiting long time (5 minutes)
TIME_OUT = 60



class MigrateConfigurationPlugin(IPlugin):

    """
    A plugin for migrating from XR to eXR/fleXR
    This plugin accesses rommon and set rommon variable EMT.
    A router is reloaded twice.
    Console access is needed.
    Arguments:
    T.B.D.
    """
    NAME = "MIGRATE_CONFIG_TO_EXR"
    DESCRIPTION = "MIGRATE CONFIG TO EXR"
    TYPE = "MIGRATE"
    VERSION = "0.0.1"



    def _get_nox_binary_publish_date(self):
        try:
            url = NOX_URL + 'nox.lastPublishDate'
            r = requests.get(url)
            return r.text
        except:
            return None

    def _get_file_http(self, filename, destination):
        with open(destination + '/' + filename, 'wb') as handle:
            response = requests.get(NOX_URL + filename, stream=True)


            if not response.ok:
                self.error("ERROR: HTTP request to" + NOX_URL + filename + " failed.")

            print "request ok"
            for block in response.iter_content(1024):
                handle.write(block)

    def _is_conversion_successful(self, nox_output):
        match = re.search('Filename[\sA-Za-z\n]*[-\s]*\S*\s+(\d*)\s+\d*\(\s*\d%\)\s+\d*\(\s*\d%\)\s+(\d*)', nox_output)

        if match:
            print "matched " + match.group(1) + " to " + match.group(2)
            if match.group(1) == match.group(2):
                return True

        print "no match or matches not equal"
        return False


    def _apply_config(self, device, filename):
        cmd = 'admin config'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success


        cmd = 'load disk0:/' + filename + ' \r'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success


        # TO DO: confirm if commit replace or commit best-effort
        cmd = 'commit'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success

        cmd = 'end'
        success, output = device.execute_command(cmd)
        print cmd, '\n', output, "<-----------------", success


    def start(self, device, *args, **kwargs):

        repo_str = kwargs.get('repository', None)
        if not repo_str:
            self.error("ERROR:repository not provided")

        repo_str = 'tftp://1.75.1.1/joydai'

        fileloc = kwargs.get('fileloc', None)
        if not fileloc:
            fileloc = '../../csm_data/migration'
            noxloc = '../aut/au/plugins/'
            packages = kwargs.get("pkg_file", None)
            if not packages:
                self.error("ERROR:packages not provided")
        else:
            noxloc = './'
            packages = ['asr9k-fpd-px.pie-5.3.2.10I.SIT_IMAGE', 'asr9k-px-5.3.2.10I.CSCuu11794.pie']

        print "device name = " + device.name
        filename = device.name.replace(".", "_")
        filename = filename.replace(":", "_")



        # checked: migrate config file to new config - need Eddie's tool

        date = self._get_nox_binary_publish_date()

        need_new_nox = False
        print "date = " + date
        if os.path.isfile(fileloc + '/' + 'nox.lastPublishDate'):
            with open(fileloc + '/' + 'nox.lastPublishDate', 'r') as f:
                current_date = f.readline()

            if date != current_date:
                need_new_nox = True

        else:
            need_new_nox = True

        if need_new_nox:
            self._get_file_http(NOX_FILENAME_fetch, fileloc)
            with open(fileloc + '/' + 'nox.lastPublishDate', 'w') as nox_publish_date_file:
                nox_publish_date_file.write(date)


        print "chmod" + "+x" + fileloc + '/' + NOX_FILENAME
        print fileloc + '/' + NOX_FILENAME + "-f" + fileloc + '/' + filename

        commands = [subprocess.Popen(["chmod", "+x", fileloc + '/' + NOX_FILENAME]), subprocess.Popen([fileloc + '/' + NOX_FILENAME, "-f", fileloc + '/' + filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)]


        nox_output, nox_error = commands[1].communicate()

        print nox_output
        print nox_error
        conversion_success = self._is_conversion_successful(nox_output)

        if conversion_success:

            print "conversion is successful"
            self.csm_ctx.post_status("finished converting config")

        else:
            self.error("configuration conversion is not successful.")

            #self._copy_file_to_device(device, repo_str, filename, 'disk0:/')


            # Yet to test: apply the config
            #self._apply_config(device, filename)




        #return True


def main():
    device = Device(["telnet://root:root@172.25.146.221:2005"])
    #device = Device(["telnet://cisco:cisco@172.28.98.3"])
    #repo = 'ftp://terastream:cisco@172.20.168.195/echami'
    repo = 'tftp://1.75.1.1/joydai'

    device.connect()
    migration = MigrateToExrPlugin()
    migration.start(device, repository=repo, fileloc = '../../../../csm_data/migration')


if __name__ == "__main__":
    main()
