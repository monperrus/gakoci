"""
GakoCI: A simple continuous integration server for Github ni Python
see https://github.com/monperrus/gakoci
Author: Martin Monperrus
License: MIT
Nov 2016
"""

import uuid
import github
import json
import socket
import os
from tempfile import mkstemp, mkdtemp
from subprocess import Popen, PIPE, DEVNULL
import subprocess
import time
import uuid
import threading
import glob
from distutils.spawn import find_executable

# non standards, in requirements.txt
from flask import Flask, request, abort
import requests
import github


class EventAction:
    """ abstract class represents an action to be done in response to a Github event. See for instance PushAction """

    def __init__(self):
        self.meta_info = {}

    def get_scripts(self):
        """ returns all scripts to be executed for this event. to be overridden """
        return []

    def add_script(self, script):
        """ adds a script if it exists and is executable """
        globpath = os.path.join(self.hooks_dir, script + '*')
        for s in glob.glob(globpath):
            if os.path.isfile(s) and os.access(s, os.X_OK) and s not in self.scripts:
                self.scripts.append(s)


class PushAction(EventAction):
    """ calls push-<owner>-<repo>-* with 6 arguments """

    def __init__(self, application, payload_path):
        self.scripts = []
        self.hooks_dir = application.hooks_dir
        self.meta_info = get_core_info_push_file(payload_path)
        self.payload_path = payload_path

    def get_scripts(self):
        # here it means that we somehow "secure" the CI daemon, because only
        # certain repo will be handled
        self.add_script(
            "push-" + self.meta_info['owner'] + '-' + self.meta_info['repo'])
        print(self.scripts)
        return self.scripts

    def arguments(self):
        return [self.payload_path,  # $1 in shell
                self.meta_info['event_type'],  # $2 in shell
                self.meta_info['owner'],  # $3 in shell
                self.meta_info['repo'],  # $4 in shell
                self.meta_info['branch'],  # $5 in shell
                self.meta_info['commit']  # $6 in shell
                ]


class PullRequestAction(EventAction):
    """ calls pull_requests-<owner>-<repo>-* with 8 arguments """

    def __init__(self, application, payload_path):
        self.scripts = []
        self.hooks_dir = application.hooks_dir
        self.meta_info = get_core_info_pull_request_file(payload_path)
        self.payload_path = payload_path

    def get_scripts(self):
        # here it means that we somehow "secure" the CI daemon, because only
        # certain repo will be handled
        self.add_script(
            "pull_request-" + self.meta_info['base_owner'] + '-' + self.meta_info['base_repo'])
        return self.scripts

    def arguments(self):
        return [self.payload_path, self.meta_info['event_type'], self.meta_info['owner'], self.meta_info['repo'], self.meta_info['branch'], self.meta_info['commit'], self.meta_info['base_owner'], self.meta_info['base_repo'], self.meta_info['pr_number']]


def get_core_info_push_file(json_path):
    """ extracts the important information from the push payload given as path """
    with open(json_path) as path:
        json_data = json.load(path)
        return get_core_info_push_str(json_data)


def get_core_info_push_str(json_data):
    """ extracts the important information from the push payload as string"""
    result = {'owner': json_data['repository']['owner']['name'] if 'name' in json_data['repository']['owner'].keys() else json_data['repository']['owner']['login'],
              'repo': json_data['repository']['name'],
              'branch': json_data['ref'].split('/')[2] if 'ref' in json_data else "unknown",
              'commit': json_data["head_commit"]['id'] if 'head_commit' in json_data else "unknown"
              }

    statuses_url = ('https://api.github.com/repos/'
                    '{args[owner]}/'
                    '{args[repo]}/statuses/'
                    '{args[commit]}'.format(args=result))

    result['statuses_url'] = statuses_url
    return result


def get_core_info_pull_request_file(json_path):
    """ extracts the important information from the pull request payload given as path """
    with open(json_path) as path:
        json_data = json.load(path)
        return get_core_info_pull_request_str(json_data)


def get_core_info_pull_request_str(json_data):
    """ extracts the important information from the pull request payload given as string"""
    return {
        'owner': json_data['pull_request']['head']['repo']['owner']['name'] if 'name' in json_data['pull_request']['head']['repo']['owner'].keys() else json_data['pull_request']['head']['repo']['owner']['login'],
        'repo': json_data['pull_request']['head']['repo']['name'],
        'base_owner': json_data['pull_request']['base']['repo']['owner']['name'] if 'name' in json_data['pull_request']['base']['repo']['owner'].keys() else json_data['pull_request']['base']['repo']['owner']['login'],
        'base_repo': json_data['pull_request']['base']['repo']['name'],
        'branch': json_data['pull_request']['head']['ref'] if 'ref' in json_data['pull_request']['head'] else "unknown",
        'commit': json_data['pull_request']['head']['sha'] if 'sha' in json_data['pull_request']['head'] else "unknown",
        'statuses_url': json_data['pull_request']['statuses_url'] if 'statuses_url' in json_data['pull_request'] else "unknown",
        'pr_number': str(json_data['pull_request']['number']) if 'number' in json_data['pull_request'] else "unknown"
    }


def set_commit_status(args):
    """ set the commit status on github """
    headers = {'Authorization': 'token {args[token]}'.format(args=args)}
    data = json.dumps({
        'state': args['state'],
        'context': args['context'],
        'description': args['description'] or '',
        'target_url': args['target_url'] or ''})
    resp = requests.post(url=args['statuses_url'], data=data, headers=headers)
    assert resp.status_code == 201, (resp.status_code, resp.text)


class GakoCI:
    """ 
    The main class of the GakoCI server.
    Usage: GakoCI(github_token="khkjhkjf", repos = ["monperrus/test-repo"]).run()
    """

    def __init__(self, repos, github_token="", host="127.0.0.1", port=5000, hooks_dir='./hooks'):
        self.github_token = github_token if github_token != "" else os.environ["GITHUB_AUTH_TOKEN"]
        self.repos = repos
        self.host = host
        self.port = port
        self.hooks_dir = hooks_dir
        self.application = self.create_flask_application()
        self.set_public_url()
        self.register_webhooks()
        self.ran = {}

        # used so that only one task is performed at a time
        # otherwise with for CI java, the server goes into out-of-memory
        self.lock = threading.Lock()
        pass  # end __init__

    def register_webhooks(self):
        github_o = github.Github(login_or_token=self.github_token)
        for repo in self.repos:
            r = github_o.get_repo(repo)
            if self.public_url not in [x.config['url'] for x in r.get_hooks() if "url" in x.config]:
                r.create_hook(name="web", config={
                              "url": self.public_url, "content_type": "json"}, events=["push", "pull_request"])

    def set_public_url(self):
        if self.host == "0.0.0.0":
            self.public_url = "http://" + socket.getfqdn() + ":" + str(self.port)
        else:
            self.public_url = "http://" + self.host + ":" + str(self.port)

    def get_core_info_depending_on_event_type(self, event_type, payload_path):
        result = EventAction()
        if event_type == "push":
            result = PushAction(self, payload_path)
        if event_type == "pull_request":
            result = PullRequestAction(self, payload_path)
        result.meta_info['event_type'] = event_type
        return result

    def perform_tasks(self, event_type, payload_path):
        event_action = self.get_core_info_depending_on_event_type(
            event_type, payload_path)
        for s in event_action.get_scripts():
            # has to be asynchronous, because Github expects a fast response
            threading.Thread(target=GakoCI.execute, args=(
                self, s, event_action)).start()

    def get_script_timeout_in_seconds(self):
        """ can be overridden by subclasses """
        return 60*10 # 10 minutes

    def execute(self, s, event_action):
        try:
            self.lock.acquire(True)
            cwd = mkdtemp()
            self.ran[os.path.basename(cwd)] = cwd
            command = [s] + event_action.arguments()
            print(" ".join(command))
            proc = Popen(
                executable=os.path.abspath(s),
                args=command,
                shell=False,
                cwd=cwd,
                stdout=DEVNULL, stderr=DEVNULL
            )
            timer = threading.Timer(self.get_script_timeout_in_seconds(), proc.kill)
            timer.start()
            proc.wait()
            timer.cancel()

            description = cwd
            # try to get status from status.txt file
            if os.path.isfile(cwd + "/status.txt"):
                try:
                    with open(cwd + "/status.txt") as pf:
                        description = pf.readline()
                except:
                    print("Error while reading status file.")

            # set failed status if a hook failed
            set_commit_status({
                'statuses_url': event_action.meta_info['statuses_url'],
                'token': self.github_token,
                'state': 'success' if proc.returncode == 0 else 'failure',
                'context': os.path.basename(s),
                'target_url': self.public_url + '/traces/' + os.path.basename(cwd),
                'description': description
            }
            )
        finally:
            self.lock.release()

    def create_flask_application(self):
        application = Flask(__name__)
        application.log = {}
        application.killurl = str(uuid.uuid4())

        @application.route('/' + application.killurl, methods=['POST'])
        def seriouslykill():
            func = request.environ.get('werkzeug.server.shutdown')
            func()
            return "Shutting down..."

        @application.route('/traces/<trace_id>', methods=['GET'])
        def trace(trace_id):
            return open(self.ran[trace_id] + "/trace.txt").read(), 200, {'Content-Type': 'text/plain; charset=utf-8'}

        @application.route('/', methods=['GET'])
        def about():
            return "running <a href='http://github.com/monperrus/gakoci'>http://github.com/monperrus/gakoci</a>"

        @application.route('/', methods=['POST'])
        def index():
            event_type = request.headers.get('X-GitHub-Event', 'unknown')
            event_id = request.headers.get('X-GitHub-Delivery', 'unknown')
            # if event_type == "ping": return ''

            # ping events have no POST data
            #payload=json.loads(request.data.decode('utf-8')) if len(request.data.decode('utf-8'))>0 else 'ss'
            payload = request.get_json()
            application.last_payload = payload
            if event_type in application.log:
                application.log[event_type].append(event_id)
            else:
                application.log[event_type] = [event_id]

            osfd, payloadfile = mkstemp()
            with os.fdopen(osfd, 'w') as pf:
                pf.write(json.dumps(payload))
            self.perform_tasks(event_type, payloadfile)
            return 'OK'  # end INDEX
        return application

    def run(self, **keywords):
        self.application.run(host=self.host, port=self.port, **keywords)


class GakoCINgrok(GakoCI):
    """ A GakoCI that uses Ngrok, it requires environment variable NGROK_AUTH_TOKEN """

    def __init__(self, repos, github_token, host="127.0.0.1", port=5000, hooks_dir='./hooks', auth_token=None):
        if auth_token == None:
            auth_token = os.environ["NGROK_AUTH_TOKEN"]
        self.setUp_ngrok(port, auth_token=auth_token)
        super().__init__(repos=repos, github_token=github_token,
                         host=host, port=port, hooks_dir=hooks_dir)

    def set_public_url(self):
        self.public_url = self.ngrokconfig["url"]

    def setUp_ngrok(self, port, auth_token):

        os.system('killall ngrok')

        self.ngrok = None
        self.ngrokconfig = {}
        self.ngrokconfig["port"] = port  # flask port

        # We need ngrok tunnel for webhook notifications
        self.auth_token = auth_token
        self.ngrok = NgrokTunnel(self.ngrokconfig["port"], auth_token)

        # Pass dynamically generated tunnel URL to backend config
        tunnel_url = self.ngrok.start()
        self.ngrokconfig["url"] = tunnel_url


class NgrokTunnel:
    """ utility class for GakoCINgrok. Credits: https://opensourcehacker.com/2015/03/27/testing-web-hook-http-api-callbacks-with-ngrok-in-python/ """

    def __init__(self, port, auth_token):
        """Initalize Ngrok tunnel.

        :param auth_token: Your auth token string you get after logging into ngrok.com

        :param port: int, localhost port forwarded through tunnel
        """
        assert find_executable(
            "ngrok"), "ngrok command must be installed, see https://ngrok.com/"
        self.port = port
        self.auth_token = auth_token

    def start(self, ngrok_die_check_delay=3):
        """Starts the thread on the background and blocks until we get a tunnel URL.

        :return: the tunnel URL which is now publicly open for your localhost port
        """

        command = ["ngrok", "http", "--authtoken={}".format(
            self.auth_token), "--log=stdout", str(self.port)]
        self.ngrok = subprocess.Popen(command, stdout=subprocess.DEVNULL)

        # See that we don't instantly die
        time.sleep(ngrok_die_check_delay)

        # getting the generated subdomain from the Ngrok local API
        response = requests.get(
            "http://localhost:4040/api/tunnels", headers={"accept": "application/json"})
        self.public_url = response.json()['tunnels'][0]['public_url']

        assert self.ngrok.poll() is None, "ngrok terminated abrutly"

        return self.public_url

    def stop(self):
        """Tell ngrok to tear down the tunnel.

        Stop the background tunneling process.
        """
        self.ngrok.terminate()
