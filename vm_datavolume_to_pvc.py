#!/usr/bin/env python
from argparse import ArgumentParser
from ocp_virtops import VM
from ocp_virtops import oc


parser = ArgumentParser(description="Migrate VMs between Namespaces. Default strategy is to create a VM clone in the new namespace as this is the least destructive to the source VM and therefore the safest approach. Some options, such as preserving NIC MAC addresses will necessitate making changes to the source VM as OpenShift will not allow the same MAC to be held by more than one machine at a time. ")
parser.add_argument('vm', help="vm to convert datavolume configuration to pure PVC configuration")
parser.add_argument('-n', '--namespace', dest="namespace", required=True, help="source namespace where VMs currently exist")
parser.add_argument('--output-dir', default=".", help="path to write new VM configuration files")
parser.add_argument('--apply', action='store_true', default=False, help='directly apply changes rather than generating output')
parser.add_argument('--delete-dv', action='store_true', default=False, help="delete the datavolume object")
#parser.add_argument('--preserve-mac', action='store_true', default=False, help="Remove NIC mac addresses from old vm and apply it to new Cloned VM. The old VM will end up with new randomly assigned MAC addresses for its NICs" )
#parser.add_argument('--direct-migration', action='store_true', default=False, help="[NOT IMPLEMENTED] don't clone data - directly reference the PV of the source VM")

args = parser.parse_args()
oc.status_check()

vm = VM(oc.get("vm", args.vm, args.namespace))
vm.dv_to_pvc(apply=args.apply, delete_dv=args.delete_dv)
if not args.apply:
    vm.write(args.output_dir)