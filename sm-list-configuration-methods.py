#!/usr/bin/env python

# This program was developed by Greg Baker <gregb@ifost.org.au> (c) 2010

import smwsdl

web_service = smwsdl.smwsdl(smwsdl.CONFIGURATION)

web_service.print_available_methods()
