#!/usr/bin/env python

# $Id$
version = '$Revision$'
# Usually you'll just invoke this as
#  sm-resolve-incident.py --incident-id=IM123456 
#
# See sm-create-incident.py for what files it reads and what
# environment it looks at. sm-create-incident.py does not use
# the 'incident defaults' section.

import smwsdl

web_service = smwsdl.smwsdl(smwsdl.INCIDENT)

from optparse import OptionParser

parser = OptionParser(usage="usage: %prog --incident-id=...",version=version)

web_service.add_to_command_line_parser(parser,"IncidentModelType",provide_defaults=False)

(options,args) = parser.parse_args()

new_incident = web_service.create_soap_object("IncidentModelType",options.__dict__)

answer = web_service.invoke('ResolveIncident',new_incident)

import sys
for m in answer.messages.message:
    sys.stderr.write(m.value+'\n')
    

