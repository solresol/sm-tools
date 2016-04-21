# sm-tools
Tools for interacting with HP Service Manager

- activitywsdl.unl -- enable WSDL access to the Activity table

- create-or-update-incident.sh -- when NNM detects a node goes down, either update the existing Service Manager incident or create a new one.

- event-handler.sh -- When NNM generates an event (either up or down), dispatch appropriately to Service Manager

- email2ticket.py -- a much easier way of having HP SM receive emails that doesn't involve Connect-IT. Edit email2ticket.conf and you're ready to go

- fastpass-email2ticket.py -- similar to email2ticket but designed to work with FastPass, and report the ticket as closed automatically

- sm2email.py -- a much easer way for HP SM to send emails that doesn't involve Connect-IT. Edit sm2email.conf and that's about it.

- sm2sms.py -- if HP SM tries to send a "pager" notification, send an SMS. Doesn't involve Connect-IT.

- smcli.py -- library and program -- Swiss army knife of interacting with Service Manager on the commandline

- smprocmail.py -- instead of polling an IMAP or POP server, why not deliver your customer interaction emails via procmail through to smprocmail.py
 which will turn them into interactions *instantly* (i.e. no polling delay). Amaze your customers.
 
- valuesms.py -- command-line script for sending emails
