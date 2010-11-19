#!/usr/bin/env python

import smwsdl

web_service = smwsdl.smwsdl(smwsdl.INCIDENT)

web_service.print_available_methods()
