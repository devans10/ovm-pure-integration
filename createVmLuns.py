#!/usr/bin/python

import sys
import os
import time
import getpass
import simplejson as json
from optparse import OptionParser
from purestorage import FlashArray

try:
    import requests
except:
    print "Must install python requests module"
    sys.exit(1)

### Function to check the OVM Manger Running State
def check_manager_state(baseUri,s):
    while True:
        r=s.get(baseUri+'/Manager')
        manager=r.json()
        if manager[0]['managerRunState'].upper() == 'RUNNING':
            print "OVM Manager is " + manager[0]['managerRunState']
            break
        time.sleep(1)

### Function to check the status of a Job
def wait_for_job(joburi,s):
    while True:
        time.sleep(1)
        r=s.get(joburi)
        job=r.json()
        if job['summaryDone']:
            print("\n{name}: {runState}".format(name=job['name'], runState=job['jobRunState']))
            if job['jobRunState'].upper() == 'FAILURE':
                raise Exception('Job failed: {error}'.format(error=job['error']))
            elif job['jobRunState'].upper() == 'SUCCESS':
                if 'resultId' in job:
                    return job['resultId']
        sys.stdout.write('.')
        sys.stdout.flush()

def get_id_from_name(s,baseUri,resource,obj_name):
    uri=baseUri+'/'+resource+'/id'
    r=s.get(uri)
    for obj in r.json():
        if 'name' in obj.keys():
            if obj['name']==obj_name:
                return obj['value']
    raise Exception('Failed to find id for {name}'.format(name=obj_name))

def refreshStorageArray(s,baseUri,storageArray):
    print "\nRefreshing Storage Array "+storageArray
    print "#########################################"
    san_id = get_id_from_name(s,baseUri,'StorageArray',storageArray)
    uri = '{base}/StorageArray/{sanId}/refresh'.format(base=baseUri,sanId=san_id)
    r=s.put(uri)
    job=r.json()
    # wait for the job to complete
    wait_for_job(job['id']['uri'],s)


def listLUNs(s,baseUri,name):
    print "##########"
    san_id=get_id_from_name(s,baseUri,'StorageArray',name)
    print san_id['uri']
    uri='{base}/StorageElement/id'.format(base=baseUri)
    r=s.get(uri)
    seids=r.json()
    for id in seids:
        uri='{base}/StorageElement/{seid}'.format(base=baseUri,seid=id['value'])
        r=s.get(uri)
        print r.json()['name']+" "+r.json()['page83Id']

def renameLUNs(s,baseUri,array):
    volumes = array.list_volumes()
    uri='{base}/StorageElement/id'.format(base=baseUri)
    r=s.get(uri)
    seids=r.json()
    for id in seids:
        uri='{base}/StorageElement/{seid}'.format(base=baseUri,seid=id['value'])
        r=s.get(uri)
        for volume in volumes:
            if volume['serial'] == r.json()['page83Id'][9:].upper():
                new_name = volume['name']
                break

        if new_name != r.json()['name']:
            print 'Change '+r.json()['name']+' to '+new_name
            data = r.json()
            data['name'] = new_name
            r1=s.put(baseUri+'/StorageElement/'+id['value'],data=json.dumps(data))
            job=r1.json()
            # wait for the job to complete
            wait_for_job(job['id']['uri'],s)

def createAsmVols(array, prefix, vols):

    returnVols = []
    print "\nCreating ASM Volumes"
    print "######################"

    for vol in vols:
        try:
            array.create_volume(prefix+"-"+vol['volume'], vol['size'])
            print "Created "+prefix+"-"+vol['volume']+" "+vol['size']
            vol['volume'] = prefix+"-"+vol['volume']
            returnVols.append(vol)
        except Exception as e:
            print e
            print "Failed to create volume "+prefix+"-"+vol['volume']
            sys.exit(1)
    return returnVols


def connectVols(array, vols, hostgroup):
    print "\nConnecting ASM Volumes to "+hostgroup
    print "#######################################"

    for vol in vols:
        try:
            array.connect_hgroup(hostgroup, vol['volume'])
            print vol['volume']+" connected to "+hostgroup
        except:
            print "Failed to connect volume "+ vol
            sys.exit(1)
    print "SUCCESS"

def createPG(array, vols, protectGroup):
    print "\nCreating Protection Groups"
    print "###########################"

    for vol in vols:
        if vol['protect']:
            pgrps = array.list_pgroups()
            if not any(d['name'] == protectGroup+vol['pgroup'] for d in pgrps):
                try:
                    array.create_pgroup(protectGroup+vol['pgroup'])
                except:
                    print "Failed to create Protection Group"
                    sys.exit(1)
            try:
                array.add_volume(vol['volume'], protectGroup+vol['pgroup'])
                print "Added: "+vol['volume']+" to Protection Group "+protectGroup+vol['pgroup']
            except:
                print "Failed to add "+vol['volume']+" to "+protectGroup+vol['pgroup']
                sys.exit(1)

    print "SUCCESS"


############ Main Program ###############


parser = OptionParser(usage="usage: %prog [options]", version="%prog 1.0")

parser.add_option("-n", "--name", dest="name", help="Oracle Database Host or Cluster Name")
parser.add_option("-g", "--hostgroup", dest="hostgroup", help="Pure Storage HostGroup")
parser.add_option("-a", "--array", dest="array", help="Pure Storage Array")
parser.add_option("-u", "--username", dest="username", help="User for logging into OVM Manager")
parser.add_option("-p", "--password", dest="passwd", help="Password for logging into OVM Manger")
parser.add_option("-s", "--server", dest="server", default="localhost", help="FQDN of OVM Manager")
parser.add_option("-f", "--file", dest="file", help="Path to properties file with Volume Definitions")

(options, args) = parser.parse_args(sys.argv)

server = options.server

if not options.name:
    parser.error("Name not provided")
else:
    oracleServer = options.name

if not options.hostgroup:
    parser.error("Hostgroup not provided")
else:
    hostgroup = options.hostgroup

if not options.array:
    parser.error("Properties file not provided")
else:
    properties = options.file

if not options.username:
    parser.error("OVM Username not provided")
else:
    username = options.username

### Get password if not provided
password = ''
try:
    password = options.passwd
except:
    pass

while not password:
    try:
        password = getpass.getpass()
    except EOFError:
        PrintWarning('Password may not be empty... try again...')

if not options.array:
    parser.error("Array not provided")
else:
    array = FlashArray(options.array, username, password)

### Verify Array ###
try:
    array_info = array.get()
    print "FlashArray {} (version {}) REST session established!".format(
           array_info['array_name'], array_info['version'])
except:
    print "Array not connected"
    sys.exit(1)

with open(properties) as json_data_file:
    vols = json.load(json_data_file)

### Create the Volumes ###
vols = createAsmVols(array,oracleServer,vols)

### Attach Volumes to Array Hostgroup ####
connectVols(array, vols, hostgroup)

createPG(array, vols, oracleServer)


###  Create Connection to OVM Mangaer #####
s=requests.Session()
s.auth=(username, password)
s.verify=False

s.headers.update({'Accept': 'application/json', 'Content-Type': 'application/json'})

baseUri='https://'+server+':7002/ovm/core/wsapi/rest'
############################################

check_manager_state(baseUri,s)

refreshStorageArray(s,baseUri,array_info['array_name'])
renameLUNs(s,baseUri,array)

print "\nVolumes Created Successfully"
