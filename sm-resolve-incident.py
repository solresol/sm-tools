#!/usr/bin/env python

# $Id$
version = '$Revision$'
# Usually you'll just invoke this as
#  sm-resolve-incident.py --incident-id=IM123456 
#
# See sm-create-incident.py for what files it reads and what
# environment it looks at. sm-resolve-incident.py does not use
# the 'incident defaults' section.

# This program was developed by Greg Baker <gregb@ifost.org.au> (c) 2010

import smcli

smwsdl.typical_update_program(smwsdl.INCIDENT,'IncidentModelType',
                              'ResolveIncident',uses_values=False)


    

