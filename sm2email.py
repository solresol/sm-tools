#!/usr/bin/env python

import smtplib
import ConfigParser
import email
import smcli
import sys
from email.MIMEText import MIMEText

my_config = ConfigParser.ConfigParser()
read_ok = my_config.read(['/etc/sm2email.conf'])
if read_ok == []:
    sys.exit("Couldn't read sm2email.conf")

smtp_server = my_config.get('smtp','server')
if my_config.has_option('smtp','port'):
    smtp_port = my_config.getint('smtp','port')
else:
    smtp_port = 25
# Perhaps should add option for local_hostname and timeout?

from_address = my_config.get('smtp','from_address')

mail_connection = smtplib.SMTP(smtp_server,smtp_port)

outgoings = smcli.typical_search_program(smcli.EVENTOUT,
                                         ['--evtype=email'],
                                         'search')

for evsys in outgoings:
    e = smcli.typical_retrieve_program(smcli.EVENTOUT,
                                       ['--evsysseq',evsys],
                                       'retrieve'
                                       )
    try:
     sep = e['Evsepchar']
    except:
     sep = '^'
    data = e['Evfields'].split(sep)
    dest_email = data[0]
    source = data[1]
    contact = data[2]
    subject = data[3]
    body = data[4]

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['To'] = dest_email
    #msg['From'] = source  ;# not sure if that is sensible or not
    msg['From'] = from_address 
    #print msg.as_string()

    #print "="*70
    mail_connection.sendmail(from_address,[dest_email],msg.as_string())
    print "Sent message to",dest_email,"with subject",subject
    smcli.typical_delete_program(smcli.EVENTOUT,
                                 ['--evsysseq',evsys],
                                 'delete')

mail_connection.quit()
