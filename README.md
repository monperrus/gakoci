# GakoCI: continuous integration daemon for Github

##  What is GakoCI?
GakoCI is a continuous integration (CI) daemon that is specialized for Github and pull-request based development.

What it does:

1. it registers a webhook on Github for a set of repositories
2. upon pull requests, it executes a set of hook scripts 
3. for each hook script, it adds a pull request status and a link to a trace file if one exists

It is written in Python and is under a MIT license.

## How to use it?


    git clone http://github.com/monperrus/gakoci.git
    cd gakoci
    pip3 install -r requirements.txt
    export GITHUB_AUTH_USER=yourname
    export GITHUB_AUTH_TOKEN=1234
    # monperrus/test-repo is the repo for which CI is setup
    python3 -c 'import gakoci; gakoci.GakoCI(repos=["monperrus/test-repo"]).run()'

`GITHUB_AUTH_TOKEN` is an API token for Github (see <https://help.github.com/articles/creating-an-access-token-for-command-line-use/>) that is exported as environment variable.


## How to set up jobs?

### Simplest example

Let's assume you've started GakoCI for `foobar/testrepo`.
Then, the pull request job is in a file called `hooks/pull_request-foobar-testrepo-checkout`. Gakoci clones the repository automatically if the job file ends with `-checkout`.

    #!/bin/bash
    mvn clean test

If the job script does not return with 0, the pull request status is marked as `failure`.

### Github status

If the job produces a file called `status.txt`, it is used as commit status on Github

    #!/bin/bash
    mvn clean test
    echo "all good" > status.txt

### Job with traces

If the job produces a file called `trace.txt`, the pull request status contains a link to browse the trace.

Example job:

    #!/bin/bash
    mvn clean test 2>&1 | tee trace.txt
    exit ${PIPESTATUS[0]}

This can be combined with `status.txt`.

### Multiple jobs

You can have several push jobs for the same repo, by simply adding a suffix: `hooks/pull_request-foobar-testrepo-1-checkout`, `hooks/pull_request-foobar-testrepo-2--checkout`, 

### Cloning on your own

If the job file name does not end with `-checkout` you have to clone the repo on your own:

    #!/bin/bash
    git init
    git remote -v add origin git://github.com/$3/$4.git
    git fetch origin $5:gakoci
    git checkout gakoci
    ... (the rest of CI)

### Push jobs

GakoCI can also work with push events. CI scripts must staart with `push` (eg ``hooks/push-foobar-testrepo`) and push job files take 6 arguments:

    <payload.json> <event_type> <repo_owner> <repo_name> <branch> <commit_sha1>
    
    push-monperrus-spoon /home/spirals/mmonperr/tmpmzhmhr3d push monperrus spoon cleaning1 4c651dae33df8d8b339487a2c5d825f1c99e54e7



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
