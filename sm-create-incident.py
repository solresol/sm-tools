#!/usr/bin/env python

version = "$Revision: 1509 $"
id = "$Id: service-manager-incident.py 1509 2010-11-18 07:44:17Z gregb $"

import smwsdl
from optparse import OptionParser


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


web_service = smwsdl.smwsdl(smwsdl.INCIDENT)

parser = OptionParser(usage="usage: %prog --TicketFieldName=Value ...",
                      version=version)

web_service.add_to_command_line_parser(parser,"IncidentModelType")

(options,args) = parser.parse_args()

new_incident = web_service.create_soap_object("IncidentModelType",options.__dict__)

answer = web_service.invoke('CreateIncident',new_incident)

incident_id = answer.model.instance.IncidentID.value
print incident_id

