#!/usr/bin/env python

import ConfigParser
import sys
import os
import email
import re
import string
import time
import logging
import sys
import fnmatch

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

config_file = '/etc/smprocmail.conf'
configuration = ConfigParser.ConfigParser()
files_read = configuration.read(['/etc/smprocmail.conf','.smprocmail.conf'])

if len(files_read) < 1:
    sys.exit("Could not read any config files")

######################################################################

class EmailNotValid(Exception): pass
class ContactNotFound(Exception): pass
class MultipleContactsWithSameEmail(Exception): pass

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
            self.__new_interaction.instance.ReportedByContact.value = self.lookup_contact(message['From'])
        except ContactNotFound:
            if self.__options.has_key('default_contact'):
                print self.__new_interaction.instance.__dict__.keys()
                self.__new_interaction.instance.ReportedByContact.value = self.__options['default_contact']
            else:
                self.__new_interaction.instance.ReportedByContact.value = ""
        except MultipleContactsWithSameEmail,choices:
            # I should also log that this happened.
            choices.sort()
            self.__new_interaction.instance.ReportedByContact.value = choices[0]
        if self.__new_interaction.instance.__dict__.has_key('Title'):
            self.__new_interaction.instance.Title.value = message['Subject']
            # I dunno what happens if there isn't a title.
        description = None
        part_pos = 0
        used_part_pos = None
        for part in message.walk():
            part_pos = part_pos + 1
            if part.get_content_maintype() == "text":
                if part.get_content_subtype() == "plain":
                    description = part.get_payload()
                    used_part_pos = part_pos
                    break
                if part.get_content_subtype() == "html":
                    # Then it will have to do if nothing better comes along
                    description = part.get_payload()
                    used_part_pos = part_pos
        # if description is None, what should we do?
        if description is None: description = "<No text or html part found in the source email>"
        self.__new_interaction.instance.Description.value = description

        # Now to do attachments ... and then actually invoke CreateInteraction
        part_pos = 0
        for part in message.walk():
            part_pos = part_pos + 1
            if part_pos == used_part_pos: continue
            print "Part",part_pos,part.get_filename()
            print part.as_string()
            print dir(part)

        print `self.__service_desk_client.service.__dict__.keys()`
        answer = self.__service_desk_client.service.CreateInteraction(self.__new_interaction)
        for m in answer.messages.message():
            sys.stderr.write(m.value + "\n")
            # Will have to log that somewhere we can see
        
        print `answer.model.instance`

        #print self.__new_interaction
        #attachments = self.__service_desk_client.factory.create('AttachmentsType')
        #print attachments
        

######################################################################

message = email.message_from_file(sys.stdin)

section = None
for section_pattern in configuration.sections():
    if fnmatch.fnmatch(message['To'],section_pattern):
        section = section_pattern
        continue

if section is None:
    # Shrug. Hope for the best.
    section = message['To']

username = configuration.get(section,'username')
server = configuration.get(section,'server')

if configuration.has_option(section,"password"):
    password = configuration.get(section,'password')
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

if configuration.has_option(section,"protocol"):
    protocol = configuration.get(section,'protocol')
elif configuration.has_option(section,"port"):
    port = configuration.getint(section,"port")
    if port == 13080:
        protocol = "http"
    elif port == 13443:
        protocol = "https"
    else:
        protocol = "http"
else:
    protocol = "http"

if configuration.has_option(section,"port"):
    port = configuration.getint(section,"port")
elif protocol == "http":
    port = 13080
elif protocol == "https":
    port = 13443
else:
    port = 13080

servicemanager_connection = HPServiceManager(section,server,username,password,configuration.items(section),protocol,port,servicedesk_wsdl,contacts_wsdl)

servicemanager_connection.create_ticket_from_message(message)

# If we want to close it immediately.
#    smcli.typical_update_program(smcli.SERVICE_DESK,["--call-id",t],'close')
