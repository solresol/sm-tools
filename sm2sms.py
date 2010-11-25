#!/usr/bin/env python

import smcli
import valuesms
import re
import sys
import string

is_mobile_number = re.compile('^04[0-9 -]+$')
pages = smcli.typical_search_program(smcli.EVENTOUT,
                                     ['--evtype=page'],
                                     'search')

for page in pages:
    p = smcli.typical_retrieve_program(smcli.EVENTOUT,
                                       ['--evsysseq',page],
                                       'retrieve'
                                       )
    sep = p['Evsepchar']
    data = p['Evfields'].split(sep)
    telalert = data[0]
    destination=data[4]
    message = data[8]
    destmatch = is_mobile_number.match(destination)
    if destmatch is None:
        # Perhaps destination is a contact?
        c = smcli.typical_retrieve_program(smcli.CONTACT,
                                           ['--contact-name',c],
                                           'retrieve'
                                           )
        print "Unfinished, untested code."
        print "Figure out what field(s) to use from the following"
        print c
        sys.exit(1)
    phone_number = filter(lambda l: l in string.digits,destination)
    acknum=valuesms.sendsms(phone_number,message)
    print "Message",message,"sent to",phone_number,"ack code",acknum
    smcli.typical_delete_program(smcli.EVENTOUT,
                                 ['--evsysseq',page],
                                 'delete')
                                    
