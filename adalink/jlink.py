# adalink Segger JLink Controller
#
# Python interface to communicate with a JLink device using the native JLinkExe
# tool provided by Segger.  Note that you must have installed Segger JLink
# software from:
#   https://www.segger.com/jlink-software.html
#
# Additionally the JLinkExe should be in your system path (or explicitly
# provided to the JLink class initializer).
#
# Author: Tony DiCola
import logging
import os
import platform
import re
import sys
import subprocess
import tempfile
import time

from .errors import AdaLinkError


logger = logging.getLogger(__name__)


class JLink(object):
    def __init__(self, jlink_exe=None, jlink_path='', params=None):
        """Create a new instance of the JLink communication class.  By default
        JLinkExe should be accessible in your system path and it will be used
        to communicate with a connected JLink device.

        You can override the JLinkExe executable name by specifying a value in
        the jlink_exe parameter.  You can also manually specify the path to the
        JLinkExe executable in the jlink_path parameter.

        Optional command line arguments to JLinkExe can be provided in the
        params parameter as a string.
        """
        # If not provided, pick the appropriate JLinkExe name based on the
        # platform:
        # - Linux   = JLinkExe
        # - Mac     = JLinkExe
        # - Windows = JLink.exe
        if jlink_exe is None:
            system = platform.system()
            if system == 'Linux':
                jlink_exe = 'JLinkExe'
            elif system == 'Windows':
                jlink_exe = 'JLink.exe'
            elif system == 'Darwin':
                jlink_exe = 'JLinkExe'
            else:
                raise AdaLinkError('Unsupported system: {0}'.format(system))
        # Store the path to the JLinkExe tool so it can later be run.
        self._jlink_path = os.path.join(jlink_path, jlink_exe)
        logger.info('Using path to JLinkExe: {0}'.format(self._jlink_path))
        # Apply command line parameters if specified.
        self._jlink_params = []
        if params is not None:
            self._jlink_params.extend(params.split())
            logger.info('Using parameters to JLinkExe: {0}'.format(params))
        # Make sure we have the J-Link executable in the system path
        self._test_jlinkexe()

    def _test_jlinkexe(self):
        """Checks if JLinkExe is found in the system path or not
        """
        # Spawn JLinkExe process and capture its output.
        args = [self._jlink_path]
        args.append('?')
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE)
            process.wait()
        except OSError:
            raise AdaLinkError("'{0}' missing. Is the J-Link folder in your system "
                               "path?".format(self._jlink_path))
            sys.exit(-1)

    def run_filename(self, filename, timeout_sec=60):
        """Run the provided script with JLinkExe.  Filename should be a path to
        a script file with JLinkExe commands to run.  Returns the output of
        JLinkExe.  If execution takes longer than timeout_sec an exception will
        be thrown.  Set timeout_sec to None to disable the timeout completely.
        """
        # Spawn JLinkExe process and capture its output.
        args = [self._jlink_path]
        args.extend(self._jlink_params)
        args.append(filename)
        process = subprocess.Popen(args, stdout=subprocess.PIPE)
        if timeout_sec is None:
            # No timeout specified, just wait indefinitely for the process to end.
            process.wait()
        else:
            # Wait at most the timeout for the process to finish.
            start = time.time()
            while (time.time() - start) <= timeout_sec and process.returncode is None:
                process.poll()
                time.sleep(0)
            # Check if process is still running and timeout exceeded.
            if process.returncode is None:
                # Kill the process and raise error.
                process.kill()
                raise AdaLinkError('JLinkExe process exceeded timeout!')
        # Grab output of JLinkExe.
        output, err = process.communicate()
        logger.debug('JLink response: {0}'.format(output))
        return output

    def run_commands(self, commands, timeout_sec=60):
        """Run the provided list of commands with JLinkExe.  Commands should be
        a list of strings with with JLinkExe commands to run.  Returns the
        output of JLinkExe.  If execution takes longer than timeout_sec an
        exception will be thrown. Set timeout_sec to None to disable the timeout
        completely.
        """
        # Create temporary file to hold script.
        script_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
        commands = '\n'.join(commands)
        script_file.write(commands)
        script_file.close()
        logger.debug('Using script file name: {0}'.format(script_file.name))
        logger.debug('Running JLink commands: {0}'.format(commands))
        return self.run_filename(script_file.name, timeout_sec)

    def _readreg(self, register, command):
        """Read the specified register with the provided register read command.
        """
        # Build list of commands to read register.
        register = '{0:08X}'.format(register)  # Convert register value to hex string.
        commands = []
        commands.append('{0} {1} 1'.format(command, register))
        commands.append('q')
        # Run command and parse output for register value.
        output = self.run_commands(commands)
        match = re.search('^{0} = (\S+)'.format(register), output,
                          re.IGNORECASE | re.MULTILINE)
        if match:
            return int(match.group(1), 16)
        else:
            raise AdaLinkError('Could not find expected register value, are the J-Link and board connected?')

    def readreg32(self, register):
        return self._readreg(register, 'mem32')

    def readreg16(self, register):
        return self._readreg(register, 'mem16')

    def readreg8(self, register):
        return self._readreg(register, 'mem8')
