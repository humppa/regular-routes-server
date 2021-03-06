# regular-routes-server

## Introduction

"Learning Regular Routes" -server project contains the server-side code for the "learning regular routes"-project. The server is currently split into four separate components:

1. regularroutes-site: An end-user website supporting oauth2 login with a Google account and display of user-specific information. Accessible from the root address of the site.
1. regularroutes-api: Interface to the mobile client. Also some maintenance operations, which are accessed automatically (duplicate removal and snapping)
1. regularroutes-dev: Developer operations, not to be left openly accessible on a production site. Currently includes visualizations (both current data and predicted points) based on client numbers and generation of CSV-dumps from the data.
1. regularroutes-scheduler: Scheduled operations. Currently includes device_data filtering, retrieval of (Helsinki region) mass transit live data) and computation of statistics for energy certificate generation.

## Setting up a new TrafficSense client-server pair

This is the procedure for setting up a new client-server pair to run the TrafficSense service.

1. Server setup: Install and initialize the server as detailed in the [regular-routes-devops](https://github.com/aalto-trafficsense/regular-routes-devops) readme. The chef initialisation script used by the procedure in devops clones the designated branch of this repository.
1. Client setup: Build a corresponding client as detailed in the [trafficsense-android](https://github.com/aalto-trafficsense/trafficsense-android) readme.

## Setting up a new server development environment

This is the procedure to set up an environment for developing server software on any local machine.

1. Since the addition of python libraries used by prediction (numpy, scipy etc.), some extra installations are required for the successful installation of the python libraries. On Ubuntu: `$ sudo apt-get install build-essential python-pip python-dev gfortran libatlas-base-dev libblas-dev liblapack-dev`. On Mac OS X others are included in Xcode, but a fortran compiler is required. It belongs to the gcc package, on brew: `$ brew install gcc`.
1. If using a local database, install [postgresql](http://www.postgresql.org/) and [postgis](http://postgis.net/). Available for Debian Linuxes (Ubuntu) via `apt-get`, and [homebrew](http://brew.sh/) on Mac OS X. An alternative would be to tunnel onto a database on another server, but the installation of the `psycopg2` python library below fails if `pg_config`, a part of postgresql, is not available.
1. Create a regularroutes database - empty or populated - as [instructed] (https://github.com/aalto-trafficsense/regular-routes-server/tree/master/sql_admin). Leave a postgresql server running (`postgres -D rrdb`, where `rrdb` is the path to the directory with your database). If the postgresql server is on another machine, arrange tunnels accordingly.
1. Clone this (regular-routes-server) repo to a directory where development is to be carried out. Go (`cd`) into your repository root directory and start a local branch (`git branch my_test`) if practical.
1. Create a `regularroutes.cfg` file (it is listed in .gitignore, so shouldn't spread out to github) with the following contents:

          SECRET_KEY = 'secretkey'
          SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://regularroutes:qwerty@localhost/postgres'
          MAPS_API_KEY = 'INSERT_Browser_API_key_from_Google_Developers_Console'
          FMI_API_KEY = 'INSERT_key_allocated_by_Finnish_Meteorology_Institute'
          FIREBASE_KEY = 'INSERT_Server_key_from_Firebase_Console'
          RR_URL_PREFIX = ''
          AUTH_REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
          MASS_TRANSIT_LIVE_KEEP_DAYS = 7
          GMAIL_FROM = 'gmail-from-username@gmail.com'
          GMAIL_PWD = 'password-for-the-above'
          EMAIL_TO = 'email-to-recipient@somewhere.com'

    Some explanations:
    * `SQLALCHEMY_DATABASE_URI`: `qwerty` is the password for the `regularroutes` role created [here](https://github.com/aalto-trafficsense/regular-routes-server/blob/master/sql_admin/init_rr.sql).
    * On the Google Developers Console, create a project (if not already created) and enable `Google Maps JavaScript API` as explained in [devops readme](https://github.com/aalto-trafficsense/regular-routes-devops).
    * Still on the Console, create the `Browser API key` also according to [devops readme](https://github.com/aalto-trafficsense/regular-routes-devops). Under `Accept requests from these HTTP referrers (web sites)` enter `http://localhost:5000`. Press `Save`
    * From the generated `Browser API key`, copy the `API key` value into `MAPS_API_KEY` in your `regularroutes.cfg` file shown above.
    * `FMI_API_KEY` is the key to access open weather data from the services of the [Finnish Meteorology Institute](https://en.ilmatieteenlaitos.fi/open-data). The current version is once per day fetching hourly observation and forecast data for Helsinki. If useful, apply for a key from FMI. If you do not need it, please comment out `scheduler.add_job(retrieve_weather_info, "cron", hour="6")` from `scheduler.py` initialisation.
    * `FIREBASE_KEY` is found from [Firebase console](https://console.firebase.google.com/) Settings -> Project Settings -> Cloud messaging -> Project Credentials -> Server key. Note that they `google-services.json` file from the console is needed for the corresponding [client](https://github.com/aalto-trafficsense/trafficsense-android).
    * `MASS_TRANSIT_LIVE_KEEP_DAYS` is the number of days vehicle data obtained from Helsinki Regional Traffic will be stored in the database before removal. Recognised public transportation trips are stored indefinitely. A value of 1 is enough.
    * The current participation cancellation function (in siteserver.py) sends an email with the user_id to the configured EMAIL_TO address. The 'yagmail' library uses the gmail server, so a gmail account is needed (GMAIL_FROM and GMAIL_PWD) for sending.
    
    _Note: When creating a new server using chef as instructed in [devops](https://github.com/aalto-trafficsense/regular-routes-devops), the `regularroutes.cfg` file is automatically generated using parameters from a `regularroutes-srvr.json` file._
    
1. Save the `client_secrets.json` file for your project to the root of your repo. Instructions for generating it are in the [devops readme](https://github.com/aalto-trafficsense/regular-routes-devops). This file is required in server startup and used in mobile client authentication, but to access this local dev environment from a mobile client also a web server and a routable IP address for the local machine are needed, not covered by these setup instructions.
1. Optional?: Install [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/), which in addition to `pip` should be the only global python packages. Can be installed e.g. via pip, easy_install, apt-get. E.g. `pip install virtualenv`. (_MJR Note: May not be necessary, if using PyCharm built-in virtualenv-support._)
1. Install and run [PyCharm IDE](https://www.jetbrains.com/pycharm/) for web server / flask development (_Note: There is an educational license available for Intellij-Idea and PyCharm ultimate versions._)
1. `File` `Open` your regular-routes-repository root folder. If offered, deny package installations from `requirements.txt` so they don't install into the global environment.
1. Create a virtualenv from: `PyCharm`/ `Preferences` / `Project: regular-routes-server` / `Project Interpreter` (on Mac, `File` / `Settings` / ... in Linux). Click the wheel on the upper right, select `Create virtualenv` and create a virtualenv named e.g. `regular-routes-server` with Python v. 2.7.x. Select your virtualenv from the drop-down box next to the wheel. (_MJR Note: Currently using 2.7.10_)
1. If the packages in `requirements.txt` don't start installing otherwise, open one of the root-directory python-files on the editor (e.g. `apiserver.py`) 
1. Install [Flask-classy](https://pythonhosted.org/Flask-Classy/)  (REST extension package; found from python repo & PyCharm package download list). Under PyCharm installations are done under `Preferences` (or `Settings`) / `Project` / `Project Interpreter` and currently appear to be included with the packages in the `requirements.txt`.
1. Install any other packages, which might be missing from requirements.txt (_MJR Note: Newer OS X:s currently do not install the required old scipy 0.9.0 due to header problems. Installing the latest scipy instead is fine, since scipy is only needed for prediction, which is not currently used._).
1. Under `Run` `Edit configurations` set the working directory to point to your repository root. Also check the `Script:`, which can be `siteserver.py`, `devserver.py`, `apiserver.py` or `scheduler.py` depending on which component is to be run.
1. `Run 'regular-routes-server'`
1. If no major problems occurred in startup, open a browser window and test. E.g. `http://localhost:5000/maintenance/duplicates` (from `apiserver`) should receive a `0 duplicate data points were deleted` response. Other commands in the [command reference](https://github.com/aalto-trafficsense/regular-routes-server/wiki/Command-Reference).

## Python virtualenv

Basically [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/) and pip should be the only global python packages. Virtualenv isolates the site-packages for each separate project, making it easier to maintain them. For the local development environment virtual environments can be managed with PyCharm, on the server the deployment chef-script creates the necessary virtual environment.

If there is a need to access virtualenvs manually, the installation can be done with pip:

    $ sudo pip install virtualenv

Current default setup in the regularroutes servers is that the virtualenv is in directory `/opt/regularroutes` and it is called `virtualenv`. Activation from command line:

    $ source virtualenv/bin/activate

Sometimes it is necessary to regenerate the virtualenv for cleanup purposes. This can be done with:

1. Rename the old virtualenv to some other name
1. Create a new virtualenv: `$ virtualenv virtualenv`
1. Install the requirements: `pip install -r requirements.txt`
    
