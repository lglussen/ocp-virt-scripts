#!/usr/bin/env python
import os
import json
import subprocess
from argparse import ArgumentParser
from ocp_virtops import VM 
from ocp_virtops import oc

parser = ArgumentParser(description="Migrate VMs between Namespaces. Default strategy is to create a VM clone in the new namespace as this is the least destructive to the source VM and therefore the safest approach. Some options, such as preserving NIC MAC addresses will necessitate making changes to the source VM as OpenShift will not allow the same MAC to be held by more than one machine at a time. ")
parser.add_argument('src', help="source namespace where VMs currently exist")
parser.add_argument('dest', help="destination namespace: the target namespace of the VM migration / cloning operation")
parser.add_argument('-o', '--output-dir', dest="output_dir", default=".", help="path to write new VM configuration files")
parser.add_argument('--preserve-mac', action='store_true', default=False, help="Preserve MAC addresses on NICS. You will be responsible for manually changing the MAC on the source VM before creating the clone VM")
parser.add_argument('--name', default=False, help='run against only one specific VM rather than the entire namespace')
parser.add_argument('--direct-migration', action='store_true', default=False, help="[NOT IMPLEMENTED] don't clone data - directly reference the PV of the source VM")



class NamespaceMigration():
    def __init__(self, args):
        self.source_namespace = args.src
        self.dest_namespace = args.dest
        self.name = args.name

    def create_if_not_exists(self, object):
        args = ["oc", "get", object['kind'], object['metadata']['name']]
        if "namespace" in object['metadata']:
            args += ['-n', object['metadata']['namespace']]
        try:
            subprocess.run(args, capture_output=True, check=True)
        except Exception as e:
            subprocess.run(["oc", "apply", "-f", "-"], input=json.dumps(object).encode(), check=True)

    def get_all(self):
        return  oc.get_all(self.kind(), self.source_namespace)

    def generate_pvc_files(self, output_dir):
        pass
    
    def generate_clone_files(self, output_dir):

        for obj in self.get_all():
            name = obj['metadata']['name']
            if self.name and self.name != name:
                continue

            clone = self.transform(name)
            try:
                import yaml
                with open(os.path.join(output_dir, f"{name}.{self.kind()}-clone.yaml"), 'w', encoding='utf-8') as f:
                    yaml.dump(clone, f)
            except:
                with open(os.path.join(output_dir, f"{name}.{self.kind()}-clone.json"), 'w', encoding='utf-8') as f:
                    f.write(json.dumps(clone, indent=4))
    

    def transform(self, name) -> dict: pass

    

class VM_NamespaceMigration(NamespaceMigration):

    def __init__(self, args):
        super().__init__(args)
        self.preserve_mac = args.preserve_mac
        

    def kind(self):
        return "vm"

    def set_permissions(self):
        name = "datavolume-cloner"
        cluster_role = {
            'apiVersion': 'rbac.authorization.k8s.io/v1','kind': 'ClusterRole',
            'metadata': { 'name': name },
            'rules':[{
                'apiGroups': ["cdi.kubevirt.io"],
                'resources': ["datavolumes/source"],
                'verbs': ["*"]
            }]
        }
        role_binding = {
            "apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding",
            "metadata": { "name": f"{name}-{self.dest_namespace}", "namespace": self.source_namespace },
            "subjects": [{ "kind": "ServiceAccount", "name": "default", "namespace": self.dest_namespace }],
            "roleRef": { "kind": "ClusterRole", "name": name, "apiGroup": "rbac.authorization.k8s.io" }
        }
        self.create_if_not_exists(cluster_role)
        self.create_if_not_exists(role_binding)
        
    def oc_get_vm(self, name):
        return VM(oc.get("vm", name, self.source_namespace))
    
    def oc_get_dv(self, name): 
        return oc.get("datavolume", name, self.source_namespace)
    
    def oc_get_pvc_storage(self, name):
        pvc = oc.get("pvc", name, self.source_namespace)
        return pvc['status']['capacity']['storage']
    
    def convert_volumes_to_dv_clones(self, vm):

        dataVolumeTemplates = []
        volumes = []

        for volume in vm.data['spec']['template']['spec']['volumes']:
            
            if 'persistentVolumeClaim' in volume:
                pvc = volume['persistentVolumeClaim']['claimName'] 
            elif 'dataVolume' in volume:
                dv = self.oc_get_dv(volume['dataVolume']['name'])
                pvc = dv['status']['claimName']
            else:
                raise Exception(f"UNKNOWN VOLUME TYPE: {json.dumps(volume)}")
            dv_clone_name = f"{pvc}-{self.source_namespace}"
            volumes.append({
                    "dataVolume": { "name": dv_clone_name }, 
                    "name": volume['name'] 
            })
            dataVolumeTemplates.append({
                "metadata":{ "name": dv_clone_name },
                "spec": {
                    "storage": { 
                        "accessModes": [ "ReadWriteOnce" ], 
                        "resources": { "requests": { "storage": self.oc_get_pvc_storage(pvc) }}
                    },
                    "source": {"pvc": {"namespace": self.source_namespace, "name": pvc }}
                }
            })
        vm.set("spec.template.spec.volumes", volumes)
        vm.set("spec.dataVolumeTemplates", dataVolumeTemplates)

    def transform(self, name):
        vm = self.oc_get_vm(name)

        # Remove Status --------------------------------------------------------
        vm.delete("status")

        # Remove revisionName as it seems to cause issues ----------------------
        vm.delete('spec.preference.revisionName')

        # Sanitize Metadata and Change Namespace -------------------------------
        # We completely wipe metadata of everything except the essentials (name / namespace)
        # this approach seems the simplest. in the off-chance that labels or other metadata are needed - they can be added back manually
        vm.set('metadata', { 'name': name, 'namespace': self.dest_namespace })

        # NIC MAC Address strategy ---------------------------------------------
        if self.preserve_mac: 
            pass # manually change mac address in source vm
            # we could try to automatically do it here, but we would need to ensure the machine was off
        else:
            vm.delete_any("macAddress") # src vm keeps the original MAC

        # Stop the VMs ---------------------------------------------------------
        # and ensure to remove the deprecated "running" as that can cause issues with 
        vm.delete("spec.template.spec.running") # removing deprecated "running"
        vm.set("spec.template.spec.runStrategy", "Halted")

        # convert each volume entry into a DataVolume with a corresponding DataVolumeTemplate
        # entry referencing the original volumes backing PVC
        self.convert_volumes_to_dv_clones(vm)
        return vm.data
        #return {
        #    'kind': "List",
        #    'metadata': {"resourceVersion":""},
        #    'apiVersion': "v1",
        #    'items': [vm_src.data, vm_new.data]
        #}

args = parser.parse_args()

migrate = VM_NamespaceMigration(args)
oc.status_check()
migrate.set_permissions()
migrate.generate_clone_files(args.output_dir)
