# A simple continuous integration daemon for Github

##  What is GakoCI?
GakoCI is a simple continuous integration daemon for Github.
For a set of repositories:

1. it registers a webhook on Github 
2. upon push and pull request, it executes a set of hook scripts 
3. it adds a commit / pull requests status for each script

It can work on localhost and machines in private networks thanks to Ngrok.

## How to use it?

First, create an API token for Github (see <https://help.github.com/articles/creating-an-access-token-for-command-line-use/>) and export it as environment variable.

    git clone http://github.com/monperrus/gakoci.git
    cd gakoci
    pip3 install -r requirements.txt
    export GITHUB_AUTH_TOKEN=1234
    python3 -c 'import gakoci; gakoci.GakoCI(repos=["monperrus/test-repo"]).run()'

If you work on a private server, with no public interface, you would rather use [Ngrok](https://ngrok.com/).

    export NGROK_AUTH_TOKEN=1234
    python3 -c 'import gakoci; gakoci.GakoCINgrok(repos=["monperrus/test-repo"]).run()'


## How to set up jobs?

Let's assume you've started GakoCI for `foobar/test-repo`.
Then, the push jobs is in a file called `hooks/push-foobar-test-repo`, and the pull request job is in a file called `hooks/pull_request-foobar-test-repo`. If the job creates a file called `trace.txt`, it is viewable from the internet as job log, as in Travis (note the `| tee trace.txt` below).

You can have several push jobs for the same repo, by simply adding a suffix: `hooks/pull_request-foobar-test-repo-1`, `hooks/pull_request-foobar-test-repo-2`, ...

Typical push job for Python:

    #!/bin/bash
    git init
    echo git://github.com/$4/$5.git
    git remote -v add -t $5 origin git://github.com/$3/$4.git
    git fetch origin $5
    git reset --hard FETCH_HEAD
    python3 -m unittest 2>&1 | tee trace.txt
    exit ${PIPESTATUS[0]}

Typical push job for Java/Maven:

    #!/bin/bash
    git init
    echo git://github.com/$4/$5.git
    git remote -v add -t $5 origin git://github.com/$3/$4.git
    git fetch origin $5
    git reset --hard FETCH_HEAD
    mvn clean test 2>&1 | tee trace.txt
    exit ${PIPESTATUS[0]}
    

Push hook files take 6 arguments:

    <payload.json> <event_type> <repo_owner> <repo_name> <branch> <commit_sha1>
    push-monperrus-spoon /home/spirals/mmonperr/tmpmzhmhr3d push monperrus spoon cleaning1 4c651dae33df8d8b339487a2c5d825f1c99e54e7

Pull-request hook files take 8 arguments:

    <payload.json> <event_type> <repo_owner> <repo_name> <branch> <commit_sha1> <base_owner> <base_repo>


## Motivation

I had some experience with Travis and Jenkins, and:

* there is a kind of vendor lock-in with Travis which I don't like (esp if you have complex `.travis.yml` setups).
* Jenkins is awful because it is hardly scriptable and configurable on the command line,

Regarding the others (eg buildbot or circleci), the main required features are either not supported or badly documented (open source, support for Github webhooks, support for Github commit statuses).

[python-github-webhooks](https://github.com/carlos-jenkins/python-github-webhooks) is a good yet incomplete solution.


## Credits

<https://github.com/carlos-jenkins/python-github-webhooks> for the initial design.

<https://opensourcehacker.com/2015/03/27/testing-web-hook-http-api-callbacks-with-ngrok-in-python/> for the Ngrok part.

<https://pypi.python.org/pypi/ghstats> for code snippets about Github statuses. 
