#!/usr/bin/env python

version = "$Revision: 1509 $"
id = "$Id: service-manager-incident.py 1509 2010-11-18 07:44:17Z gregb $"

######################################################################
#
# The point of this program is so that you can run:
#
#   sm-create-incident.py --description="Something crashed" \
#                         --title="Crash"
#
# ... and have it generate an incident in ServiceManager
#
######################################################################
#
# It looks for a configuration file in the following places:
#   /etc/smwsdl.cfg
#   ~/.smswsdl.cfg
#   ./.smswsdl.cfg
#   $SMWSDL_CONF
#
# The configuration file should look like this:
#
# [connection]
# server=localhost
# ; doesn't default to localhost since it almost definitely won't be
# port=13080
# ; defaults to 13080
# protocol=http
# ; which defaults to http
# username=...
# password=...
#
# [incident defaults]
# Service=...
# AssignmentGroup=...
# Category=...
# Area=...
# Subarea=...
# Urgency=...
# Impact=...
# ;(and so on for any other fields you want to have a default value for)
#
#
######################################################################
#
# However, if the environment variable $SMWSDL_INCIDENT_DEFAULTS (or
# $SMWSDL_DEFAULTS) is set to something other than the string 
# 'incident defaults' then that other section will be looked up.
#
# (The idea behind this feature is that you might have a couple of
# different kinds of incidents you create, so you can run
#  SMWSDL_DEFAULTS=network-problem sm-create-incident.py
# and
#  SMWSDL_DEFAULTS=application-problem sm-create-incident.py
#
######################################################################

import ConfigParser, os, string
from optparse import OptionParser
import logging

config_file_locations = ['/etc/smswsdl.conf',os.path.expanduser('~/.smwsdl.cfg'),'.smwsdl.cfg']
if os.environ.has_key('SMWSDL_CONF'):
    config_file_locations.append(os.environ['SMWSDL_CONF'])

config = ConfigParser.ConfigParser()

files_read = config.read(config_file_locations)
if files_read == []:
    sys.exit("Cannot continue because none of the following files were usable: "+string.join(config_file_locations," "))



######################################################################
# Know what server to connect to (i.e. read the "connection" section):

if config.has_option('connection','server'):
    service_manager_server = config.get('connection','server')
else:
    sys.exit("Server not specified")

if config.has_option('connection','protocol'):
    service_manager_protocol = config.get('connection','protocol')
else:
    service_manager_protocol = 'http'

if config.has_option('connection','port'):
    service_manager_port = config.getint('connection','port')
else:
    service_manager_port = 13080

if config.has_option('connection','password'):
    service_manager_password = config.get('connection','password')
elif config.has_option('connection','pass'):
    service_manager_password = config.get('connection','pass')
else:
    service_manager_password = ''

if config.has_option('connection','username'):
    service_manager_username = config.get('connection','username')
elif config.has_option('connection','user'):
    service_manager_username = config.get('connection','user')
else:
    sys.exit("Username not specified")



######################################################################

# This program requires the python SUDS package. If the import in the
# next line fails, then try
# - sudo apt-get install python-setuptools  or yum install python-setuptools
# - sudo easy_install http://pypi.python.org/packages/2.6/s/suds/suds-0.4-py2.6.egg

logging.basicConfig(level=logging.ERROR)
from suds import WebFault
from suds.client import Client
url = service_manager_protocol + "://" + service_manager_server + ":" + `service_manager_port` + "/SM/7/IncidentManagement.wsdl"
from suds.transport.http import HttpAuthenticated
t = HttpAuthenticated(username=service_manager_username,
                      password=service_manager_password)
client = Client(url,transport=t)

########################################

# This next black magic figures out what fields there are in the
# modelthing instance and turns them into command-line options.

# Firstly, if a field begins with __ then it's python or suds internal
# and not derived from the WSDL.

modelthing = client.factory.create('IncidentModelType')
incident_ticket_fields = filter(lambda x: x[0:1]!='_',dir(modelthing.instance))

parser = OptionParser(usage="usage: %prog --TicketFieldName=Value ...",
                      version=version)


def camel2unix(x):
    answer = x[0].lower()
    for i in range(1,len(x)-1):
        answer = answer + x[i].lower()
        if x[i].islower() and x[i+1].isupper():
            answer = answer + '-'
        if (i+2<len(x)) and x[i].isupper() and x[i+1].isupper() and x[i+2].islower():
            answer = answer + '-'
    answer = answer + x[-1].lower()
    return answer

if os.environ.has_key('SMWSDL_INCIDENT_DEFAULTS'):
    section_to_use = os.environ["SMWSDL_INCIDENT_DEFAULTS"]
elif os.environ.has_key('SMWSDL_DEFAULTS'):
    section_to_use = os.environ["SMWSDL_DEFAULTS"]
else:
    section_to_use = 'incident defaults'

for ticket_field in incident_ticket_fields:
    helptext = "Set the "+ticket_field+" field in the created ticket."
    unixified = camel2unix(ticket_field)
    parser.add_option("--"+unixified,dest=ticket_field,type='string',
                      action="store",
                      help=helptext)
    for config_file_option_name in [ticket_field,unixified]:
        if config.has_option(section_to_use,config_file_option_name):
            parser.set_default(ticket_field,config.get(section_to_use,config_file_option_name))
                      
(options,args) = parser.parse_args()


# To-do: cope better with array arguments such as description. At the moment
# it works, but it's kind of by luck because ServiceManager will promote a
# string to an array.
#
# Neat would be to make sure that numbers and dates get validated at the client
# end rather than hammering ServiceManager, but it will do for now.

for ticket_field in options.__dict__.keys():
    modelthing.instance.__dict__[ticket_field] = options.__dict__[ticket_field]
    
answer = client.service.CreateIncident(modelthing)

incident_id = answer.model.instance.IncidentID.value
print incident_id

