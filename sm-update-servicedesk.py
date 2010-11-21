#!/usr/bin/env python

# $Id$
version = '$Revision$'
# Usually you'll just invoke this as
#  sm-update-servicedesk.py --servicedesk-id=IM123456 --status="Work In Progress"
#
# See sm-create-servicedesk.py for what files it reads and what
# environment it looks at.  sm-update-servicedesk.py does not use
# the 'servicedesk defaults' section.


# This program was developed by Greg Baker <gregb@ifost.org.au> (c) 2010

import smcli

smwsdl.typical_update_program(smwsdl.SERVICE_DESK,
                              'InteractionModelType','UpdateInteraction')
    

