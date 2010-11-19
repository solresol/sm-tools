#!/usr/bin/env python

# $Id$
version = '$Revision$'
# Usually you'll just invoke this as
#  sm-reopen-incident.py --incident-id=IM123456 
#
# See sm-create-incident.py for what files it reads and what
# environment it looks at. sm-open-incident.py does not use
# the 'incident defaults' section.

import smwsdl

smwsdl.typical_update_program(smwsdl.INCIDENT,'IncidentModelType',
                              'ReopenIncident',uses_values=True)


    

