#!/usr/bin/env python

# This program was developed by Greg Baker <gregb@ifost.org.au> (c) 2010

import smcli

web_service = smcli.smwsdl(smcli.INCIDENT)

web_service.print_available_methods()
