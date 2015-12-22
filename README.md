Pullpo
======

Pull requests / reviews analyzer

Usage
-----
```
usage: Usage: 'pullpo [options] <owner> <repository>

positional arguments:
  owner                 Owner of the repository on GitHub
  repository            Name of the repository on GitHub

optional arguments:
  -h, --help            show this help message and exit

Database options:
  -u DB_USER, --user DB_USER
                        Database user name
  -p DB_PASSWORD, --password DB_PASSWORD
                        Database user password
  -d DB_NAME            Name of the database where fetched projects will be
                        stored
  --host DB_HOSTNAME    Name of the host where the database server is running
  --port DB_PORT        Port of the host where the database server is running

GitHub options:
  --gh-user GH_USER     GiHub user name
  --gh-password GH_PASSWORD
                        GitHub user password
```

Requirements
------------

* Python >= 2.7 (3.x series not supported yet)
* MySQL >= 5.5
* SQLAlchemy >= 0.8
* requests>=2.0.0
* github3.py >= 1.0a

License
-------

Licensed under GNU General Public License (GPL), version 3 or later.
