#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Replace 'web/secure/base_url' and 'web/unsecure/base_url' in magento MySQL dumps.

Example usage:

    ./mgt-adjust-mysqldump.py -d mysqldump.server.dev.sql \ 
        -b http://localhost:8888/magento/ \
        -o mysqldump.chiba.dev.sql

"""

import sys, optparse, re, os

def replace_base_url(content, key, value, verbose=False):
    """
    Replace the value of key, e.g. 'web/secure/base_url' with a
    new value, e.g. the new target base_url.
    Returns the modified content.
    """
    pattern = re.compile(r"'{0}','([^']*)'".format(key))
    matches = [m for m in pattern.findall(content)]
    if not len(matches) == 1:
        raise Exception("This dump seems to be broken. We have more than one '{0}' option.".format(key))
    current_url = matches[0]
    if verbose:
        print >> sys.stderr, 'replacing {0}: {1} ==> {2}'.format(key, current_url, value)
    content = content.replace("'{0}','{1}'".format(key, current_url), 
        "'{0}','{1}'".format(key, value))
    return content

def main():
    
    parser = optparse.OptionParser()
    parser.add_option("-d", "--dumpfile", dest="dumpfile",
        action="store", help="the MySQL dump file", metavar="DUMPFILE")
    parser.add_option("-u", "--unsecure-base", dest="unsecure_base_url",
        action="store", help="the new unsecure base url", metavar="UNSECURE_BASE_URL")
    parser.add_option("-s", "--secure-base", dest="secure_base_url",
        action="store", help="the new secure base url", metavar="SECURE_BASE_URL")
    parser.add_option("-b", "--base", dest="base_url",
        action="store", help="the new secure and unsecure base url", metavar="BASE_URL")
    parser.add_option("-o", "--out", dest="out_file",
        action="store", help="dump the adjustments to OUTFILE", metavar="OUTFILE")
    parser.add_option("-v", "--verbose", dest="verbose",
        action="store_true", help="be verbose")

    (options, args) = parser.parse_args()
    
    if not (options.dumpfile and (
        options.base_url or options.secure_base_url and options.unsecure_url)):
        print >> sys.stderr,  "We need a dumpfile (-d) and a base URL (-b) or secure (-s) and unsecure (-u) base URLs."
        return 0
    
    try:
        fp = open(options.dumpfile, 'r')
        original_content = fp.read()
        fp.close()
    except IOError, ioe:
        print >> sys.stderr, 'IO error. {0}'.format(ioe)
        return 1
    
    if options.dumpfile and options.base_url:
        try:
            updated_dump = replace_base_url(original_content, 'web/unsecure/base_url', options.base_url, options.verbose)
            updated_dump = replace_base_url(updated_dump, 'web/secure/base_url', options.base_url, options.verbose)
            if options.out_file:
                if os.path.exists(options.out_file):
                    should_overwrite = raw_input('Overwrite existing file? [yN]: ')
                    if not should_overwrite in ('Y', 'y'):
                        print >> sys.stderr, "Nothing changed."
                        return 0
                fp = open(options.out_file, 'w')
                fp.write(updated_dump)
                fp.close()
                print >> sys.stderr, "Wrote adjusted dump to {0}".format(options.out_file)
            else:
                print updated_dump
        except IOError, ioe:
            print >> sys.stderr, "Could not open file. {0}".format(ioe)

    if options.dumpfile and options.secure_base_url and options.unsecure_base_url:
        try:
            updated_dump = replace_base_url(original_content, 'web/unsecure/base_url', 
                options.unsecure_base_url, options.verbose)
            updated_dump = replace_base_url(updated_dump, 'web/secure/base_url', options.secure_base_url,
                options.verbose)
            if options.out_file:
                if os.path.exists(options.out_file):
                    should_overwrite = raw_input('Overwrite existing file? [yN]: ')
                    if not should_overwrite in ('Y', 'y'):
                        print >> sys.stderr, "Nothing changed."
                        return 0
                fp = open(options.out_file, 'w')
                fp.write(updated_dump)
                fp.close()
                print >> sys.stderr, "Wrote adjusted dump to {0}".format(options.out_file)
            else:
                print updated_dump
        except IOError, ioe:
            print >> sys.stderr, "Could not open file. {0}".format(ioe)

if __name__ == '__main__':
    sys.exit(main())

