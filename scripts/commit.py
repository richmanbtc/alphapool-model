import argparse
import datetime
import os
import shutil
import subprocess
import tempfile
import yaml
from dotenv import load_dotenv

load_dotenv()


def run_commit(src_path=None, dest_suffix=None, project_id=None, pool=None, machine=None, deploy_key=None, prod=False):
    with tempfile.TemporaryDirectory() as dir:
        config_path = dir + '/cloudbuild.yaml'

        repoUrl = 'git@github.com:richmanbtc/alphapool-model.git'
        repoDir = 'repo'

        dest_dir = src_path.replace('.ipynb', '')
        dest_path = '{}/{}{}.ipynb'.format(
            dest_dir,
            datetime.datetime.now().strftime('%Y%m%d_%H%M%S'),
            '' if dest_suffix is None else dest_suffix
        )
        model_path = src_path.replace('.ipynb', '.xz').replace('notebooks/', 'data/')

        print('[{}]({})'.format(dest_path.replace('notebooks/', ''), dest_path.replace('notebooks/', '')))

        commit_message = 'build {}'.format(dest_path)

        known_hosts = "github.com ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ=="

        ssh_volume = {
            'name': 'ssh',
            'path': '/root/.ssh'
        }

        steps = [
            {
                'name': 'gcr.io/cloud-builders/git',
                'entrypoint': 'bash',
                'args': [
                    '-c',
                    ' && '.join([
                        'echo "$$DEPLOY_KEY" > /root/.ssh/id_rsa',
                        'chmod 400 /root/.ssh/id_rsa',
                        'echo "{}" > /root/.ssh/known_hosts'.format(known_hosts),
                    ])
                ],
                'volumes': [ssh_volume],
                'env': [
                    'DEPLOY_KEY=$_DEPLOY_KEY'
                ]
            },
            {
                'name': 'gcr.io/cloud-builders/git',
                'args': [ 'config', '--global', 'user.email', "you@example.com", ],
            },
            {
                'name': 'gcr.io/cloud-builders/git',
                'args': [ 'config', '--global', 'user.name', "Your Name", ],
            },
            {
                'name': 'gcr.io/cloud-builders/git',
                'args': [ 'clone', '--recursive', repoUrl, repoDir, ],
                'volumes': [ssh_volume],
            },
            {
                'name': 'gcr.io/cloud-builders/gcloud',
                'entrypoint': 'bash',
                'args': [ '-c', 'mkdir -p {}/{} && mv src.ipynb "{}/{}"'.format(repoDir, dest_dir, repoDir, dest_path), ],
            },
            {
                'name': 'gcr.io/cloud-builders/gcloud',
                'entrypoint': 'bash',
                'args': ['-c', 'chmod -R a+rw data notebooks'],
                'dir': repoDir,
            },
            {
                'name': 'gcr.io/cloud-builders/gcloud',
                'entrypoint': 'bash',
                'args': ['-c', 'echo ALPHAPOOL_DATASET={} >> .env'.format(os.getenv('ALPHAPOOL_DATASET'))],
                'dir': repoDir,
            },
            {
                'name': 'gcr.io/$PROJECT_ID/docker-compose',
                'args': [
                    '-f', 'docker-compose-jupyter-commit.yml',
                    'run',
                    'notebook',
                    'jupyter',
                    'nbconvert',
                    '--execute',
                    '--inplace',
                    '--ExecutePreprocessor.timeout=-1',
                    dest_path,
                ],
                'dir': repoDir,
            },
            {
                'name': 'node',
                'entrypoint': 'bash',
                'args': [
                    '-c',
                    'npm install -g optipng-bin && cp {} /tmp/a.ipynb && (cat /tmp/a.ipynb | node scripts/optipng_ipynb.js > {})'.format(dest_path, dest_path)
                ],
                'dir': repoDir
            },
        ]

        if prod:
            steps += [
                {
                    'name': 'gcr.io/cloud-builders/gcloud',
                    'entrypoint': 'bash',
                    'args': ['-c', 'mv {} {}'.format(dest_path, src_path)],
                    'dir': repoDir,
                },
                {
                    'name': 'gcr.io/cloud-builders/git',
                    'args': [ 'add', src_path, model_path ],
                    'dir': repoDir
                },
            ]
        else:
            steps += [
                {
                    'name': 'gcr.io/cloud-builders/git',
                    'args': [ 'add', dest_path ],
                    'dir': repoDir
                },
            ]

        steps += [
            {
                'name': 'gcr.io/cloud-builders/git',
                'args': [ 'commit', '-m', "'{}'".format(commit_message) ],
                'dir': repoDir
            },
            {
                'name': 'gcr.io/cloud-builders/git',
                'args': ['stash'],
                'dir': repoDir
            },
            {
                'name': 'gcr.io/cloud-builders/git',
                'args': [ 'pull', '--rebase', 'origin', 'master' ],
                'dir': repoDir,
                'volumes': [ssh_volume],
            },
            {
                'name': 'gcr.io/cloud-builders/git',
                'args': [ 'push', 'origin', 'master' ],
                'dir': repoDir,
                'volumes': [ssh_volume],
            },
        ]

        config = {
            'steps': steps,
            # 'options': {
            #     'pool': {
            #         'name': pool,
            #     }
            # },
            'timeout': '86400s',
            'queueTtl': '86400s',
        }

        with open(config_path, "w") as f:
            yaml.dump(config, f)

        shutil.copyfile(src_path, '{}/src.ipynb'.format(dir))
        shutil.copyfile(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'), '{}/google_credentials.json'.format(dir))

        options = [
            'gcloud',
            'builds',
            'submit',
            '--config={}'.format(config_path),
            '--async',
            '--project={}'.format(project_id),
            '--substitutions=_DEPLOY_KEY={}'.format(deploy_key),
        ]
        if machine is not None:
            options += ['--machine-type={}'.format(machine)]
        options += [dir]

        res = subprocess.run(options, stdout=subprocess.PIPE)

    print(res.stdout.decode('utf-8'))

parser = argparse.ArgumentParser()

parser.add_argument('src')
parser.add_argument('-p', '--prod', action='store_true')

args = parser.parse_args()
print(args)

run_commit(
    src_path=args.src,
    prod=args.prod,
    dest_suffix=None,
    project_id=os.getenv('GC_PROJECT_ID'),
    pool=None,
    machine='e2-highcpu-32',
    deploy_key=os.getenv('DEPLOY_KEY')
)
