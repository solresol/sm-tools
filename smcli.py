# This module provides support for HP ServiceManager Web Services (WSDL)
# $Id$


# The following constants are the tested modules. (Have to be lower case)

INCIDENT = "incident"
SERVICE_DESK = "servicedesk"
CONFIGURATION = "configuration"
CONTACTS = 'contacts'


######################################################################
#
# This was developed by Greg Baker <gregb@ifost.org.au> (c) 2010

version = '$Revision$'

import ConfigParser, os, string
import logging
from optparse import OptionParser
from optparse import OptionGroup
import sys

# This program requires the python SUDS package. If the import in the
# next line fails, then try
# - sudo apt-get install python-setuptools  or yum install python-setuptools
# - sudo easy_install http://pypi.python.org/packages/2.6/s/suds/suds-0.4-py2.6.egg
from suds import WebFault
from suds.client import Client
from suds.transport.http import HttpAuthenticated

logging.basicConfig(level=logging.ERROR)

######################################################################

def camel2unix(x):
    """A convenience function when you want to go from SomethingCamelCase to something-camel-case"""
    answer = x[0].lower()
    for i in range(1,len(x)-1):
        answer = answer + x[i].lower()
        if x[i].islower() and x[i+1].isupper():
            answer = answer + '-'
        if (i+2<len(x)) and x[i].isupper() and x[i+1].isupper() and x[i+2].islower():
            answer = answer + '-'
    answer = answer + x[-1].lower()
    return answer


######################################################################


wsdl_paths = { INCIDENT : "IncidentManagement.wsdl",
               SERVICE_DESK: "ServiceDesk.wsdl",
               CONFIGURATION: "ConfigurationManagement.wsdl",
               CONTACTS: "ConfigurationManagement.wsdl",
               }

class smwsdl:
    """Reads config files from /etc/smwsdl.ini, ~/.smswsdl.ini,
./.smswsdl.ini and $SMWSDL_CONF. Figures out which server to connect
to."""
    def __init__(self,sm_module):
        self.__sm_module = sm_module
        self.__wsdl_path = wsdl_paths[sm_module]

        self.__read_config()
        self.__deduce_defaults_section()
        self.__get_connection_details()
        self.__create_soap_client()

    def print_available_methods(self):
        print self.__client

    def add_to_command_line_parser(self,parser,soap_data_type,include_keys=True,include_instance=True,provide_defaults=False):
        """Given a SOAP data type, returns an OptionParser which
        parses command-lines based on the WSDL service. e.g. if
        AffectedCI is part of the soap_data_type, returns a parser
        which understands --affected-ci=....
        """
        modelthing = self.__client.factory.create(soap_data_type)
        ticket_fields = []
        if include_keys:
            ticket_fields = ticket_fields + dir(modelthing.keys)
            key_group = parser
        if include_instance:
            ticket_fields = ticket_fields + dir(modelthing.instance)
            instance_group = parser
        if include_keys and include_instance:
            key_group = OptionGroup(parser,"Key/Search/Selection options")
            parser.add_option_group(key_group)
            instance_group = OptionGroup(parser,"Update/create options")
            parser.add_option_group(instance_group)
        ticket_fields = filter(lambda x: x[0:1]!='_',ticket_fields)
        seen = {}
        for field in ticket_fields:
            if seen.has_key(field): continue
            seen[field]=True
            # read the config file and see if there are any defaults
            if provide_defaults:
                if self.__config.has_option(self.__default_section,field):
                    def_value = self.__config.get(self.__default_section,field)
                    parser.set_default(field,def_value)
                    helptext = "Set the "+field+" field (default='%default')"
                else:
                    helptext = "Set the "+field+" field (no default)"
            else:
                helptext = "The "+field+" field."
            unixified = camel2unix(field)
            if modelthing.keys.__dict__.has_key(field) and include_keys:
                group = key_group
            elif modelthing.instance.__dict__.has_key(field) and include_instance:
                group = instance_group
            else:
                group = parser
            group.add_option("--"+unixified,dest=field,type='string',
                              action="store",help=helptext)


        # To-do. It should also iterate of modelthing.keys, and put them
        # into a separate option group. We should have an argument to say
        # whether we are creating or doing some kind of update.


    def create_soap_object(self,soap_data_type,initialisation_dict):
        modelthing = self.__client.factory.create(soap_data_type)
        for field in initialisation_dict.keys():
            if modelthing.keys.__dict__.has_key(field):
                modelthing.keys.__dict__[field] = initialisation_dict[field]
            elif modelthing.instance.__dict__.has_key(field):
                modelthing.instance.__dict__[field] = initialisation_dict[field]
            # And skip it otherwise. It's probably irrelevant.
            # Maybe I should warn?

        return modelthing

    def invoke(self,function,argument):
        func = self.__client.service.__getattr__(function)
        return func(argument)

    def __deduce_defaults_section(self):
        best_environment = "SMWSDL_" + self.__sm_module.upper() + "_DEFAULTS"
        if os.environ.has_key(best_environment):
            self.__default_section = os.environ[best_environment]
            return
        if os.environ.has_key('SMWSDL_DEFAULTS'):
            self.__default_section = os.environ['SMWSDL_DEFAULTS']
            return
        self.__default_section = self.__sm_module + " defaults"

    def __read_config(self):
        if sys.platform[:3] == 'win':
            config_file_locations = [ 'smwsdl.ini' ]
            # Perhaps I should look up the registry instead?
            # Look in the install location?
        elif sys.platform == 'vms':
            sys.exit("I don't have a VMS box to test. What config files should this read?")
        else:
            config_file_locations = ['/etc/smwsdl.ini',
                                     os.path.expanduser('~/.smwsdl.ini'),
                                     '.smwsdl.ini'
                                     ]
        if os.environ.has_key('SMWSDL_CONF'):
            config_file_locations.append(os.environ['SMWSDL_CONF'])

        self.__config = ConfigParser.ConfigParser()
        files_read = self.__config.read(config_file_locations)
        if files_read == []:
            sys.exit("Cannot continue because none of the following files were usable: "+string.join(config_file_locations," "))


    def __get_connection_details(self):
        """Read the [connection] section from the config file"""
        if self.__config.has_option('connection','server'):
            self.__service_manager_server = self.__config.get('connection','server')
        else:
            sys.exit("Server not specified")

        if self.__config.has_option('connection','protocol'):
            self.__service_manager_protocol = self.__config.get('connection','protocol')
        else:
            self.__service_manager_protocol = 'http'

        if self.__config.has_option('connection','port'):
            self.__service_manager_port = self.__config.getint('connection','port')
        else:
            self.__service_manager_port = 13080
    
        if self.__config.has_option('connection','password'):
            self.__service_manager_password = self.__config.get('connection','password')
        elif self.__config.has_option('connection','pass'):
            self.__service_manager_password = self.__config.get('connection','pass')
        else:
            self.__service_manager_password = ''

        if self.__config.has_option('connection','username'):
            self.__service_manager_username = self.__config.get('connection','username')
        elif self.__config.has_option('connection','user'):
            self.__service_manager_username = self.__config.get('connection','user')
        else:
            sys.exit("Username not specified")


    def __create_soap_client(self):
        url = self.__service_manager_protocol + "://" + self.__service_manager_server + ":" + `self.__service_manager_port` + "/SM/7/" + self.__wsdl_path
        t = HttpAuthenticated(username=self.__service_manager_username,
                              password=self.__service_manager_password)
        self.__client = Client(url,transport=t)

                      


def typical_update_program(sm_module,search_arg_type,invocation,uses_values=True):
    web_service = smwsdl(sm_module)
    parser = OptionParser(usage="usage: %prog --"+sm_module+"-id=...",version=version)
    web_service.add_to_command_line_parser(parser,search_arg_type,include_instance=uses_values)
    (options,args) = parser.parse_args()
    new_incident = web_service.create_soap_object(search_arg_type,options.__dict__)
    answer = web_service.invoke(invocation,new_incident)
    for m in answer.messages.message:
        sys.stderr.write(m.value+'\n')


def typical_create_program(sm_module,creation_arg_type,invocation,return_part):
    web_service = smwsdl(sm_module)
    parser = OptionParser(usage="usage: %prog --field-name=Value ...",
                          version=version)
    web_service.add_to_command_line_parser(parser,creation_arg_type,
                                           include_keys=False,
                                           provide_defaults=True)
    (options,args) = parser.parse_args()
    new_incident = web_service.create_soap_object(creation_arg_type,options.__dict__)
    answer = web_service.invoke(invocation,new_incident)
    for m in answer.messages.message:
        sys.stderr.write(m.value + "\n")
    print answer.model.instance.__dict__[return_part].value


def typical_search_program(sm_module,search_arg_type,invocation,return_part):
    web_service = smwsdl(sm_module)
    parser = OptionParser(usage="usage: %prog --field=... --other-field=...",
                          version=version)
    web_service.add_to_command_line_parser(parser,search_arg_type,
                                           include_keys=False,
                                           provide_defaults=False)
    (options,args) = parser.parse_args()
    new_incident = web_service.create_soap_object(search_arg_type,options.__dict__)
    answer = web_service.invoke(invocation,new_incident)
    
    for k in answer.keys:
        if k.__dict__[return_part].__dict__.has_key("value"):
            print k.__dict__[return_part].value

def typical_retrieve_program(sm_module,search_arg_type,invocation):
    web_service = smwsdl(sm_module)
    parser = OptionParser(usage="usage: %prog --field=... --other-field=...",
                          version=version)
    web_service.add_to_command_line_parser(parser,search_arg_type,
                                           include_keys=True,
                                           include_instance=False,
                                           provide_defaults=False)
    (options,args) = parser.parse_args()
    new_incident = web_service.create_soap_object(search_arg_type,options.__dict__)
    answer = web_service.invoke(invocation,new_incident)
    
    fields = answer.model.instance.__dict__.keys()
    fields.sort()
    for k in fields:
        if k[0]=="_": continue
        print k+": ",
        v = answer.model.instance.__dict__[k]
        if v._type == "Array":
            first=True
            for elem in v.__dict__.keys():
                if elem[0] == '_': continue
                for subelem in v.__dict__[elem]:
                    #if subelem[0]=="_": continue
                    if first: first=False
                    else: print (" "*len(k+": ")),
                    print subelem.value
        else:
            print v.value

def typical_list_methods_program(sm_module):
    web_service = smwsdl(sm_module)
    web_service.print_available_methods()

# To-do:
# 1. Merge sm-*.py into here.
# 2. Support windows&VMS style command args /foo:bar
# 3. Handle arrays properly.
# 4. Return error code if something went wrong.
# 5. Table aliases: e.g. contacts are part of configuration.
# 6. Usage argument should show what we are doing
# 7. Fix up help so that it shows aliases as well

actions = {
    'create' : { INCIDENT: { 'creation_arg_type': 'IncidentModelType',
                             'invocation': 'CreateIncident',
                             'return_part': 'IncidentID'  },
                 SERVICE_DESK: { 'creation_arg_type': 'InteractionModelType',
                                 'invocation': 'CreateInteraction',
                                 'return_part': 'CallID'   }
                 },
    'close' :  { INCIDENT: { 'search_arg_type': 'IncidentModelType',
                             'invocation': 'CloseIncident',
                             'uses_values':True }
                 },
    'update' : { INCIDENT:  {'search_arg_type': 'IncidentModelType',
                             'invocation': 'UpdateIncident' }
                 },
    'reopen' : { INCIDENT: { 'search_arg_type': 'IncidentModelType',
                             'invocation': 'ReopenIncident',
                             'uses_values': True }
                 },
    'search' : { INCIDENT: { 'search_arg_type': 'IncidentModelType',
                             'invocation': 'RetrieveIncidentKeysList',
                             'return_part': 'IncidentID' },
                 SERVICE_DESK: { 'search_arg_type': 'InteractionModelType',
                                 'invocation': 'RetrieveInteractionKeysList',
                                 'return_part': 'CallID' },
                 CONTACTS: { 'search_arg_type': 'ContactModelType',
                             'invocation': 'RetrieveContactKeysList',
                             'return_part' : 'ContactName'}
                 },
    'retrieve' : { INCIDENT: { 'search_arg_type': 'IncidentModelType',
                               'invocation': 'RetrieveIncident' }
                   },
    'list-methods' : { INCIDENT:  {},
                       SERVICE_DESK: {},
                       CONTACTS: {},
                       CONFIGURATION: {},
                       }
    }


function_calls = {
    'create'  : typical_create_program,
    'close'   : typical_update_program,
    'update'  : typical_update_program,
    'reopen'  : typical_update_program,
    'search'  : typical_search_program,
    'retrieve': typical_retrieve_program,
    'list-methods': typical_list_methods_program
    }

aliases = { 'new' : 'create',
            'make' : 'create',
            'change' : 'update',
            'alter' : 'update',
            'find' : 'search',
            'return' : 'retrieve',
            'lookup' : 'retrieve',
            'fetch' : 'retrieve',
            'debug' : 'list-methods' }

table_aliases = { 'incident' : INCIDENT,
                  'incidents' : INCIDENT,
                  'interaction' : SERVICE_DESK,
                  'interactions' : SERVICE_DESK,
                  'servicedesk' : SERVICE_DESK,
                  'service-desk' : SERVICE_DESK,
                  'call' : SERVICE_DESK,
                  'contact' : CONTACTS,
                  'contacts' : CONTACTS,
                  'configuration' : CONFIGURATION
                  }

if __name__ == '__main__':
    action = sys.argv[1].lower()
    if (aliases.has_key(action)): action = aliases[action]
    
    table = sys.argv[2].lower()
    if (table_aliases.has_key(table)):
        table = table_aliases[table]

    sys.argv = sys.argv[2:]
    if not(actions.has_key(action)):
        sys.exit("Unknown action. Actions are: "+string.join(actions.keys()," "))
    if not(actions[action].has_key(table)):
                sys.exit("Unsupported table. Tables supported for " + action + " are "+
                 string.join(actions[action].keys()," "))
    kwargs = actions[action][table]
    function = function_calls[action]
    function(table,**kwargs)
    

