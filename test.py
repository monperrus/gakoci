"""
Test Suite for GakoCI

Usage: 
create an API token
export GITHUB_AUTH_TOKEN=<your token>
create a test repo called 'test-repo'
change YOU=<login> below
python3 -m unittest test
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

YOU = "surli"


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
        self.assertEqual("spoon", gakoci.get_core_info_push_file(
            'test/resources/push_event.json')['repo'])
        self.assertEqual("INRIA", gakoci.get_core_info_push_file(
            'test/resources/push_event.json')['owner'])
        self.assertEqual("master", gakoci.get_core_info_push_file(
            'test/resources/push_event.json')['branch'])
        self.assertEqual("385f1274627568a6d225061452abb3f3663ff57d", gakoci.get_core_info_push_file(
            'test/resources/push_event.json')['commit'])
        self.assertEqual("https://api.github.com/repos/INRIA/spoon/statuses/385f1274627568a6d225061452abb3f3663ff57d",
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
    owner = YOU
    repo_name = "test-repo"
    repo_path = owner + "/" + repo_name
    """ python3 -m unittest test.CoreTestCase """

    def setUp(self):
        self.setUp_github()
        self.setUp_local()
        self.setUp_flask()

    def setUp_flask(self):

        # curl -X POST http://localhost:5000/seriouslykill
        app = gakoci.GakoCINgrok(repos=[CoreTestCase.repo_path], github_token=os.environ[
                                 "GITHUB_AUTH_TOKEN"], hooks_dir="testhooks")
        self.gakoci = app
        self.application = app.application
        # http://stackoverflow.com/questions/14814201/can-i-serve-multiple-clients-using-just-flask-app-run-as-standalone
        thread = threading.Thread(target=self.application.run)
        thread.start()
        time.sleep(1)

    def setUp_local(self):
        if os.path.exists("test-repo"):
            shutil.rmtree("test-repo")
        if os.path.exists("testhooks"):
            shutil.rmtree("testhooks")
        os.system("git clone git@github.com:" +
                  CoreTestCase.repo_path + ".git")
        os.system('mkdir -p testhooks')
        # the hooks that will be used
        os.system('printf "#!/bin/sh\necho yeah | tee trace.txt"  > testhooks/push-' +
                  CoreTestCase.owner + '-' + CoreTestCase.repo_name)
        os.system('printf "#!/bin/sh\necho foo | tee trace.txt"  > testhooks/push-' +
                  CoreTestCase.owner + '-' + CoreTestCase.repo_name + 'foo')
        os.system('printf "#!/bin/sh\necho bar | tee trace.txt"  > testhooks/push-' +
                  CoreTestCase.owner + '-' + CoreTestCase.repo_name + 'bar')
        os.system('chmod 755 testhooks/*')

    def setUp_github(self):
        self.github = github.Github(
            login_or_token=os.environ["GITHUB_AUTH_TOKEN"])
        self.repo = self.github.get_repo(CoreTestCase.repo_path)
        for x in self.repo.get_hooks():
            x.delete()

    def runTest(self):
        r = self.repo
        # self.assertEqual(0, sum(1 for x in r.get_hooks()))
        self.assertEqual(1, sum(1 for x in r.get_hooks()))
        n_commits = sum(1 for x in r.get_commits())
        n_events = sum(1 for x in r.get_events())
        os.system(
            'cd test-repo/; echo `date` > README.md; git commit -m up -a ; git push origin master')

        # wait that Github updates the data on the API side
        time.sleep(.5)
        self.assertEqual(n_commits + 1, sum(1 for x in r.get_commits()))

        # wait for Github callback a little bit
        time.sleep(1.5)

        self.assertEqual(1, len(self.application.log['ping']))
        self.assertEqual(1, len(self.application.log['push']))

        self.assertEqual(
            "test-repo", self.application.last_payload["repository"]["name"])

        commit_id = gakoci.get_core_info_push_str(
            self.application.last_payload)['commit']

        self.assertEqual(n_commits + 1, sum(1 for x in r.get_commits()))

        # we have uploaded several statuses
        self.assertEqual(
            3, sum(1 for x in r.get_commit(commit_id).get_statuses()))

        # todo assert on status detail url

        # now testing pull requests
        os.system('rm testhooks/*')
        os.system('printf "#!/bin/sh\necho pr" > testhooks/pull_request-' +
                  CoreTestCase.owner + '-' + CoreTestCase.repo_name)
        os.system('chmod 755 testhooks/*')

        pr_branch = str(uuid.uuid4())
        os.system('cd test-repo/; git checkout -b ' + pr_branch +
                  '; echo `date` > README.md; git commit -m up -a ; git push -f origin ' + pr_branch)
        create_pull_request({"token": os.environ[
                            "GITHUB_AUTH_TOKEN"], "user": CoreTestCase.owner, "repo": CoreTestCase.repo_name, "head": pr_branch})

        # wait for Github callback a little bit
        time.sleep(3)

        self.assertEqual(1, len(self.application.log['pull_request']))

    def tearDown(self):
        # Stop webserver
        requests.post(self.gakoci.ngrokconfig[
                      "url"] + "/" + self.application.killurl)

        # Stop tunnelling
        if self.gakoci.ngrok:
            self.gakoci.ngrok.stop()
            self.gakoci.ngrok = None
