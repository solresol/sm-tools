#!/usr/bin/env python

# $Id$
version = '$Revision$'
# Usually you'll just invoke this as
#  sm-update-incident.py --incident-id=IM123456 --status="Work In Progress"
#
# See sm-create-incident.py for what files it reads and what
# environment it looks at.  sm-update-incident.py does not use
# the 'incident defaults' section.


# This program was developed by Greg Baker <gregb@ifost.org.au> (c) 2010

import smwsdl

smwsdl.typical_update_program(smwsdl.INCIDENT,'IncidentModelType','UpdateIncident')
    

