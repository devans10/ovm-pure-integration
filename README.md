# ovm-pure-integration
Scripts for automating Pure Storage and Oracle VM

These scripts utilize the [Pure Storage Python Rest Client](https://github.com/purestorage/rest-client) for connecting to the Pure FlashArray, and they use Oracle VM Rest API for connecting to OVM Manager.

These scripts were created to automate the disk and VM creation for building Virtual Machines to be used with Oracle's [deploycluster tool](http://www.oracle.com/technetwork/server-storage/vm/database-templates-12c-11gr2-1972804.html) for creating Single Instance and RAC Databases.  The volumes being created are to be used as ASM disks.  Each database has its own ASM diskgroup to allow us to utilize the snapshot cloning capability of the Pure FlashArray.

#### Assumptions
1. Both the FlashArray and OVM Manager are able to be logged into with the same username and password.  In our case, they are both authenticated via Active Directory.
2. The OVM Serverpool and FlashArray hostgroup have the same name. 
3. The Pure FlashArray has been discovered by OVM, and has been given its FQDN as the SAN Server in OVM Manager.

### createVmLuns.py
This script creates volumes on the Pure Flash Array, connects them to the given hostgroup, refreshes the Storage Array in OVM, then renames the StorageElements in OVM to match what is defined in the FlashArray.  The -f flag defines a JSON properties file that gives a template of volumes to be created that are prefixed with the "--name" argument.  This allows us to keep the initial storage on our servers consistent.  This also creates protection groups and adds the volumes to those groups.  There is a sample JSON properties files in the repo.

Options:
  * --version             show program's version number and exit
  * -h, --help            show this help message and exit
  * -n NAME, --name=NAME  Oracle Database Host or Cluster Name
  * -g HOSTGROUP, --hostgroup=HOSTGROUP
                        Pure Storage HostGroup
  * -a ARRAY, --array=ARRAY
                        Pure Storage Array
  * -u USERNAME, --username=USERNAME
                        User for logging into OVM Manager
  * -p PASSWD, --password=PASSWD
                        Password for logging into OVM Manger
  * -s SERVER, --server=SERVER
                        FQDN of OVM Manager
  * -f FILE, --file=FILE  Path to properties file with Volume Definition
  
  ### createVms.py
  This script creates VMs from a given template, renames the OS and Application Virtual Disks, then attaches the Pure Volumes as Physical Disks that are passed through Dom0 to the VM.  
  
  Options:
  * --version             show program's version number and exit
  * -h, --help            show this help message and exit
  * -u USERNAME, --username=USERNAME
                        User for logging into OVM Manager
  * -p PASSWD, --password=PASSWD
                        Password for logging into OVM Manger
  * -s SERVER, --server=SERVER
                        FQDN of OVM Manager
  * --vm=VMS              Virtual Machines to create (can be repeated)
  * --repo=REPO           OVM Repository to Create the VMs
  * --serverpool=SERVERPOOL
                        OVM ServerPool to create the VMs
  * --template=TEMPLATE   OVM VM Template to clone VMs from
  * --cluster=CLUSTER     Cluster name
  * -f FILE, --file=FILE  Path to properties file with Volume Definitions

  
