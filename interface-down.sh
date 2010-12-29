#!/bin/bash

# $Id$

# This script takes five-and-then-some arguments:
#
# - The first argument should be a uuid (e.g. $uuid from an NNM
# incident).
# 
# - The second argument should be a source node (e.g. $snn from an 
# NNM incident)
#
# - The third argument should be an interface (e.g. $ifn from an NNM incident)
#
# - The fourth argument should be an interface alias (e.g. $ifa)
#
# - The fifth argument should be one of: open, close, completed, registered
#
# - Any remaining arguments will be passed to smcli.py update incident or
# smcli.py create incident unchanged
#
# The script will look to see if there is already an incident with
# that nnmuuid.
#   + If there is not, it will call smcli.py create incident
#   + If there is, and the action is "close", it will call smcli.py close
#     incident
#   + If there is, and the incident is in a closed state, it will call
#     smcli.py reopen incident
#   + Otherwise it will call smcli.py update incident
#
# - If we have to create an incident, the script will lookup servicenetif 
# on ServiceManager (via WSDL) and try to figure out what service is 
# affected by this problem. It will try:
#     + --netdevice=$SOURCE_NODE --interface=$IFALIAS
#     + --netdevice=$SOURCE_NODE --interface=$INTERFACE
#     + --netdevice=$SOURCE_NODE 
# until it gets something sensible. If nothing works, it hopes that the
# service has been defined in the passed-along-unchanged arguments.
#

echo "[$$] $0 $* invoked on $(date)" >> /tmp/coui.log

UUID=$1
SOURCE_NODE=$2
INTERFACE=$3
IFALIAS=$4
ACTION=$5
shift
shift
shift
shift
shift

PATH=/var/opt/OV/shared/nnm/actions:$PATH

INCIDENTS=$(smcli.py search incidents --nnmid="$UUID")

if [ "$INCIDENTS" != "" ]
then
  err=0
  for INCIDENT in $INCIDENTS
  do
    INCIDENT_STATE=$(smcli.py fetch incident --incident-id=$INCIDENT | grep '^Status: ' | sed 's/^Status: //')
    if [ "$ACTION" = "close" ]
    then
        smcli.py close incident --incident-id=$INCIDENT "$@" && err=$?
        continue
    fi
    if [ "$INCIDENT_STATE" = "Closed" ]
    then
      smcli.py reopen incident --incident-id=$INCIDENT "$@" && err=$?
      continue
    fi
    smcli.py update incident --incident-id=$INCIDENT "$@" && err=$?
  done
  exit $err
fi

# OK, so we're creating a new incident.

if [ "$SOURCE_NODE" = "" ]
then
  # Shrug, can't do much with that.
  smcli.py create incident --nnmid="$UUID" "$@"
  exit $?
fi

# Find out the serviceif mapping id
SMAP_ID=""
if [ "$IFALIAS" != "" ]
then
  SMAP_ID=$(smcli.py search servicenetif --netdevice=$SOURCE_NODE --interface=$IFALIAS)
fi
if [ "$SMAP_ID" = "" -a "$INTERFACE" != "" ]
then
  SMAP_ID=$(smcli.py search servicenetif --netdevice=$SOURCE_NODE --interface=$INTERFACE)
fi
if [ "$SMAP_ID" = "" ]
then
  # Getting desperate. Is there only one service for this device?
  if [ $(smcli.py search servicenetif --netdevice=$SOURCE_NODE | wc -l) = 1 ]
  then
    SMAP_ID=$(smcli.py search servicenetif --netdevice=$SOURCE_NODE)
  fi
fi

# Now turn that SMAP_ID into a service name with --service
if [ "$SMAP_ID" = "" ]
then
  SERVICE_ARG=""
else
  smcli.py fetch servicenetif --id=$SMAP_ID >> /tmp/coui.log
  SERVICE=$(smcli.py fetch servicenetif --id=$SMAP_ID | grep -i '^service: '| sed 's/^service: //i')
  SERVICE_ARG="--service=$SERVICE"
fi

echo "[$$] Launched smcli.py create incident --nnmid=$UUID $SERVICE_ARG $*" >> /tmp/coui.log
smcli.py create incident --nnmid="$UUID" "$SERVICE_ARG" "$@"
