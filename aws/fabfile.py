# Follow the instructions in `readme.md` to get started.
# Remember to call `source ~/bin/aws-mfa` every 24 hours.
import boto3
from fabric import task, Connection, ThreadingGroup as Group
from paramiko import RSAKey
import os
from json import dumps
import time

ec2 = boto3.client('ec2')
region = os.environ.get("AWS_EC2_REGION")


# --- Start Config ---

def credentials():
    ''' Set the username and path to key file. '''
    return {
        'user': 'ubuntu',
        'keyfile': '/Users/asonnino/.ssh/aws-fb.pem'
    }


def filter(instance):
    ''' Specify a filter to select only the desired hosts. '''
    name = next(tag['Value'] for tag in instance.tags if 'Name'in tag['Key'])
    return 'vasp'.casefold() in name.casefold()

# --- End Config ---


def set_hosts(ctx, status='running', cred=credentials, filter=filter):
    ''' Helper function to set the credentials and a list of instances into
    context; the instances are filtered with the filter provided as input.
    '''
    # Set credentials into the context
    credentials = cred()
    ctx.user = credentials['user']
    ctx.keyfile = credentials['keyfile']  # This is only used the task `info`
    ctx.connect_kwargs.pkey = RSAKey.from_private_key_file(
        credentials['keyfile'])

    # Get all instances for a given status.
    ec2resource = boto3.resource('ec2')
    instances = ec2resource.instances.filter(
        Filters=[{'Name': 'instance-state-name', 'Values': [status]}]
    )

    # Get all instances that match the input filter
    ctx.instances = [x for x in instances if filter(x)]
    ctx.hosts = [x.public_ip_address for x in instances if filter(x)]


@task
def test(ctx):
    ''' Test the connection with all hosts.
    If the command succeeds, it prints "Hello, World!" for each host.

    COMMANDS:	fab test
    '''
    set_hosts(ctx)
    g = Group(*ctx.hosts, user=ctx.user, connect_kwargs=ctx.connect_kwargs)
    g.run('host myip.opendns.com resolver1.opendns.com | grep address')


@task
def info(ctx):
    ''' Print commands to ssh into hosts (debug).

    COMMANDS:	fab info
    '''
    set_hosts(ctx)
    print('\nAvailable machines:')
    for i, host in enumerate(ctx.hosts):
        print(f'{i}\t ssh -i {ctx.keyfile} {ctx.user}@{host}')
    print()


@task
def start(ctx):
    ''' Start all instances.

    COMMANDS:	fab start
    '''
    set_hosts(ctx, status='stopped')
    ids = [instance.id for instance in ctx.instances]
    if not ids:
        print('There are no instances to start.')
        return
    response = ec2.start_instances(InstanceIds=ids, DryRun=False)
    print(response['StartingInstances'])


@task
def stop(ctx):
    ''' Stop all instances.

    COMMANDS:	fab stop
    '''
    set_hosts(ctx, status='running')
    ids = [instance.id for instance in ctx.instances]
    if not ids:
        print('There are no instances to stop.')
        return
    response = ec2.stop_instances(InstanceIds=ids, DryRun=False)
    print(response)


@task
def install(ctx):
    ''' Cleanup and install twins on a fresh machine.

    COMMANDS:	fab install
    '''
    setup_script = 'offchainapi-aws-setup.sh'

    set_hosts(ctx)
    for host in ctx.hosts:
        c = Connection(host, user=ctx.user, connect_kwargs=ctx.connect_kwargs)
        c.put(setup_script, '.')
        c.run(f'chmod +x {setup_script}')

    # TODO: find a way to forgo the grub config prompt and run the setup
    # script automatically.
    print(f'The script "{setup_script}"" is now uploaded on every machine; '
          'Run it manually and pay attention to the APT grub config prompt.')


@task
def update(ctx):
    ''' Update the software from Github.

    UPLOAD_FILES:
        False: Only update the code from GitHub.
        True: Update the code and upload new config files.

    COMMANDS:	fab update
    '''
    UPLOAD_FILES = True

    run_script = 'offchainapi-aws-run.sh'
    port = 8090  # NOTE: Not a simple param, update nginx config accordingly.

    # Update code.
    set_hosts(ctx)
    g = Group(*ctx.hosts, user=ctx.user, connect_kwargs=ctx.connect_kwargs)
    g.run('(cd off-chain-api/ && git pull)')

    # Generate config files.
    files = []
    for i, host in enumerate(ctx.hosts):
        configs = {
            "addr": chr(65+i)*16,
            "base_url": f'{host}',
            "port": port
        }
        files += [f'{host}.json']
        with open(files[-1], 'w') as f:
            f.write(dumps(configs))

    if not UPLOAD_FILES:
        return

    # Upload files.
    print('Uploading files..')
    for host in ctx.hosts:
        c = Connection(host, user=ctx.user, connect_kwargs=ctx.connect_kwargs)
        c.put(run_script, '.')
        c.run(f'chmod +x {run_script}')
        c.run('rm off-chain-api/*.json || true')
        for f in files:
            c.put(f, './off-chain-api')
    print('done.')


@task
def nginx(ctx):
    ''' Configure NGINX.

    COMMANDS:   fab config
    '''
    nginx_conf = 'offchainapi-nginx.conf'
    tls_material = ['server_cert.pem', 'server_key.pem']

    set_hosts(ctx)
    for host in ctx.hosts:
        c = Connection(host, user=ctx.user, connect_kwargs=ctx.connect_kwargs)
        for file in tls_material:
            c.put(file, '.')
        c.put(nginx_conf, '.')
        c.sudo(f'mv {nginx_conf} /etc/nginx/sites-available || true')
        command = f'ln -s /etc/nginx/sites-available/{nginx_conf}'
        command += f' /etc/nginx/sites-enabled/{nginx_conf}'
        command += ' || true'
        c.sudo(command)
        c.sudo('service nginx restart')


@task
def run(ctx, num_of_commands=100, port=80, id=0):
    ''' Runs experiments with the specified configs.

    COMMANDS:	fab run
    '''
    run_script = 'offchainapi-aws-run.sh'

    set_hosts(ctx)
    for host in ctx.hosts:
        path = f'{host}.json '
        runs = f'{num_of_commands}' if host == ctx.hosts[-1] else '0'
        logfile = f'{host}-{num_of_commands}-{id}.logs.txt'

        # NOTE: Calling tmux in threaded groups does not work (bug in Fabric?).
        c = Connection(host, user=ctx.user, connect_kwargs=ctx.connect_kwargs)
        command = 'tmux new -d -s "offchainapi"'
        command += f' ./{run_script} {path} {runs} {port} {logfile}'
        c.run(command)
        if host == ctx.hosts[-1]:
            print(f'The client is {host}.')


@task
def kill(ctx):
    ''' Kill the process on all machines and (optionally) clear all state.

    CONFIG:
        0: Only kill the process.
        1: Kill the process and delete logs.
        2: Kill the process and delete all state and logs.

    COMMANDS:   fab kill
    '''
    CONFIG = 1

    set_hosts(ctx)
    g = Group(*ctx.hosts, user=ctx.user, connect_kwargs=ctx.connect_kwargs)

    # Kill process.
    g.run('tmux kill-server || true')

    # Reset state and delete logs.
    if CONFIG > 0:
        g.run('rm off-chain-api/*.log* || true')
    if CONFIG > 1:
        g.run('rm off-chain-api/*.json || true')


@task
def status(ctx):
    ''' Prints info about the execution progress.

    COMMANDS:	fab status
    '''
    set_hosts(ctx)
    host = ctx.hosts[-1]
    c = Connection(host, user=ctx.user, connect_kwargs=ctx.connect_kwargs)
    c.run('cat ./off-chain-api/*.log* || true')


@task
def tps(ctx):
    ''' Runs TPS measurement and print results to logs.

    COMMANDS:	fab tps
    '''
    configs = range(10000, 100000+1, 10000)
    repeats = 9
    offset = 5
    port = 80

    def compute_delay(num_of_commands):
        return 30 * num_of_commands / 5000 if num_of_commands > 5000 else 30

    for repeat in range(repeats):
        for i, num_of_commands in enumerate(configs):
            executed, total = (i+1) + repeat*len(configs), repeats*len(configs)
            print(f'Progress: {executed}/{total}')
            kill(ctx)
            time.sleep(0.5)
            run(ctx, num_of_commands=num_of_commands, id=repeat+offset, port=port)
            time.sleep(compute_delay(num_of_commands))

    kill(ctx)
    status(ctx)


@task
def latency(ctx):
    ''' Runs latency measurement and print results to logs.

    COMMANDS:	fab latency
    '''
    repeats = 100
    port = 80

    for repeat in range(repeats):
        print(f'Progress: {repeat}/{torepeatstal}')
        kill(ctx)
        time.sleep(0.5)
        run(ctx, num_of_commands=1, id=repeat, port=port)
        time.sleep(5)

    kill(ctx)
    status(ctx)
