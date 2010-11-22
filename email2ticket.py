#!/usr/bin/env python

import smcli
import ConfigParser
import sys
import imaplib
import poplib
import os
import email
import getpass
import fnmatch

configuration = ConfigParser.ConfigParser()

if len(sys.argv) <= 1:
    config_file = 'email2ticket.conf'
else:
    config_file = sys.argv[1]

# Both this program and smcli will share the same config file.
configuration.read(config_file)
application = smcli.smwsdl(smcli.SERVICE_DESK,config_file)

protocol = configuration.get('mail','protocol').upper()
server = configuration.get('mail','server')
username = configuration.get('mail','username')
password = configuration.get('mail','password')
if configuration.has_option('mail','port'):
    port = configuration.get('mail','port')
else:
    port = None

# Do we receive email directly from contacts? If so, we use their
# email address as the key to creating the ticket.
# If not, we look for the first email address in the body
# or subject of the email.
if configuration.has_option('rules','from_is_contact'):
    from_is_contact = configuration.getbool('rules','from_is_contact')
else:
    from_is_contact = True

# Should the body of the email be the description? If not,
# we are relying on their being a default somewhere.
if configuration.has_option('rules','body_is_description'):
    body_is_description = configuration.getbool('rules','body_is_description')
else:
    body_is_description = True

# Is the subject of the email the title of the service desk ticket?
# If not, there needs to be a default in the config file.
if configuration.has_option('rules','subject_is_title'):
    body_is_description = configuration.getbool('rules','subject_is_title')
else:
    body_is_description = True

# One day -- add a Bayesian filter to figure out all the remaining
# fields.

if protocol[:3] == 'POP':
    if protocol[-1] == 'S' or protocol[-3:] == "SSL":
        if port is None: M = poplib.POP3_SSL(server)
        else:            M = poplib.POP3_SSL(server,port)
    else:
        if port is None: M = poplib.POP3(server)
        else:            M = poplib.POP3(server,port)
    M.user(username)
    M.pass_(password)
    # Finish this bit
elif protocol[:4] == "IMAP":
    if protocol[-1] == "S" or protocol[-3:] == "SSL":
        if port is None: M = imaplib.IMAP4_SSL(server)
        else:            M = imaplib.IMAP4_SSL(server,port)
    else:
        if port is None: M = imaplib.IMAP4(server)
        else:            M = imaplib.IMAP4(server,port)
    M.login(username,password)
    M.select()
    typ, data = M.search(None,'ALL')
    # Finish this bit too.
    
    
