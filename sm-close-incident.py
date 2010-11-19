#!/usr/bin/env python

# $Id$
version = '$Revision$'
# Usually you'll just invoke this as
#  sm-close-incident.py --incident-id=IM123456
#
# See sm-create-incident.py for what files it reads and what
# environment it looks at.

import smwsdl

web_service = smwsdl.smwsdl(smwsdl.INCIDENT)

from optparse import OptionParser

parser = OptionParser(usage="usage: %prog --incident-id=...",version=version)

web_service.add_to_command_line_parser(parser,"IncidentModelType")

(options,args) = parser.parse_args()

new_incident = web_service.create_soap_object("IncidentModelType",options.__dict__)

answer = web_service.invoke('CloseIncident',new_incident)

incident_id = answer.model.instance.IncidentID.value
print incident_id

