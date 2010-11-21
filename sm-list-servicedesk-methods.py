#!/usr/bin/env python

# This program was developed by Greg Baker <gregb@ifost.org.au> (c) 2010

import smcli

web_service = smwsdl.smwsdl(smwsdl.SERVICE_DESK)

web_service.print_available_methods()
