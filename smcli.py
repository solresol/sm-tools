#!/usr/bin/env python
# This module provides support for HP ServiceManager Web Services (WSDL)
# $Id$


# The following constants are the tested modules. 

INCIDENT = "Incident"
SERVICE_DESK = "Interaction"
CONFIGURATION = "Configuration"
CONTACT = 'Contact'
PROBLEM_MANAGEMENT = 'Problem'
COMPANY = 'Company'
COMPUTER = 'Computer'
DEPARTMENT = 'Department'
EVENTOUT = 'Eventout'  ;# this one requires special stuff loaded in SM7/9
SERVICENETIF = 'Servicenetmap'
DEVICE = 'Device'


######################################################################
#
# This was developed by Greg Baker <gregb@ifost.org.au> (c) 2010

version = '$Revision$'

import ConfigParser, os, string
import logging
from optparse import OptionParser
from optparse import OptionGroup
import sys
import re

# This program requires the python SUDS package. If the import in the
# next line fails, then try
# - sudo apt-get install python-setuptools  or yum install python-setuptools
# - sudo easy_install http://pypi.python.org/packages/2.6/s/suds/suds-0.4-py2.6.egg
from suds import WebFault
from suds.client import Client

import suds.transport.http

logging.basicConfig(level=logging.ERROR)



wsdl_paths = { INCIDENT : "IncidentManagement.wsdl",
               SERVICE_DESK: "ServiceDesk.wsdl",
               CONFIGURATION: "ConfigurationManagement.wsdl",
               CONTACT: "ConfigurationManagement.wsdl",
               COMPANY: "ConfigurationManagement.wsdl",
               COMPUTER: "ConfigurationManagement.wsdl",
               DEVICE: "ConfigurationManagement.wsdl",
               DEPARTMENT: "ConfigurationManagement.wsdl",
               PROBLEM_MANAGEMENT: "ProblemManagement.wsdl",
               EVENTOUT: "Eventout.wsdl",
               SERVICENETIF: "ServiceNetMap.wsdl"
               }




service_manager_naming_convention = [
    ('create',re.compile('Create(.*)')),
    ('reopen', re.compile('Reopen(.*)')),
    ('search', re.compile('Retrieve(.*)KeysList')),
    ('retrievelist', re.compile('Retrieve(.*)List')),
    ('update', re.compile('Update(.*)')),
    ('retrieve', re.compile('Retrieve(.*)')),
    ('delete', re.compile('Delete(.*)'))
    ]


class UpdateException(Exception):
    pass

class UnableToCreateSoapClient(Exception):
    def __init__(self,err):
        self.__err = err
    def __str__(self):
        return "UnableToCreateSoapClient" + `err`

def read_config_files(config_file=None):
    c = ConfigParser.ConfigParser()
    if config_file is not None:
        if type(config_file) == type([]):         config_file_locations = config_file
        else:                                     config_file_locations = [config_file]
    elif os.name == 'nt':
        config_file_locations = [ 'smwsdl.ini' ]
        # Perhaps I should look up the registry instead?
        # Look in the install location?
    elif os.name == 'posix':
        config_file_locations = ['/etc/smwsdl.ini',
                                 os.path.expanduser('~/.smwsdl.ini'),
                                 '.smwsdl.ini'
                                 ]
        if os.environ.has_key('SMWSDL_CONF'):
            config_file_locations.append(os.environ['SMWSDL_CONF'])
    else:
        sys.exit("Don't know where to look for config files on "+os.name)

    files_read = c.read(config_file_locations)
    if files_read == []:
        sys.exit("Cannot continue because none of the following files were usable: "+string.join(config_file_locations," "))
    return c



class smwsdl:
    """Reads config files from /etc/smwsdl.ini, ~/.smswsdl.ini,
./.smswsdl.ini and $SMWSDL_CONF. Figures out which server to connect
to."""
    def __init__(self,sm_module,config_file=None,config_obj=None):
        self.__sm_module = sm_module
        self.__wsdl_path = wsdl_paths[sm_module]

        if config_obj is not None:
            self.__config = config_obj
        else:
            self.__config = read_config_files(config_file)

        self.__deduce_defaults_section()
        self.__get_connection_details()
        try:
            self.__create_soap_client()
        except suds.transport.TransportError,err:
            raise UnableToCreateSoapClient(err)

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
            if modelthing.keys.__dict__.has_key(field) and include_keys:
                group = key_group
            elif modelthing.instance.__dict__.has_key(field) and include_instance:
                group = instance_group
            else:
                group = parser
            group.add_option("--"+camel2unix(field),"--"+field,
                             dest=field,type='string',
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
        self.__default_section = self.__default_section.lower()

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
        t = suds.transport.http.HttpAuthenticated(username=self.__service_manager_username,
                                                  password=self.__service_manager_password)
        self.__client = Client(url,transport=t)


    def list_raw_methods(self,print_return=False):
        """Every single method in every single port"""
        answer = []
        for sd in self.__client.sd:
            for port in sd.service.ports:
                answer = answer + port.methods.keys()
        if print_return:
            print answer
        return answer

    def list_objects(self,print_return=False):
        """Quite often this will be a one-element list, like [u'Incident']"""
        known_objects = {}
        raw_methods = self.list_raw_methods()
        for method in raw_methods:
            for (purpose,fn) in service_manager_naming_convention:
                m = fn.match(method)
                if m is not None:
                    obj = m.group(1)
                    known_objects[obj] = True
                    break
        if print_return:
            print known_objects.keys()
        return known_objects.keys()

    def list_methods_for_object(self,obj):
        raw_methods = self.list_raw_methods()
        available_methods = {'wsdl' : True}
        for method in raw_methods:
            for (purpose,fn) in service_manager_naming_convention:
                m = fn.match(method)
                if m is not None:
                    if m.group(1) == obj:
                        available_methods[purpose] = True
                        break
        return available_methods.keys()
            

######################################################################

def camel2unix(x):
    """A convenience function when you want to go from SomethingCamelCase to something-camel-case"""
    answer = x[0].lower()
    for i in range(1,len(x)-1):
        if x[i] == ".":
            answer = answer + "-"
            continue
        answer = answer + x[i].lower()
        if x[i].islower() and x[i+1].isupper():
            answer = answer + '-'
        if (i+2<len(x)) and x[i].isupper() and x[i+1].isupper() and x[i+2].islower():
            answer = answer + '-'
    answer = answer + x[-1].lower()
    return answer


######################################################################
                      
return_parts = { INCIDENT: 'IncidentID',
                 SERVICE_DESK: 'CallID',
                 CONTACT: 'ContactName',
                 PROBLEM_MANAGEMENT: 'id',
                 EVENTOUT: 'Evsysseq',
                 COMPANY: 'CustomerID',
                 COMPUTER: 'logical.name',
                 DEPARTMENT: None,
                 SERVICENETIF: 'id',
                 DEVICE: 'ConfigurationItem'
                 }

def standard_arg_type(module_name):
    return module_name.capitalize() + "ModelType"


def typical_create_program(sm_module,cmdline,action,print_return=False,web_service=None):
    if web_service is None:
        web_service = smwsdl(sm_module)
    arg_type=standard_arg_type(sm_module)
    invocation='Create' + sm_module.capitalize()
    return_part=return_parts[sm_module]
    parser = OptionParser(usage="usage: %prog --field-name=Value ...",
                          version=version)
    web_service.add_to_command_line_parser(parser,arg_type,
                                           include_keys=False,
                                           provide_defaults=True)
    (options,args) = parser.parse_args(cmdline)
    new_incident = web_service.create_soap_object(arg_type,options.__dict__)
    answer = web_service.invoke(invocation,new_incident)
    for m in answer.messages.message:
        sys.stderr.write(m.value + "\n")
    
    if return_part is None:
        ret = `answer.model.instance`
    else:
        ret = answer.model.instance.__dict__[return_part].value
    if print_return:
        print ret
    return ret


def typical_search_program(sm_module,cmdline,action,print_return=False,web_service=None):
    if web_service is None:
        web_service = smwsdl(sm_module)
    arg_type=standard_arg_type(sm_module)
    invocation='Retrieve' + sm_module.capitalize() + 'KeysList'
    return_part=return_parts[sm_module]

    parser = OptionParser(usage="usage: %prog --field=... --other-field=...",
                          version=version)
    web_service.add_to_command_line_parser(parser,arg_type,
                                           include_keys=False,
                                           provide_defaults=False)
    (options,args) = parser.parse_args(cmdline)
    new_incident = web_service.create_soap_object(arg_type,options.__dict__)
    answer = web_service.invoke(invocation,new_incident)

    answers = []
    for k in answer.keys:
        if return_part is None:
            answers.append(`k`)
            continue
        if k.__dict__[return_part].__dict__.has_key("value"):
            answers.append(k.__dict__[return_part].value)
    if print_return:
        print string.join(answers,'\n')
    return answers


def typical_update_program(sm_module,cmdline,action,print_return=False,web_service=None):
    if web_service is None:
        web_service = smwsdl(sm_module)
    arg_type=standard_arg_type(sm_module)
    invocation=action.capitalize() + sm_module.capitalize()
    parser = OptionParser(usage="usage: %prog --"+sm_module+"-id=...",version=version)
    web_service.add_to_command_line_parser(parser,arg_type)
    (options,args) = parser.parse_args(cmdline)
    new_incident = web_service.create_soap_object(arg_type,options.__dict__)
    answer = web_service.invoke(invocation,new_incident)
    ret = []
    if not(answer.__dict__.has_key('messages')):
        # Something really bad happened
        raise UpdateException
    for m in answer.messages.message:
        ret.append(m.value)
    if print_return:
        sys.stderr.write(string.join(ret,'\n')+'\n')
    return ret


def typical_delete_program(sm_module,cmdline,action,print_return=False,web_service=None):
    if web_service is None:
        web_service = smwsdl(sm_module)
    arg_type=standard_arg_type(sm_module)
    invocation='Delete' + sm_module.capitalize()
    parser = OptionParser(usage="usage: %prog --"+sm_module+"-id=...",version=version)
    web_service.add_to_command_line_parser(parser,arg_type,include_instance=False,provide_defaults=False)
    (options,args) = parser.parse_args(cmdline)
    new_incident = web_service.create_soap_object(arg_type,options.__dict__)
    answer = web_service.invoke(invocation,new_incident)
    ret = []
    if not(answer.__dict__.has_key('messages')):
        # Something really bad happened
        raise UpdateException
    for m in answer.messages.message:
        ret.append(m.value)
    if print_return:
        sys.stderr.write(string.join(ret,'\n')+'\n')
    return ret


def typical_retrieve_program(sm_module,cmdline,action,print_return=False,web_service=None):
    if web_service is None:
        web_service = smwsdl(sm_module)
    arg_type=standard_arg_type(sm_module)
    invocation='Retrieve' + sm_module.capitalize()
    parser = OptionParser(usage="usage: %prog --field=... --other-field=...",
                          version=version)
    web_service.add_to_command_line_parser(parser,arg_type,
                                           include_keys=True,
                                           include_instance=False,
                                           provide_defaults=False)
    (options,args) = parser.parse_args(cmdline)
    new_incident = web_service.create_soap_object(arg_type,options.__dict__)
    answer = web_service.invoke(invocation,new_incident)
    #print answer
    
    fields = answer.model.instance.__dict__.keys() + answer.model.keys.__dict__.keys()
    fields.sort()

    ret = {}
    seen_before = {}
    for k in fields:
        if seen_before.has_key(k): continue
        seen_before[k] = True
        if k[0]=="_": continue
        if answer.model.instance.__dict__.has_key(k):
            v = answer.model.instance.__dict__[k]
        else:
            v = answer.model.keys.__dict__[k]
        if v._type == "Array":
            ret[k] = []
            for elem in v.__dict__.keys():
                if elem[0] == '_': continue
                for subelem in v.__dict__[elem]:
                    if subelem.__dict__.has_key('value'):
                        ret[k].append(subelem.value)
        else:
            if not(v.__dict__.has_key('value')):
                # Hitting this code means something is badly wrong in the server response
                # Sometimes it might mean an invalid query was sent.
                print k,v,answer
            else:
                ret[k] = v.value

    if print_return:
        fields = ret.keys()
        fields.sort()
        for k in fields:
            if type(ret[k])==type([]):
                first_time=True
                print k+": ",
                for line in ret[k]:
                    if first_time: first_time=False
                    else: print (" "*(len(k+": "))),
                    print line
            else:
                print k+": "+ret[k]
    return ret

def typical_list_methods_program(sm_module,cmdline,action,print_return=False,web_service=None):
    if web_service is None:
        web_service = smwsdl(sm_module)
    if print_return:
        web_service.print_available_methods()
    return None

# To-do:
# 3. Handle arrays properly.
# 4. Return error code if something went wrong for more than just updates.
# 6. Usage argument should show what we are doing
# 7. Fix up help so that it shows aliases as well
# 8. Typical retrieve program should return a dictionary, I think.
# 10. Implement delete methods (e.g. delete contact)
# 11. Maybe the "typical_*_program" stuff should be wrapped in a class?
#     Then I could ditch 'action' as an argument perhaps?
# 12. Instead of hard-coding what actions are supported, we should figure
#     it out from the WSDL.
# 13. We should have a config file so that we can add additional WSDLs
#     if the site has customised extaccess.

  
function_calls = {
    'create'  : typical_create_program,
    'close'   : typical_update_program,
    'update'  : typical_update_program,
    'reopen'  : typical_update_program,
    'search'  : typical_search_program,
    'retrieve': typical_retrieve_program,
    'wsdl': typical_list_methods_program,
    'delete': typical_delete_program
    }

action_aliases = {
    'gloop'  : 'create',
    'new'    : 'create',
    'make'   : 'create',
    'add'    : 'create',
    'create' : 'create',
    'change' : 'update',
    'alter' : 'update',
    'update': 'update',
    'find'   : 'search',
    'list'   : 'search',
    'search' : 'search',
    'return'   : 'retrieve',
    'lookup'   : 'retrieve',
    'retrieve' : 'retrieve',
    'fetch'    : 'retrieve',
    'debug' : 'wsdl',
    'wsdl'  : 'wsdl',
    'remove' : 'delete',
    'delete' : 'delete'
    }

table_aliases = { 'incident' : INCIDENT,
                  'incidents' : INCIDENT,
                  'interaction' : SERVICE_DESK,
                  'interactions' : SERVICE_DESK,
                  'servicedesk' : SERVICE_DESK,
                  'service-desk' : SERVICE_DESK,
                  'call' : SERVICE_DESK,
                  'calls' : SERVICE_DESK,
                  'contact' : CONTACT,
                  'contacts' : CONTACT,
                  'configuration' : CONFIGURATION,
                  'problems' : PROBLEM_MANAGEMENT,
                  'company' : COMPANY,
                  'device' : DEVICE,
                  'devices' : DEVICE,
                  'ci' : DEVICE,
                  'configurationitem' : DEVICE,
                  'bizservice' : DEVICE,
                  'eventout' : EVENTOUT,
                  'servicenetif' : SERVICENETIF,
                  }

if __name__ == '__main__':
    action = sys.argv[1].lower()
    if (action_aliases.has_key(action)):
        action = action_aliases[action]
    else:
        sys.exit("Unknown action: " + sys.argv[1] + "\nKnown actions are: "+string.join(action_aliases.keys()," "))
    
    table = sys.argv[2].lower()
    if (table_aliases.has_key(table)):
        table = table_aliases[table]
    else:
        sys.exit("Unknown object: " + sys.argv[2] + "\nKnown objects are: "+string.join(table_aliases.keys()," "))

    sys.argv[0] = sys.argv[0]+" "+sys.argv[1]+" " + sys.argv[2]
    cmdline = sys.argv[3:]
    if os.name == 'nt':
        # Allow users to use /Foo:bar instead of --Foo=bar
        slashcolonsomething = re.compile('^/([A-Za-z0-9_]+):(.+)$')
        slashcolononly = re.compile('^/([A-Za-z0-9_]+):')
        justslash = re.compile('^/')
        for i in range(len(cmdline)):
            if slashcolonsomething.match(cmdline[i]):
                cmdline[i] = slashcolonsomething.sub('--\\1=\\2',cmdline[i])
                continue
            if slashcolononly.match(cmdline[i]):
                cmdline[i] = slashcolononly.sub('--\\1',cmdline[i])
                continue
            if justslash.match(cmdline[i]):
                cmdline[i] = justslash.sub('--',cmdline[i])
                continue

    ws = smwsdl(table)
    supported_actions = ws.list_methods_for_object(table)
    if not(action in supported_actions):
        sys.exit("Unsupported action. Actions are: "+string.join(supported_actions,' '))
    function = function_calls[action]
    try:
        function(table,cmdline,action,print_return=True,web_service=ws)
    except UpdateException:
        sys.exit("Update failure")
