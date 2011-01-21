#!/usr/bin/env python

import smcli
import ConfigParser
import sys
import imaplib
import poplib
import os
import email
import re
import string

email_re = re.compile('[a-zA-Z0-9._+-]+@[a-zA-Z0-9_+-]+\.[a-zA-Z0-9_.+-]+')

configuration = ConfigParser.ConfigParser()

if len(sys.argv) <= 1:
    config_file = 'email2ticket.conf'
else:
    config_file = sys.argv[1]

configuration.read(config_file)

class EmailNotValid(Exception): pass
class ContactNotFound(Exception): pass
class MultipleContactsWithSameEmail(Exception): pass
class NoEmailAddressFound(Exception): pass

def get_contact(email_address):
    m = email_re.search(email_address)
    if m is None:  raise EmailNotValid,email_address
    lookup = email_address[m.start():m.end()]
    contact_list = smcli.typical_search_program(smcli.CONTACT,
                                                ["--email="+lookup],
                                                'search')
    if contact_list == []: raise ContactNotFound,lookup
    if len(contact_list)>1: raise MultipleContactsWithSameEmail,contact_list
    return contact_list[0]

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
    from_is_contact = configuration.getboolean('rules','from_is_contact')
else:
    from_is_contact = True

# Should the body of the email be the description? If not,
# we are relying on their being a default somewhere.
if configuration.has_option('rules','body_is_description'):
    body_is_description = configuration.getboolean('rules','body_is_description')
else:
    body_is_description = True

# Is the subject of the email the title of the service desk ticket?
# If not, there needs to be a default in the config file.
if configuration.has_option('rules','subject_is_title'):
    subject_is_title = configuration.getboolean('rules','subject_is_title')
else:
    subject_is_title = True

# Do you want the call to close immediately? You can't do this simply
# by setting the call status.
if configuration.has_option('rules','close_immediately'):
    close_immediately = configuration.getboolean('rules','close_immediately')
else:
    close_immediately = False


def message_to_ticket(message):
    #print "Handling message:",message
    this_ticket = {}
    if subject_is_title: this_ticket['Title'] = msg['Subject']
    if from_is_contact: this_ticket['Contact'] = get_contact(msg['From'])  
    else:
        m = email.re.search(msg['Subject'])
        if m is not None:
            this_ticket['Contact'] = msg['Subject'][m.start():m.end()]
        else:
            for part in msg.walk():
                m=email_re.search(part)
                if m is None: continue
                this_ticket['Contact'] = get_contact(part[m.start():m.end()])
            if not(this_ticket.has_key('Contact')):
                raise NoEmailAddressFound
    if body_is_description:
        for part in msg.walk():
            if part.get_content_maintype() == "text":
                if part.get_content_subtype() == "plain":
                    this_ticket['Description'] = part.get_payload()
                    break
                if part.get_content_subtype() == "html":
                    # Then it will have to do if nothing better comes along
                    this_ticket['Description'] = part.get_payload()
        # Hope that there was some valid part of that message.
    command_line = []
    for k in this_ticket.keys():
        command_line.append("--"+k+"="+this_ticket[k])
    t=smcli.typical_create_program(smcli.SERVICE_DESK,command_line,'create')
    if close_immediately:
        smcli.typical_update_program(smcli.SERVICE_DESK,["--call-id",t],'close')
    


if protocol[:3] == 'POP':
    if protocol[-1] == 'S' or protocol[-3:] == "SSL":
        if port is None: M = poplib.POP3_SSL(server)
        else:            M = poplib.POP3_SSL(server,port)
    else:
        if port is None: M = poplib.POP3(server)
        else:            M = poplib.POP3(server,port)
    M.user(username)
    M.pass_(password)
    M.list()
    (numMsgs, totalSize) = M.stat()
    for i in range(1, numMsgs + 1):
        (header, msglines, octets) = M.retr(i)
        msg = email.message_from_string(string.join(msglines,"\n"))
        message_to_ticket(msg)
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
    (status,msglist) = M.search(None,'ALL')
    msg_ids = msglist[0].split()
    for msg_id in msg_ids:
        (status,content) = M.fetch(msg_id,"(rfc822)")
        (formatting,tail) = content
        (rfcdesc,rfcdata) = formatting
        msg = email.message_from_string(rfcdata)
        message_to_ticket(msg)



# To-do:
# 1. Confirm that IMAP-based email works.
# 2. Delete messages after we have seen them.
# 3. Don't die on error conditions.
# 4. Improve logging.
# 5. If the first email address doesn't match a contact, try again with
#    other email addresses in the message.
