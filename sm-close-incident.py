#!/usr/bin/env python

# $Id$
version = '$Revision$'
# Usually you'll just invoke this as
#  sm-close-incident.py --incident-id=IM123456
#
# See sm-create-incident.py for what files it reads and what
# environment it looks at. sm-close-incident.py does not use
# the 'incident defaults' section.

import smwsdl

smwsdl.typical_update_program(smwsdl.INCIDENT,'IncidentModelType','CloseIncident',uses_values=False)












    

