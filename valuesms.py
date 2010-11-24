#!/usr/bin/env python

import urllib
import urllib2
import sys
import string
import re

class SendFailureException(Exception): pass

def sendsms(phone,message,username='SMS08836',password='6db1cb25',config_file=None):
    # Username and password should be in a config file; then I can get rid of those
    # arguments
    if config_file is not None: sys.exit("Sorry, haven't implemented reading username and password from config file yet")
    if type(phone)==type([]):
        phone = string.join(phone,',')
    form = {'u': username
            'p': password
            'd': phone,
            'm': message
            }
    url = "http://www.valuesms.com/msg.php?" + urllib.urlencode(form)
    result = urllib2.urlopen(url)
    good_result = re.compile("^ACK (\d+)")
    content = result.read()
    m = good_result.search(content)
    if m is None:
        raise SendFailureException,content
    return int(content[m.group(0)])
