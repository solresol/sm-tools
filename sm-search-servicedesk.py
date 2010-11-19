#!/usr/bin/env python

# $Id$

version = '$Revision$'

# This program was developed by Greg Baker <gregb@ifost.org.au> (c) 2010

import smwsdl

smwsdl.typical_search_program(smwsdl.SERVICE_DESK,
                              'InteractionModelType',
                              'RetrieveInteractionKeysList',
                              'CallID')
