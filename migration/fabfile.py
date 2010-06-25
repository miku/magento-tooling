#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Approach from 

http://activecodeline.com/moving-magento-site-from-development-to-live-server

to move a magento from one location to another coded in *fabric*.

Use ``migration.cfg`` to specify your locations. Double-check
those entries, since we have some destructive commands in here,
which will e.g. wipe out destination directories before placing a new copy.

When configured, just run

    fab migrate:your_configuration_file
    

Prerequisites:

    - python and fabric installed
    - a password-less ssh connection via keys

References:

http://activecodeline.com/moving-magento-site-from-development-to-live-server
http://fabfile.org

Todo:
    - Check permissions
    - Get rid of global cfg object
    - More safety measures

"""
import time, os, re, sys
from ConfigParser import SafeConfigParser
from fabric.api import run, local, env
from fabric.operations import get, put

env.hosts = [username@example.com]

MYSQLDUMP_HEADER = """
SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT;
SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS;
SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION;
SET NAMES utf8;
SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO';
SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0;
"""

MYSQLDUMP_FOOTER = """
SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT;
SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS;
SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION;
SET SQL_NOTES=@OLD_SQL_NOTES;
"""

cfg = SafeConfigParser()
# cfg.readfp(open('migration.cfg'))

def mass_replace(filename, match, replacement):
    """
    In-place mass replace match with replacement in filename.
    """
    fh = open(filename, 'r')
    content = fh.read()
    fh.close()
    
    # some stats
    pattern = re.compile(match)
    print >> sys.stderr, 'Replacing {0} occurences...'.format(
        len(pattern.findall(content)))
    
    content = content.replace(match, replacement)
    
    fh = open(filename, 'w')
    fh.write(content)
    fh.close()
    
def replace_base_url(filename, key, value, verbose=True):
    """
    In-place replace the value of key, e.g. 'web/secure/base_url' with a
    new value, e.g. the new target base_url.
    """
    fh = open(filename, 'r')
    content = fh.read()
    fh.close()

    pattern = re.compile(r"'{0}','([^']*)'".format(key))
    matches = [m for m in pattern.findall(content)]
    if not len(matches) == 1:
        print >> sys.stderr, 'This dump seems to be broken.'
        raise Exception("We have more than one '{0}' option.".format(key))
    current_url = matches[0]
    if verbose:
        print >> sys.stderr, 'Replacing {0}: {1} ==> {2}'.format(
            key, current_url, value)
    content = content.replace("'{0}','{1}'".format(key, current_url), 
        "'{0}','{1}'".format(key, value))

    fh = open(filename, 'w')
    fh.write(content)
    fh.close()

def config():
    """
    Show current configuration.
    """
    for section in cfg.sections():
        for k, v in sorted(cfg.items(section)):
            print '[{0}] {1} ==> {2}'.format(section, k, v)

def get_dump():
    """
    Get a current MySQL dump.
    """
    run('rm -f {0}'.format(cfg.get('transit', 'dump_filename')))
    run('rm -f {0}.bz2'.format(cfg.get('transit', 'dump_filename')))
    
    local('rm -f {0}'.format(os.path.basename(
        cfg.get('transit', 'dump_filename'))))
    local('rm -f {0}.bz2'.format(os.path.basename(
        cfg.get('transit', 'dump_filename'))))

    run('{0} --compatible=mysql40 --user={1} --password={2} {3} > {4}'.format(
        cfg.get('source', 'mysqldump_exe'), 
        cfg.get('source', 'mysql_username'), 
        cfg.get('source', 'mysql_password'),
        cfg.get('source', 'mysql_db'),
        cfg.get('transit', 'dump_filename')
    ))
    run('bzip2 {0}'.format(cfg.get('transit', 'dump_filename')))
    get('{0}.bz2'.format(cfg.get('transit', 'dump_filename')), 
        '{0}.bz2'.format(os.path.basename(
            cfg.get('transit', 'dump_filename'))))
    local('bunzip2 {0}.bz2'.format(os.path.basename(
        cfg.get('transit', 'dump_filename'))))

def transform_dump():
    """
    Do the mysql mass transformations (locally).
    """ 
    try:
        rules = eval(cfg.get('transit', 'rules'))
    except Exception, e:
        print >> sys.stderr, 'Found a problem in transit > rules'
        print >> sys.stderr, 'Rules evaluate to a tuple of tuples!'
        raise Exception("Rules are not of desired format.")

    for rule in rules:
        print >> sys.stderr, 'Mass replacing {0[0]} ==> {0[1]}'.format(rule)
        mass_replace(os.path.basename(cfg.get('transit', 'dump_filename')), 
            rule[0], rule[1])
    
    replace_base_url(os.path.basename(cfg.get('transit', 'dump_filename')),
        'web/unsecure/base_url', 
        cfg.get('destination', 'unsecure_base_url'))

    replace_base_url(os.path.basename(cfg.get('transit', 'dump_filename')),
        'web/secure/base_url', 
        cfg.get('destination', 'secure_base_url'))

    print >> sys.stderr, 'Decorating SQL dump...'
    # decorate dump with MYSQLDUMP_HEADER and _FOOTER
    fh = open(os.path.basename(cfg.get('transit', 'dump_filename')), 'r')
    content = fh.read()
    fh.close()
    
    # content = MYSQLDUMP_HEADER + content + MYSQLDUMP_FOOTER
    
    fh = open(os.path.basename(cfg.get('transit', 'dump_filename')), 'w')
    fh.write(content)
    fh.close()
    
def upload_dump():
    """
    Upload local mysqldump to server. The dump should be modified by now.
    """
    run('rm -f {0}'.format(cfg.get('transit', 'dump_filename')))
    run('rm -f {0}.bz2'.format(cfg.get('transit', 'dump_filename')))
    
    local('bzip2 {0}'.format(os.path.basename(
        cfg.get('transit', 'dump_filename'))))
    
    put("{0}.bz2".format(os.path.basename(
        cfg.get('transit', 'dump_filename'))),
        "{0}.bz2".format(
        cfg.get('transit', 'dump_filename')))
    
    run('bunzip2 {0}.bz2'.format(cfg.get('transit', 'dump_filename')))

def copy_remote_magento_installation(archiver='zip'):
    """
    Copy magento installation on the server, using `tar`.
    """
    
    if not archiver in ('tar', 'zip'):
        print >> sys.stderr, 'Use either "zip" or "tar" as archiver.'
        print >> sys.stderr, \
            'Skipping this step may leave your system inconsistent.'
        return 1

    original_magento_root = cfg.get('source', 'magento_root')
    # original_magento_root_packed = '/tmp/original_magento_root.packed.zip'
    original_magento_root_packed = '/tmp/original_magento_root.packed.tar'
    run('rm -f {0}'.format(original_magento_root_packed))

    if archiver == 'zip':
        run('cd {0}; zip -r {1} {2}; cd -'.format(
            os.path.dirname(original_magento_root),
            original_magento_root_packed,
            os.path.basename(original_magento_root),
        ))

    if archiver == 'tar':
        run('cd {0}; tar cvf {1} {2}; cd -'.format(
            os.path.dirname(original_magento_root),
            original_magento_root_packed,
            os.path.basename(original_magento_root),
        ))

    new_magento_root = cfg.get('destination', 'magento_root')

    # beware, this is destructive
    run("rm -rf {0}".format(os.path.dirname(new_magento_root)))
    run("mkdir -p {0}".format(os.path.dirname(new_magento_root)))
    run("mv {0} {1}".format(original_magento_root_packed, 
        os.path.dirname(new_magento_root)))

    if archiver == 'zip':
        run("cd {0}; unzip {1}; cd -".format(os.path.dirname(new_magento_root),
            os.path.basename(original_magento_root_packed)))

    if archiver == 'tar':
        run("cd {0}; tar xf {1}; cd -".format(
            os.path.dirname(new_magento_root),
            os.path.basename(original_magento_root_packed)))
        
def import_dump():
    """
    Import mysql dump.
    """
    print >> sys.stderr, 'Importing MySQL dump...'
    
    run("{0} --user={1} --password={2} {3} < {4}".format(
        cfg.get('destination', 'mysql_exe'),
        cfg.get('destination', 'mysql_username'),
        cfg.get('destination', 'mysql_password'),
        cfg.get('destination', 'mysql_db'),
        cfg.get('transit', 'dump_filename'),
    ))

def adjust_local_xml():
    """
    Adjust configuration at magento/app/etc/local.xml
    """
    
    print >> sys.stderr, 'Adjusting magento/app/etc/local.xml'
    
    tmp_local = 'new_local.xml'

    get(os.path.join(os.path.join(
        cfg.get('destination', 'magento_root'), 'app/etc/local.xml')),
        tmp_local
    )
    
    fh = open(tmp_local, 'r')
    content = fh.read()
    fh.close()
    
    o_username = "<username><![CDATA[{0}]]></username>".format(
        cfg.get("source", "mysql_username"))
    o_password = "<password><![CDATA[{0}]]></password>".format(
        cfg.get("source", "mysql_password"))
    o_db = "<dbname><![CDATA[{0}]]></dbname>".format(
        cfg.get("source", "mysql_db"))
        
    n_username = "<username><![CDATA[{0}]]></username>".format(
        cfg.get("destination", "mysql_username"))
    n_password = "<password><![CDATA[{0}]]></password>".format(
        cfg.get("destination", "mysql_password"))
    n_db = "<dbname><![CDATA[{0}]]></dbname>".format(
        cfg.get("destination", "mysql_db"))
    
    content = content.replace(o_username, n_username)
    content = content.replace(o_password, n_password)
    content = content.replace(o_db, n_db)

    fh = open(tmp_local, 'w')
    fh.write(content)
    fh.close()
    
    put(tmp_local, os.path.join(
        cfg.get('destination', 'magento_root'), 'app/etc/local.xml'))

def migrate(migration):
    """
    Do migrate. This will subsequently:
    
        - Get a current mysql dump file,
        - transform the dump locally (mainly URL replacements),
        - upload the modified dump,
        - import the modified dump on remote machine,
        - copy the magento installation and
        - adjust local.xml configuration.
    """
    
    if not migration.endswith(".cfg"):
        migration = migration + ".cfg"
    
    cfg.readfp(open(migration))

    get_dump()
    transform_dump()
    upload_dump()
    import_dump()
    copy_remote_magento_installation()
    adjust_local_xml()

