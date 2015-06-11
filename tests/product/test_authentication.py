# -*- coding: utf-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Product tests for SSH authentication for presto-admin commands
"""

import os
import subprocess

from nose.plugins.attrib import attr

from tests.product.base_product_case import BaseProductTestCase, \
    LOCAL_RESOURCES_DIR


class TestAuthentication(BaseProductTestCase):

    success_output = (
        'Deploying tpch.properties connector configurations on: slave1 \n'
        'Deploying tpch.properties connector configurations on: master \n'
        'Deploying tpch.properties connector configurations on: slave2 \n'
        'Deploying tpch.properties connector configurations on: slave3 \n'
    )

    interactive_text = (
        '/usr/lib64/python2.6/getpass.py:83: GetPassWarning: Can not control '
        'echo on the terminal.\n'
        'Initial value for env.password: \n'
        'Warning: Password input may be echoed.\n'
        '  passwd = fallback_getpass(prompt, stream)\n'
    )

    serial_text = (
        'Disconnecting from master... done.\n'
        'Disconnecting from slave1... done.\n'
        'Disconnecting from slave2... done.\n'
        'Disconnecting from slave3... done.\n'
    )

    sudo_password_prompt = (
        '[master] out: sudo password:\n'
        '[master] out: \n'
        '[slave1] out: sudo password:\n'
        '[slave1] out: \n'
        '[slave2] out: sudo password:\n'
        '[slave2] out: \n'
        '[slave3] out: sudo password:\n'
        '[slave3] out: \n'
    )

    @attr('smoketest')
    def test_incorrect_hostname(self):
        self.install_presto_admin()
        topology = {'coordinator': 'dummy_master', 'workers':
                    ['slave1', 'slave2', 'slave3']}
        self.upload_topology(topology=topology)
        command_output = self.run_prestoadmin('--extended-help',
                                              raise_error=False)
        self.assertEqual('u\'dummy_master\' is not a valid ip address or host '
                         'name.  More detailed information can be found in '
                         '/var/log/prestoadmin/presto-admin.log\n',
                         command_output)

    def parallel_password_failure_message(self, with_sudo_prompt=True):
        with open(os.path.join(LOCAL_RESOURCES_DIR,
                               'parallel_password_failure.txt')) as f:
            parallel_password_failure = f.read()
        if with_sudo_prompt:
            parallel_password_failure += ('[slave3] out: sudo password:\n'
                                          '[slave3] out: Sorry, try again.\n'
                                          '[slave2] out: sudo password:\n'
                                          '[slave2] out: Sorry, try again.\n'
                                          '[slave1] out: sudo password:\n'
                                          '[slave1] out: Sorry, try again.\n'
                                          '[master] out: sudo password:\n'
                                          '[master] out: Sorry, try again.\n')
        return parallel_password_failure

    def non_root_sudo_warning_message(self):
        with open(os.path.join(LOCAL_RESOURCES_DIR,
                               'non_root_sudo_warning_text.txt')) as f:
            non_root_sudo_warning = f.read()
        return non_root_sudo_warning

    @attr('smoketest')
    def test_passwordless_ssh_authentication(self):
        self.install_presto_admin()
        self.upload_topology()
        self.setup_for_connector_add()

        # Passwordless SSH as root, but specify -I
        # We need to do it as a script because docker_py doesn't support
        # redirecting stdin.
        command_output = self.run_prestoadmin_script(
            'echo "password" | ./presto-admin connector add -I')

        self.assertEqualIgnoringOrder(
            self.success_output + self.interactive_text, command_output)

        # Passwordless SSH as root, but specify -p
        command_output = self.run_prestoadmin('connector add --password '
                                              'password')
        self.assertEqualIgnoringOrder(self.success_output, command_output)

        # Passwordless SSH as app-admin, specify -I
        non_root_sudo_warning = self.non_root_sudo_warning_message()

        command_output = self.run_prestoadmin_script(
            'echo "password" | ./presto-admin connector add -I -u app-admin')
        self.assertEqualIgnoringOrder(
            self.success_output + self.interactive_text +
            non_root_sudo_warning, command_output)

        # Passwordless SSH as app-admin, but specify -p
        command_output = self.run_prestoadmin('connector add --password '
                                              'password -u app-admin')
        self.assertEqualIgnoringOrder(
            self.success_output + self.sudo_password_prompt, command_output)

        # Passwordless SSH as app-admin, but specify wrong password with -I
        parallel_password_failure = self.parallel_password_failure_message()
        command_output = self.run_prestoadmin_script(
            'echo "asdf" | ./presto-admin connector add -I -u app-admin')
        self.assertEqualIgnoringOrder(parallel_password_failure +
                                      self.interactive_text, command_output)

        # Passwordless SSH as app-admin, but specify wrong password with -p
        command_output = self.run_prestoadmin(
            'connector add --password asdf -u app-admin')
        self.assertEqualIgnoringOrder(parallel_password_failure,
                                      command_output)

        # Passwordless SSH as root, in serial mode
        command_output = self.run_prestoadmin_script(
            './presto-admin connector add --serial')
        self.assertEqualIgnoringOrder(
            self.success_output + self.serial_text, command_output)

    @attr('smoketest')
    def test_no_passwordless_ssh_authentication(self):
        self.install_presto_admin()
        self.upload_topology()
        self.setup_for_connector_add()

        for host in self.all_hosts():
            self.exec_create_start(host, 'rm /root/.ssh/id_rsa')

        # No passwordless SSH, no -I or -p
        parallel_password_failure = self.parallel_password_failure_message(
            with_sudo_prompt=False)
        command_output = self.run_prestoadmin('connector add')
        self.assertEqualIgnoringOrder(parallel_password_failure,
                                      command_output)

        # No passwordless SSH, -p incorrect -u root
        command_output = self.run_prestoadmin(
            'connector add --password password')
        self.assertEqualIgnoringOrder(parallel_password_failure,
                                      command_output)

        # No passwordless SSH, -I correct -u app-admin
        non_root_sudo_warning = self.non_root_sudo_warning_message()
        command_output = self.run_prestoadmin_script(
            'echo "password" | ./presto-admin connector add -I -u app-admin')
        self.assertEqualIgnoringOrder(
            self.success_output + self.interactive_text +
            non_root_sudo_warning, command_output)

        # No passwordless SSH, -p correct -u app-admin
        command_output = self.run_prestoadmin('connector add -p password '
                                              '-u app-admin')
        self.assertEqualIgnoringOrder(
            self.success_output + self.sudo_password_prompt, command_output)

        # No passwordless SSH, specify keyfile with -i
        self.exec_create_start(self.master, 'cp /home/app-admin/.ssh/id_rsa '
                                            '/root/.ssh/id_rsa.bak')
        self.exec_create_start(self.master, 'chmod 600 /root/.ssh/id_rsa.bak')
        command_output = self.run_prestoadmin(
            'connector add -i /root/.ssh/id_rsa.bak')
        self.assertEqualIgnoringOrder(self.success_output, command_output)

    @attr('smoketest')
    def test_prestoadmin_no_sudo_popen(self):
        self.install_presto_admin()
        self.upload_topology()
        self.setup_for_connector_add()

        # We use Popen because docker-py loses the first 8 characters of TTY
        # output.
        args = ['docker', 'exec', '-t', 'master', 'sudo', '-u', 'app-admin',
                '/opt/prestoadmin/presto-admin', 'topology show']
        proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        self.assertEqualIgnoringOrder(
            'Please run presto-admin with sudo.\n'
            '[Errno 13] Permission denied: \'/var/log/prestoadmin/'
            'presto-admin.log\'', proc.stdout.read())

    def setup_for_connector_add(self):
        connector_script = 'mkdir -p /etc/opt/prestoadmin/connectors\n' \
                           'echo \'connector.name=tpch\' ' \
                           '>> /etc/opt/prestoadmin/connectors/' \
                           'tpch.properties\n'
        self.run_prestoadmin_script(connector_script)
