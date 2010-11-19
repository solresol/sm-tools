#!/usr/bin/env python

# $Id$
version = '$Revision$'
# Usually you'll just invoke this as
#
#  sm-close-incident.py --incident-id=IM123456 \
#    --solution=... closure-code="Automatically Closed"
#
# You aren't forced to put a solution nor a closure code, but 
# if you re-open it, you will be forced to if you don't do it 
# now.
#
# You can of course update other fields at the same time.
#
# See sm-create-incident.py for what files it reads and what
# environment it looks at. sm-close-incident.py does not use
# the 'incident defaults' section.

import smwsdl

smwsdl.typical_update_program(smwsdl.INCIDENT,'IncidentModelType','CloseIncident',uses_values=True)












    

