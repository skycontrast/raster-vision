import uuid
import logging
import os
from typing import List, Optional

from rastervision2.pipeline import rv_config
from rastervision2.pipeline.runner import Runner

log = logging.getLogger(__name__)
AWS_BATCH = 'aws_batch'


def submit_job(cmd: List[str],
               debug: bool = False,
               profile: str = False,
               attempts: int = 5,
               parent_job_ids: List[str] = None,
               num_array_jobs: Optional[int] = None,
               use_gpu: bool = False) -> str:
    """Submit a job to run on AWS Batch.

    Args:
        cmd: a command to run in the Docker container for the remote job
        debug: if True, run the command using a ptvsd wrapper which sets up a remote
            VS Code Python debugger server
        profile: if True, run the command using kernprof, a line profiler
        attempts: the number of times to try running the command which is useful
            in case of failure.
        parent_job_ids: optional list of parent Batch job ids. The job created by this
            will only run after the parent jobs complete successfully.
        num_array_jobs: if set, make this a Batch array job with size equal to
            num_array_jobs
        use_gpu: if True, run the job in a GPU-enabled queue
    """
    batch_config = rv_config.get_namespace_config('AWS_BATCH')
    job_queue = batch_config('cpu_job_queue')
    job_def = batch_config('cpu_job_def')
    if use_gpu:
        job_queue = batch_config('gpu_job_queue')
        job_def = batch_config('gpu_job_def')

    import boto3
    client = boto3.client('batch')
    job_name = 'ffda-{}'.format(uuid.uuid4())

    cmd_list = cmd.split(' ')
    if debug:
        cmd_list = [
            'python', '-m', 'ptvsd', '--host', '0.0.0.0', '--port', '6006',
            '--wait', '-m'
        ] + cmd_list

    if profile:
        cmd_list = ['kernprof', '-v', '-l'] + cmd_list

    kwargs = {
        'jobName': job_name,
        'jobQueue': job_queue,
        'jobDefinition': job_def,
        'containerOverrides': {
            'command': cmd_list
        },
        'retryStrategy': {
            'attempts': attempts
        },
    }
    if parent_job_ids:
        kwargs['dependsOn'] = [{'jobId': id} for id in parent_job_ids]
    if num_array_jobs:
        kwargs['arrayProperties'] = {'size': num_array_jobs}

    job_id = client.submit_job(**kwargs)['jobId']
    msg = 'submitted job with jobName={} and jobId={}'.format(job_name, job_id)
    log.info(msg)
    log.info(cmd_list)

    return job_id


class AWSBatchRunner(Runner):
    """Runs pipelines remotely using AWS Batch.

    Requires Everett configuration of form:

    ```
    [AWS_BATCH]
    cpu_job_queue=
    cpu_job_def=
    gpu_job_queue=
    gpu_job_def=
    attempts=
    ```
    """

    def run(self, cfg_json_uri, pipeline, commands, num_splits=1):
        parent_job_ids = []
        for command in commands:
            cmd = [
                'python', '-m', 'rastervision2.pipeline.cli run_command',
                cfg_json_uri, command, '--runner', AWS_BATCH
            ]
            num_array_jobs = None
            if command in pipeline.split_commands and num_splits > 1:
                num_array_jobs = num_splits
                if num_splits > 1:
                    cmd += ['--num-splits', str(num_splits)]
            use_gpu = command in pipeline.gpu_commands
            cmd = ' '.join(cmd)

            job_id = submit_job(
                cmd,
                parent_job_ids=parent_job_ids,
                num_array_jobs=num_array_jobs,
                use_gpu=use_gpu)
            parent_job_ids = [job_id]

    def get_split_ind(self):
        return int(os.environ.get('AWS_BATCH_JOB_ARRAY_INDEX', 0))
