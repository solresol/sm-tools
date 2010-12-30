#!/bin/bash

# $Id$

# This script takes five-and-then-some arguments:
#
# - The first argument should be a uuid (e.g. $uuid from an NNM
# incident).
#
# - The second argument should be an event name:
#     + "ifDown"
#     + "nodeDown"
#     + "linkDown"
#
# - The third argument should be:
#     + "registered"
#     + "in progress"
#     + "completed"
#     + "closed"
#
#
# For ifDown and linkDown, there should then be three further arguments:
#     + source node
#     + interface name
#     + interface alias
#
# For nodeDown, there should be one further argument:
#     + source node
#
######################################################################
#
# The script will look to see if there is already an incident with
# that nnmuuid.
#   + If there is not, it will call "smcli.py create incident"
#   + If there is, and the action is "close", it will call "smcli.py close
#     incident" on each such incident
#   + If there is, and the incident is in a closed state, it will call
#     "smcli.py reopen incident" for each such incident
#   + Otherwise it will call "smcli.py update incident" for each such incident
#
#######################################################################
#
# If we have to create an incident, the script will lookup servicenetif 
# on ServiceManager (via WSDL) and try to figure out what service is 
# affected by this problem.
#
# For ifDown and linkDown, it will try:
#     + --netdevice=$SOURCE_NODE --interface=$IFALIAS
#     + --netdevice=$SOURCE_NODE --interface=$INTERFACE
#     + --netdevice=$SOURCE_NODE 
# until it gets something sensible.
#
# For nodeDown, it will walk through the --netdevice=$SOURCE_NODE output
# and create an incident for each interface.

echo "[$$] $0 $* invoked on $(date)" >> /tmp/coui.log

UUID=$1
EVENT_NAME=$2
ACTION=$3
shift
shift
shift

case "$EVENT_NAME" in
    ifDown|linkDown)
	SOURCE_NODE=$1
	INTERFACE=$2
	IFALIAS=$3
	shift
	shift
	shift
	;;
    nodeDown)
	SOURCE_NODE=$1
	INTERFACE=""
	IFALIAS=""
	shift
	;;
    *)
	echo "Unknown event $EVENT_NAME: should be one of ifDown, linkDown or nodeDown"
	exit 1
esac

case "$ACTION" in
    registered


PATH=/var/opt/OV/shared/nnm/actions:$PATH

INCIDENTS=$(smcli.py search incidents --nnmid="$UUID")

######################################################################
#
# If we do have some existing incidents with this ID
#
######################################################################

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

######################################################################

# OK, so we're creating a new incident.

if [ "$SOURCE_NODE" = "" ]
then
  # Shrug, can't do much with that.
  smcli.py create incident --nnmid="$UUID" "$@"
  exit $?
fi

######################################################################

# Find out the serviceif mapping id
SMAP_IDS=""
if [ "$IFALIAS" != "" ]
then
  SMAP_IDS=$(smcli.py search servicenetif --netdevice=$SOURCE_NODE --interface=$IFALIAS)
fi
if [ "$SMAP_IDS" = "" -a "$INTERFACE" != "" ]
then
  SMAP_IDS=$(smcli.py search servicenetif --netdevice=$SOURCE_NODE --interface=$INTERFACE)
fi
if [ "$SMAP_IDS" = "" ]
then
  SMAP_IDS=$(smcli.py search servicenetif --netdevice=$SOURCE_NODE)
fi

# Now turn that SMAP_ID into a service name with --service
if [ "$SMAP_IDS" = "" ]
then
  SERVICE_ARG=""
else
  smcli.py fetch servicenetif --id=$SMAP_ID >> /tmp/coui.log
  SERVICE=$(smcli.py fetch servicenetif --id=$SMAP_ID | grep -i '^service: '| sed 's/^service: //i')
  SERVICE_ARG="--service=$SERVICE"
fi

echo "[$$] Launched smcli.py create incident --nnmid=$UUID $SERVICE_ARG $*" >> /tmp/coui.log
smcli.py create incident --nnmid="$UUID" "$SERVICE_ARG" "$@"
