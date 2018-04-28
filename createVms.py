#!/usr/bin/python

import sys
import os
import time
import simplejson as json
from optparse import OptionParser
import getpass
from six.moves.urllib import parse as urlparse

try:
    import requests
except:
    print "Must install python requests module"
    sys.exit(1)



### Function to check the OVM Manger Running State
def check_manager_state(baseUri,s):
    while True:
        r = s.get(baseUri+'/Manager')
        manager = r.json()
        if manager[0]['managerRunState'].upper() == 'RUNNING':
            print "OVM Manager is " + manager[0]['managerRunState']
            break
        time.sleep(1)

### Function to check the status of a Job
def wait_for_job(joburi,s):
    while True:
        time.sleep(1)
        r = s.get(joburi)
        job = r.json()
        if job['summaryDone']:
            print('{name}: {runState}'.format(name=job['name'], runState=job['jobRunState']))
            if job['jobRunState'].upper() == 'FAILURE':
                raise Exception('Job failed: {error}'.format(error=job['error']))
            elif job['jobRunState'].upper() == 'SUCCESS':
                if 'resultId' in job:
                    return job['resultId']

### Get the OVM Object ID based on the name
def get_id_from_name(s,baseUri,resource,obj_name):
    uri=baseUri+'/'+resource+'/id'
    r=s.get(uri)
    for obj in r.json():
        if 'name' in obj.keys():
            if obj['name']==obj_name:
                return obj['value']
    raise Exception('Failed to find id for {name}'.format(name=obj_name))

### change the name of the virtual disk
def updateVirtualDisk(s,baseUri,id,newDiskName):
    print "\nVM Update Vm Disk Mapping for " + id
    print "########################################"
    uri = '{base}/VirtualDisk/{id}'.format(base=baseUri,id=id)
    r = s.get(uri)
    disk = r.json()
    disk['name'] = newDiskName

    r = s.put(uri,data=json.dumps(disk))
    job = r.json()
    # wait for the job to complete
    wait_for_job(job['id']['uri'],s)

### Clone a VM from template and set its objects to standard names
def cloneVm(s,baseUri,templateVm,vmName,repoName,serverPool):

    print "\nClone VM Template "+templateVm+" to "+ vmName
    print "##################################################"

    repo_id = get_id_from_name(s,baseUri,'Repository',repoName)

    sp_id = get_id_from_name(s,baseUri,'ServerPool',serverPool)
    template_id = get_id_from_name(s,baseUri,'Vm',templateVm)

    data = {}
    data['serverPoolId'] = sp_id
    data['repositoryId'] = repo_id
    data['createTemplate'] = False

    uri = '{base}/Vm/{vmId}/clone?{params}'.format(base=baseUri,vmId=template_id,params=urlparse.urlencode(data))
    r = s.put(uri)
    job = r.json()

    # wait for the job to complete
    vm_id = wait_for_job(job['id']['uri'],s)
    print "new vm id:" + json.dumps(vm_id, indent=2)
    print

    ## change vm name
    print '\nChange '+vm_id['name']+' to '+vmName
    print "########################################"

    data = {'name':vmName, 'id':vm_id}
    r1 = s.put(baseUri+'/Vm/'+vm_id['value'],data=json.dumps(data))
    job = r1.json()
    # wait for the job to complete
    wait_for_job(job['id']['uri'],s)

    ## change the VM Virtual Disk Names
    uri = '{base}/Vm/{vmId}'.format(base=baseUri,vmId=vm_id['value'])
    print uri
    r = s.get(uri)
    vm = r.json()

    dNum=0
    for disk in vm['vmDiskMappingIds']:
        dNum = dNum + 1
        if dNum == 1:
            newDiskName = vm['name']+'-xvda.img'
        else:
            newDiskName = vm['name']+'-xvdb.img'

        dMapping=s.get(baseUri+'/VmDiskMapping/'+disk['value'])
        dm=dMapping.json()
        updateVirtualDisk(s,baseUri,dm['virtualDiskId']['value'],newDiskName)

def listVmDisks(s,baseUri,vmName):

    vm_id = get_id_from_name(s,baseUri,'Vm',vmName)
    uri = '{base}/Vm/{vmId}'.format(base=baseUri,vmId=vm_id)
    print uri
    r = s.get(uri)
    vm = r.json()

    for dMapping in vm['vmDiskMappingIds']:
        r = s.get(dMapping['uri'])
        print json.dumps(r.json(), indent=2)

### Add ASM LUNs to the VM
def attachAsmLuns(s,baseUri,vmName,vols,clusterName):

    vm_id = get_id_from_name(s,baseUri,'Vm',vmName)

    for vol in vols:
        ### Get DATA Disks
        se_id = get_id_from_name(s,baseUri,'StorageElement',clusterName+"-"+vol['volume'])
        uri='{base}/StorageElement/{seid}'.format(base=baseUri,seid=se_id)
        r=s.get(uri)

        se_data = r.json()

        ### Make sure disk is sharable
        if se_data['shareable'] == False:
            print "\nMaking Disk "+se_data['name']+" Shareable"
            print "##########################################"
            se_data['shareable'] = True
            r = s.put(baseUri+'/StorageElement/'+se_data['id']['value'],data=json.dumps(se_data))
            job = r.json()
            # wait for the job to complete
            wait_for_job(job['id']['uri'],s)

        dMapping = {}
        dMapping['storageElementId'] = se_data['id']
        dMapping['diskTarget'] = vol['disktarget']

        print "\nAdding disk "+se_data['name']+" to "+vmName+" in slot "+vol['disktarget']
        print "##########################################"
        uri = '{base}/Vm/{vmId}/VmDiskMapping'.format(base=baseUri,vmId=vm_id)
        r = s.post(uri,data=json.dumps(dMapping))
        job = r.json()
        wait_for_job(job['id']['uri'],s)


parser = OptionParser(usage="usage: %prog [options]", version="%prog 1.0")

parser.add_option("-u", "--username", dest="username", help="User for logging into OVM Manager")
parser.add_option("-p", "--password", dest="passwd", help="Password for logging into OVM Manger")
parser.add_option("-s", "--server", dest="server", help="FQDN of OVM Manager")
parser.add_option("--vm", action="append", dest="vms", help="Virtual Machines to create")
parser.add_option("--repo", dest="repo", help="OVM Repository to Create the VMs")
parser.add_option("--serverpool", dest="serverpool", help="OVM ServerPool to create the VMs")
parser.add_option("--template", dest="template", help="OVM VM Template to clone VMs from")
parser.add_option("--cluster", dest="cluster", help="Cluster name")
parser.add_option("-f", "--file", dest="file", help="Path to properties file with Volume Definitions")


(options, args) = parser.parse_args(sys.argv)

properties = options.file

###  Create Connection to OVM Mangaer #####
s=requests.Session()
s.auth=(options.username, options.passwd)
s.verify=False

s.headers.update({'Accept': 'application/json', 'Content-Type': 'application/json'})

baseUri='https://'+options.server+':7002/ovm/core/wsapi/rest'
############################################

with open(properties) as json_data_file:
    vols = json.load(json_data_file)

check_manager_state(baseUri,s)
for vm in options.vms:
    cloneVm(s,baseUri,options.template,vm,options.repo,options.serverpool)
    attachAsmLuns(s,baseUri,vm,vols,options.cluster)
