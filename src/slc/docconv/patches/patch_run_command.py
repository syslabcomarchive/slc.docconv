# Patch _run_command to allow setting of RLIMITS
import subprocess
from logging import getLogger
import resource
from collective.documentviewer import convert

logger = getLogger('collective.documentviewer')

MAX_CPU = 1800


def setlimits():
    """ Set the max CPU time allowed for a single converter process """
    rsrc = resource.RLIMIT_CPU
    # need to know current hard limit as we can't increase that
    soft, hard = resource.getrlimit(rsrc)
    if MAX_CPU > hard:
        soft = hard
    else:
        soft = MAX_CPU
    resource.setrlimit(rsrc, (soft, hard))
    logger.info("RLIMIT_CPU set to %s/%s" % (soft, hard))


def _run_command(self, cmd):
    """ copied over from documentviewer to be able to set resource limits
    """
    if isinstance(cmd, basestring):
        cmd = cmd.split()
    cmdformatted = ' '.join(cmd)
    logger.info("Running rlimited command %s" % cmdformatted)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               close_fds=self.close_fds,
                               preexec_fn=setlimits)
    output, error = process.communicate()
    process.stdout.close()
    process.stderr.close()
    if process.returncode != 0:
        error = """Command
%s
finished with return code
%i
and output:
%s
%s""" % (cmdformatted, process.returncode, output, error)
        logger.info(error)
        raise Exception(error)
    logger.info("Finished Running Command %s" % cmdformatted)
    return output

logger.info("Patching _run_command to support RLIMIT")
convert.setlimits = setlimits
convert.BaseSubProcess._run_command = _run_command
