#!/usr/bin/env python

version = "$Revision: 1509 $"
id = "$Id: service-manager-incident.py 1509 2010-11-18 07:44:17Z gregb $"

# The point of this program is so that you can run:
#
#   sm-create-incident.py --description="Something crashed" \
#                         --title="Crash"
#
# ... and have it generate an incident in ServiceManager

######################################################################
#
# There are a few things which can be configured:
#  - ticket fields, and what defaults there are
#  - username, password, url, etc.


default_ticket_values = {    
    'Service':  'Reach Network',
    'AssignmentGroup': 'Network',
    'Category': 'incident',
    'Area': 'hardware',
    'Subarea': 'hardware failure',
    'Urgency': '1 - Critical',
    'Impact': '2 - Site/Dept'
    }

# To-do: have this stuff in a config file.

######################################################################

service_manager_protocol = 'http'  ;# can be https
service_manager_server = 'tmhred56'
service_manager_port = 13080

# These next two lines are the name and password of a ServiceManager
# operator account.
service_manager_username = 'wsdl'
service_manager_password = 'V598ouaj'
#
# To-do: instead of hard-coding username+password here, read
# it from the user's home directory (which makes sense for a service)
# and/or from stdin.









######################################################################
# That's the last of the configurable things. It's just program code
# from here on.
######################################################################


# This program requires the python SUDS package. If the import in the
# next line fails, then try
# - sudo apt-get install python-setuptools  or yum install python-setuptools
# - sudo easy_install http://pypi.python.org/packages/2.6/s/suds/suds-0.4-py2.6.egg

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

from optparse import OptionParser
import string
parser = OptionParser(usage="usage: %prog --TicketFieldName=Value ...",
                      version=version)


def is_camel_case(x):
    for i in range(1,len(x)-1):
        if x[i].islower() and x[i+1].isupper():
            return True
    return False

def camel2unix(x):
    answer = "--" + x[0].lower()
    for i in range(1,len(x)-1):
        answer = answer + x[i].lower()
        if x[i].islower() and x[i+1].isupper():
            answer = answer + '-'
        if (i+2<len(x)) and x[i].isupper() and x[i+1].isupper() and x[i+2].islower():
            answer = answer + '-'
    answer = answer + x[-1].lower()
    return answer

for ticket_field in incident_ticket_fields:
    helptext = "Set the "+ticket_field+" field in the created ticket."
    parser.add_option(camel2unix(ticket_field),
                      dest=ticket_field,
                      type='string',
                      action="store",
                      help=helptext)
    if default_ticket_values.has_key(ticket_field):
        parser.set_default(ticket_field,default_ticket_values[ticket_field])
                      
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

