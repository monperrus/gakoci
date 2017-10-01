"""
Test Suite for GakoCI

Usage: 
- create a test repo called 'test-repo'
- create an API token
- export GITHUB_AUTH_USER=<username> (eg export GITHUB_AUTH_USER=monperrus)
- export GITHUB_AUTH_TOKEN=<your token>

- python3 -m unittest test
"""
import unittest
import os
import github
import shutil
import requests
import threading
import time
import gakoci
import json
import uuid
import builtins
import subprocess
import socket as so 
def create_pull_request(args):
    """ 
    only for testing purposes master hardcoded
    POST /repos/:owner/:repo/pulls 
    args: {"token":"", "user":"", "repo":"", "head":""}
    """
    url = ('https://api.github.com/repos/'
           '{args[user]}/'
           '{args[repo]}/pulls'.format(args=args))

    headers = {'Authorization': 'token {args[token]}'.format(args=args)}
    data = json.dumps({
        'title': 'test',
        'base': 'master',
        'head': args['head'],
    })
    # print(url)
    # print(data)
    resp = requests.post(url=url, data=data, headers=headers)
    assert resp.status_code == 201, (resp.status_code, resp.text)


class HelperTestCase(unittest.TestCase):
    """  python3 -m unittest test.HelperTestCase  """

    def runTest(self):
        self.assertEqual("test", gakoci.get_core_info_push_file(
            'test/resources/push_event.json')['repo'])
        self.assertEqual("monperrus", gakoci.get_core_info_push_file(
            'test/resources/push_event.json')['owner'])
        self.assertEqual("master", gakoci.get_core_info_push_file(
            'test/resources/push_event.json')['branch'])
        self.assertEqual("385f1274627568a6d225061452abb3f3663ff57d", gakoci.get_core_info_push_file(
            'test/resources/push_event.json')['commit'])
        self.assertEqual("https://api.github.com/repos/monperrus/test/statuses/385f1274627568a6d225061452abb3f3663ff57d",
                         gakoci.get_core_info_push_file('test/resources/push_event.json')['statuses_url'])

        # doc about pull requests
        # https://developer.github.com/v3/activity/events/types/#pullrequestevent
        # everything is in pull request
        self.assertEqual("pvojtechovsky", gakoci.get_core_info_pull_request_file(
            'test/resources/pull_request_event.json')['owner'])
        self.assertEqual("spoon", gakoci.get_core_info_pull_request_file(
            'test/resources/pull_request_event.json')['repo'])
        self.assertEqual("INRIA", gakoci.get_core_info_pull_request_file(
            'test/resources/pull_request_event.json')['base_owner'])
        self.assertEqual("spoon", gakoci.get_core_info_pull_request_file(
            'test/resources/pull_request_event.json')['base_repo'])

        self.assertEqual("supportCommentsInSnippet", gakoci.get_core_info_pull_request_file(
            'test/resources/pull_request_event.json')['branch'])
        self.assertEqual("e640b870f24eb7fc1078d36a4657b556874119e5", gakoci.get_core_info_pull_request_file(
            'test/resources/pull_request_event.json')['commit'])
        self.assertEqual("https://api.github.com/repos/INRIA/spoon/statuses/e640b870f24eb7fc1078d36a4657b556874119e5",
                         gakoci.get_core_info_pull_request_file('test/resources/pull_request_event.json')['statuses_url'])
        self.assertEqual("930", gakoci.get_core_info_pull_request_file('test/resources/pull_request_event.json')['pr_number'])


class CoreTestCase(unittest.TestCase):
    """ test the server using Ngrok (works on localhost and travis) """
    """ python3 -m unittest test.CoreTestCase """

    def setUpAll(self, owner, repo_name):
        if os.path.exists('gakoci_config.py'):
            import gakoci_config

        if 'GITHUB_AUTH_USER' in dir(builtins): os.environ['GITHUB_AUTH_USER'] = builtins.GITHUB_AUTH_USER
        if 'GITHUB_AUTH_TOKEN' in dir(builtins): os.environ['GITHUB_AUTH_TOKEN'] = builtins.GITHUB_AUTH_TOKEN
        if 'NGROK_AUTH_TOKEN' in dir(builtins): os.environ['NGROK_AUTH_TOKEN'] = builtins.NGROK_AUTH_TOKEN
        self.PROTOCOL_TEST_REPO = builtins.PROTOCOL_TEST_REPO if 'PROTOCOL_TEST_REPO' in dir(builtins) else "https"
        
        repo_path = owner + "/" + repo_name
        
        self.github = github.Github(login_or_token=os.environ["GITHUB_AUTH_TOKEN"])
        self.repo = self.github.get_repo(repo_path)

        self.setUp_local(owner = owner, repo_name = repo_name)
        self.setUp_flask([repo_path], github_token=os.environ['GITHUB_AUTH_TOKEN'], gakoci_klass = gakoci.GakoCINgrok)

    def setUp_flask(self, repos, github_token = "", gakoci_klass = gakoci.GakoCI):

        app = gakoci_klass(repos=repos, github_token=github_token, hooks_dir="testhooks")
        self.gakoci = app
        self.application = app.application
        # http://stackoverflow.com/questions/14814201/can-i-serve-multiple-clients-using-just-flask-app-run-as-standalone
        thread = threading.Thread(target=self.application.run)
        thread.start()
        time.sleep(1)

    def setUp_local(self, owner, repo_name):
        owner = owner
        repo_path = owner + "/" + repo_name
        if os.path.exists("testhooks"):
            shutil.rmtree("testhooks")
        os.system('mkdir -p testhooks')
        # the hooks that will be used
        os.system('printf "#!/bin/sh\necho yeah | tee trace.txt"  > testhooks/push-' +
                  owner + '-' + repo_name)
        os.system('printf "#!/bin/sh\necho foo | tee trace.txt"  > testhooks/push-' +
                  owner + '-' + repo_name + '-something')
        # testing the shell support feature
        os.system('printf "#!/bin/sh\ngit log"  > testhooks/push-' +
                  owner + '-' + repo_name + '-shell.sh')
        os.system('chmod 755 testhooks/*')

            
    def test0(self):
      try:
        """ the server does nothing if it receives an event for which it is not configured
        python3 -m unittest test.CoreTestCase.test0
        """
        self.setUp_local(owner = "monperrus", repo_name = "test")
        self.setUp_flask(["monperrus/somethingelse"])
        with open("test/resources/push_event.json") as json:
            requests.post(self.gakoci.get_url() + "/", data = json.read(),
                          headers = {'X-GitHub-Event': 'push', 'Content-type': 'application/json'})
        self.assertEqual(0, len(self.gakoci.perform_tasks_log))
      finally: self.shutdown_server()
      
    def test1(self):
      try:
        """ the server triggers 3 actions 
        python3 -m unittest test.CoreTestCase.test1
        """
        self.setUp_local(owner = "monperrus", repo_name = "test")
        self.setUp_flask(["monperrus/test"])
        with open("test/resources/push_event.json") as json:
            requests.post(self.gakoci.get_url() + "/", data = json.read(),
                          headers = {'X-GitHub-Event': 'push', 'Content-type': 'application/json'})
        self.assertEqual(3, len(self.gakoci.perform_tasks_log))
        self.assertTrue('push' in self.gakoci.log)
      finally: self.shutdown_server()

    def test2(self):
      try:
        """ global end to end test using github """
        owner = "monperrus"
        repo_name = "test-repo"
        self.setUpAll(owner = owner, repo_name = repo_name)
        os.system("git clone " + self.PROTOCOL_TEST_REPO + "://github.com/" +
                  owner+ "/" + repo_name + ".git")
        r = self.repo
        # self.assertEqual(0, sum(1 for x in r.get_hooks()))
        hooks = [x.config['url'] for x in r.get_hooks()]
        self.assertTrue(self.gakoci.public_url in hooks)
        n_commits = sum(1 for x in r.get_commits())
        n_events = sum(1 for x in r.get_events())
        
        ## testing push-based CI
        os.system('cd test-repo/; git checkout master')
        os.system(
            'cd test-repo/; echo `date` > README.md; git commit -m up -a ; git push origin master')

        # wait that Github updates the data on the API side
        time.sleep(.5)
        self.assertEqual(n_commits + 1, sum(1 for x in r.get_commits()))

        # wait for Github callback a little bit
        time.sleep(1.5)

        self.assertEqual(1, len(self.gakoci.log['ping']))
        self.assertEqual(1, len(self.gakoci.log['push']))

        self.assertEqual(
            "test-repo", self.application.last_payload["repository"]["name"])

        commit_id = gakoci.get_core_info_push_str(
            self.application.last_payload)['commit']

        self.assertEqual(n_commits + 1, sum(1 for x in r.get_commits()))

        # we have uploaded several statuses
        self.assertEqual(
            3, sum(1 for x in r.get_commit(commit_id).get_statuses()))

        # now testing pull requests
        os.system('rm testhooks/*')
        # creating one pull request file
        os.system('printf "#!/bin/sh\nls --format=horizontal" > testhooks/pull_request-' +
                  owner + '-' + repo_name+"-checkout.sh")
        os.system('chmod 755 testhooks/*')

        pr_branch = str(uuid.uuid4())
        os.system('cd test-repo/; git checkout -b ' + pr_branch)
        os.system('cd test-repo/; echo `date` > README.md; git commit -m up -a ; git push -f origin ' + pr_branch)
        commit_id = subprocess.check_output(['sh', '-c', "cd test-repo/; git rev-parse HEAD"]).decode("utf-8").strip()
        print("pr commit: "+commit_id)
        create_pull_request({"token": os.environ[
                            "GITHUB_AUTH_TOKEN"], "user": owner, "repo": repo_name, "head": pr_branch})

        # wait for Github callback a little bit (3 seconds is not enough)
        time.sleep(5)
        statuses = [x for x in r.get_commit(commit_id).get_statuses()]
        self.assertEqual(
            1, len(statuses))
        # testing the status.txt feature and the checkout feature
        self.assertEqual("README.md", statuses[0].description)
        self.assertEqual(1, len(self.gakoci.log['pull_request']))
      finally: 
          self.shutdown_server()
          if os.path.exists("test-repo"):
            shutil.rmtree("test-repo")
    def shutdown_server(self):
        # Stop webserver, should shutdown
        requests.post(self.gakoci.get_url() + "/" + self.application.killurl)
