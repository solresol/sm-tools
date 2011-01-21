#!/usr/bin/env python

import ConfigParser
import sys
import imaplib
import poplib
import os
import email
import re
import string
import time
import logging

from suds import WebFault
from suds.client import Client

import suds.transport.http

if os.environ.has_key("DEBUG"):
  logging.basicConfig(level=logging.DEBUG)
else:
  logging.basicConfig(level=logging.ERROR)

email_re = re.compile('[a-zA-Z0-9._+-]+@[a-zA-Z0-9_+-]+\.[a-zA-Z0-9_.+-]+')

######################################################################

command_line_args = sys.argv

run_once = False
debug = False
dry_run = False

if 'once' in command_line_args:
    run_once = True
    command_line_args.remove('once')

if 'debug' in command_line_args:
    debug = True
    command_line_args.remove('debug')

if 'test' in command_line_args:
    dry_run = True
    command_line_args.remove('test')

if len(sys.argv) <= 1:
    config_file = 'email2ticket.conf'
else:
    config_file = sys.argv[1]

configuration = ConfigParser.ConfigParser()
files_read = configuration.read(config_file)

if len(files_read) < 1:
    sys.exit("Could not read " + config_file + "\n")

######################################################################

servicemanager_connections = {}

class EmailNotValid(Exception): pass
class ContactNotFound(Exception): pass
class MultipleContactsWithSameEmail(Exception): pass
class NoEmailAddressFound(Exception): pass

class HPServiceManager:
    def __init__(self,name,server,username,password,others,protocol="http",port=13080,
                 servicedesk_wsdl_path="/SM/7/ServiceDesk.wsdl",
                 contacts_wsdl_path="/SM/7/ConfigurationManagement.wsdl"):
        self.__name = name
        self.__server = server
        self.__username = username
        self.__password = password
        self.__protocol = protocol
        self.__port = port
        self.__servicedesk_wsdl_path = servicedesk_wsdl_path
        self.__contacts_wsdl_path = contacts_wsdl_path
        self.__options = {}
        self.__options.update(others)
        self.__make_configmgmt_connection()
        self.__make_servicedesk_connection()

    def __make_servicedesk_connection(self):
        self.__servicedesk_transport = suds.transport.http.HttpAuthenticated(username=self.__username,password=self.__password)
        self.__servicedesk_wsdl = self.__protocol + "://" + self.__server + ":" + `self.__port` + self.__servicedesk_wsdl_path
        print "Initiating service desk SOAP connection"
        self.__service_desk_client = Client(self.__servicedesk_wsdl,
                                            transport=self.__servicedesk_transport)
        #print self.__service_desk_client
        self.__new_interaction = self.__service_desk_client.factory.create("InteractionModelType")


    def __make_configmgmt_connection(self):
        self.__configmgmt_transport = suds.transport.http.HttpAuthenticated(username=self.__username,password=self.__password)
        self.__configmgmt_wsdl = self.__protocol + "://" + self.__server + ":" + `self.__port` + self.__contacts_wsdl_path
        print "Initiating config mgmt SOAP connection"
        self.__contact_lookup_client = Client(self.__configmgmt_wsdl,
                                              transport=self.__configmgmt_transport)
        self.__lookup_email = self.__contact_lookup_client.factory.create('ContactModelType')
        #print self.__contact_lookup_client


    def lookup_contact(self,email_address):
        m = email_re.search(email_address)
        if m is None:  raise EmailNotValid,email_address
        lookup = email_address[m.start():m.end()]
        print "Asked to look up email address",lookup
        contact_list = []
        self.__lookup_email.instance.Email = lookup
        result = self.__contact_lookup_client.service.RetrieveContactKeysList(self.__lookup_email)
        contact_list_raw = result.keys
        if contact_list_raw == []: raise ContactNotFound,lookup
        if not(contact_list_raw[0].ContactName.__dict__.has_key("value")):
            #print self.__lookup_email
            #print "Funny return result from query:",contact_list_raw
            raise ContactNotFound,lookup
        contact_list = []
        #print contact_list_raw
        for c in contact_list_raw:
            print "Found",c.ContactName.value
            contact_list.append(c.ContactName.value)
        if len(contact_list_raw)>1: raise MultipleContactsWithSameEmail,contact_list
        return contact_list[0]

    def create_ticket_from_message(self,message):
        for name in self.__new_interaction.instance.__dict__.keys():
            if name[0] != "_":
                if self.__options.has_key(name):
                    self.__new_interaction.instance.__dict__[name].value = self.__options[name]
        try:
            self.__new_interaction.instance.ContactName.value = self.lookup_contact(message['From'])
        except ContactNotFound:
            if self.__options.has_key('servicemanager_default_contact'):
                self.__new_interaction.instance.ContactName.value = self.__options['servicemanager_default_contact']
            else:
                self.__new_interaction.instance.ContactName.value = ""
        except MultipleContactsWithSameEmail,choices:
            # I should also log that this happened.
            choices.sort()
            self.__new_interaction.instance.ContactName.value = choices[0]
        self.__new_interaction.instance.Title.value = message['Subject']
        description = None
        for part in msg.walk():
            if part.get_content_maintype() == "text":
                if part.get_content_subtype() == "plain":
                    description = part.get_payload()
                    break
                if part.get_content_subtype() == "html":
                    # Then it will have to do if nothing better comes along
                    description = part.get_payload()
        # if description is None, what should we do?
        if description is None: description = "<No text or html part found in the source email>"
        self.__new_interaction.instance.Description.value = description
        # Now to do attachments.
        print self.__new_interaction
        

######################################################################

mail_connections = {}


class MailConnectionRefiredTooSoon(Exception): pass

class POPConnection:
    def __init__(self,server,username,password,protocol,port=None):
        if protocol[-1] == 'S' or protocol[-3:] == "SSL":
            if port is None: M = poplib.POP3_SSL(server)
            else:            M = poplib.POP3_SSL(server,port)
        else:
            if port is None: M = poplib.POP3(server)
            else:            M = poplib.POP3(server,port)
        M.user(username)
        M.pass_(password)
        self.M = M
    def do_messages(self,servicemanager):
        self.M.list()
        (numMsgs, totalSize) = self.M.stat()
        for i in range(1, numMsgs + 1):
            (header, msglines, octets) = self.M.retr(i)
            msg = email.message_from_string(string.join(msglines,"\n"))
            servicemanager.create_ticket_from_message(msg)

    def disconnect(self):
        self.M.quit()

class IMAPConnection:
    def __init__(self,server,username,password,protocol,port=None):
        if protocol[-1] == "S" or protocol[-3:] == "SSL":
            if port is None: M = imaplib.IMAP4_SSL(server)
            else:            M = imaplib.IMAP4_SSL(server,port)
        else:
            if port is None: M = imaplib.IMAP4(server)
            else:            M = imaplib.IMAP4(server,port)
        M.login(username,password)
        self.M = M
    def do_messages(self,servicemanager):
        self.M.select()
        (status,msglist) = self.M.search(None,'ALL')
        msg_ids = msglist[0].split()
        for msg_id in msg_ids:
            (status,content) = self.M.fetch(msg_id,"(rfc822)")
            (formatting,tail) = content
            (rfcdesc,rfcdata) = formatting
            msg = email.message_from_string(rfcdata)
            servicemanager.create_ticket_from_message(msg)

    def disconnect(self):
        self.M.close()
        self.M.logout()

class MailConnection:
    def __init__(self,connection_name,protocol,server,username,password,port=None,reconnect_each_time=False,minimum_idle=0):
        self.__connection_name = connection_name
        self.__protocol = protocol.upper()
        self.__username = username
        self.__password = password
        self.__server = server
        self.__reconnect_each_time = reconnect_each_time
        self.__minimum_idle = minimum_idle
        self.__connection = None
        self.__last_usage = 0
        self.__port = port

    def idle_time_remaining(self,when=None):
        """Return the number of seconds we must sleep before we can fire again. Negative numbers mean OK to fire"""
        if when is None: when = time.time()
        return (self.__last_usage + self.__minimum_idle) - when

    def connect(self):
        if self.__connection is not None: return
        if self.__protocol[:3] == 'POP':
            print "Making POP connection to ",self.__server,"as",self.__username,"with password",self.__password,"using",self.__protocol,"on port",self.__port
            self.__connection = POPConnection(self.__server,self.__username,self.__password,self.__protocol,self.__port)
        elif self.__protocol[:4] == "IMAP":
            print "Making IMAP connection to ",self.__server,"as",self.__username,"with password",self.__password,"using",self.__protocol,"on port",self.__port
            self.__connection = IMAPConnection(self.__server,self.__username,self.__password,self.__protocol,self.__port)
        print "Connection object is now",self.__connection

    def inject_new_messages(self,servicemanager):
        print "Asked to do new messages for",self.__connection_name
        if self.idle_time_remaining() > 0: raise MailConnectionRefiredTooSoon
        self.__last_usage = time.time()
        self.connect()
        print "Doing messages for",self.__connection_name
        self.__connection.do_messages(servicemanager)
        if self.__reconnect_each_time:
            print "Disconnecting from",self.__connection_name
            self.__connection = None


for section in configuration.sections():
    # Create the mail account
    protocol = configuration.get(section,'mail_protocol')
    username = configuration.get(section,'mail_username')
    password = configuration.get(section,'mail_password')
    server = configuration.get(section,'mail_server')
    if configuration.has_option(section,'mail_port'):
        port = configuration.getint(section,'mail_port')
    else:
        port = None

    if configuration.has_option(section,'reconnect_each_time'):
        reconnect_each_time = configuration.getboolean(section,'reconnect_each_time')
    else:
        reconnect_each_time = False

    if configuration.has_option(section,'sleep_between_polls'):
        sleep_between_polls = configuration.getfloat(section,'sleep_between_polls')
    else:
        sleep_between_polls = 15
    mail_connections[section] = MailConnection(section,protocol,server,username,password,port,reconnect_each_time,sleep_between_polls)

    # Create the servicemanager connection
    username = configuration.get(section,'servicemanager_username')
    server = configuration.get(section,'servicemanager_server')

    if configuration.has_option(section,"servicemanager_password"):
        password = configuration.get(section,'servicemanager_password')
    else:
        password = ""

    if configuration.has_option(section,"servicedesk_wsdl"):
        servicedesk_wsdl = configuration.get(section,'servicedesk_wsdl')
    else:
        servicedesk_wsdl = "/SM/7/ServiceDesk.wsdl"

    if configuration.has_option(section,"contacts_wsdl"):
        contacts_wsdl = configuration.get(section,'contacts_wsdl')
    else:
        contacts_wsdl = "/SM/7/ConfigurationManagement.wsdl"

    if configuration.has_option(section,"servicemanager_protocol"):
        protocol = configuration.get(section,'servicemanager_protocol')
    elif configuration.has_option(section,"servicemanager_port"):
        port = configuration.getint(section,"servicemanager_port")
        if port == 13080:
            protocol = "http"
        elif port == 13443:
            protocol = "https"
        else:
            protocol = "http"
    else:
        protocol = "http"

    if configuration.has_option(section,"servicemanager_port"):
        port = configuration.getint(section,"servicemanager_port")
    elif protocol == "http":
        port = 13080
    elif protocol == "https":
        port = 13443
    else:
        port = 13080

    servicemanager_connections[section] = HPServiceManager(section,server,username,password,configuration.items(section),protocol,port,servicedesk_wsdl,contacts_wsdl)

finished = False
while not(finished):
    if run_once: finished = True
    wait_time = None
    for scenario in mail_connections.keys():
        mail_server = mail_connections[scenario]
        delay_required = mail_server.idle_time_remaining()
        print scenario,"asked for a delay of",delay_required,"seconds"
        if delay_required < 0:
            wait_time = 0
            continue
        if wait_time is None:
            wait_time = delay_required
            continue
        if delay_required < wait_time: 
            wait_time = delay_required
    print "I have to wait",wait_time,"seconds"
    time.sleep(wait_time)
    for scenario in mail_connections.keys():
        mail_server = mail_connections[scenario]
        delay_required = mail_server.idle_time_remaining()
        if delay_required < 0:
            mail_server.inject_new_messages(servicemanager_connections[scenario])
        # Test out email address lookup



sys.exit(0)








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
        # Hope that there was some valid part of that message.
    command_line = []
    for k in this_ticket.keys():
        command_line.append("--"+k+"="+this_ticket[k])
    t=smcli.typical_create_program(smcli.SERVICE_DESK,command_line,'create')
    if close_immediately:
        smcli.typical_update_program(smcli.SERVICE_DESK,["--call-id",t],'close')
    



# To-do:
# 1. Confirm that IMAP-based email works.
# 2. Delete messages after we have seen them.
# 3. Don't die on error conditions.
# 4. Improve logging.
# 5. If the first email address doesn't match a contact, try again with
#    other email addresses in the message.
