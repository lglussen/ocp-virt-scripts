#!/usr/bin/env python
import os
import json
import subprocess
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('src', help="source namespace where VMs currently exist")
parser.add_argument('dest', help="destination namespace: the target namespace of the VM migration / cloning operation")
parser.add_argument('--output-dir', default=".", help="path to write new VM configuration files")

class KS_Object:

    def __init__(self, json_s):
        self.data = json.loads(json_s)
    
    def delete(self, reference):
        data = self.data
        args =  reference.lstrip(".").split('.')
        for x in args:
            try:
                parent = data
                data = data[x]
            except KeyError:
                return
        parent.pop(args[-1])

    def set(self, name, value):

        args = name.lstrip(".").split(".")
        for x in args:
            try:
                parent = data
                data = data[x]
            except KeyError:
                data[x] = {}
                data = data[x]
        parent[args[-1]] = value

    
    def delete_any(self, keyname):
        def walk(d):
            values = []
            if isinstance(d, dict):
                for k in list(d.keys()):
                    if k == keyname:
                        del d[k]
                    else: walk(d[k])
            if isinstance(d, list) or isinstance(d, tuple):
                for x in d: walk(x)

class VM_NamespaceMigration:
    def __init__(self, source, dest):
        self.source_namespace = source
        self.dest_namespace = dest
        try:
            subprocess.run(['oc', 'status'], check=True)
        except Exception as e:
            print("Ensure `oc` is on the system path AND is logged into the target cluster")
            exit(-1)

        
    def oc_get_vm(self, name):
        result = subprocess.run(['oc', 'get', 'vm', name, '-n', self.source_namespace, '-o', 'json'], capture_output=True, text=True, check=True)
        return VM(result.stdout)
    
    def oc_get_dv(self, name):
        result = subprocess.run(['oc', 'get', 'datavolume', name, '-n', self.source_namespace, '-o', 'json'], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    
    def oc_get_pvc_storage(self, name):
        result = subprocess.run(['oc', 'get', 'pvc', name, '-n', self.source_namespace, '-o', 'json'], capture_output=True, text=True, check=True)
        pvc = json.loads(result.stdout)
        return pvc['status']['capacity']['storage']
    
    def convert_volumes_to_dv_clones(self, vm):

        dataVolumeTemplates = []
        volumes = []

        for volume in vm.data['spec']['template']['spec']['volumes']:
            
            if 'persistentVolumeClaim' in volume:
                pvc = volume['persistentVolumeClaim']['claimName'] 
            elif 'dataVolume' in volume:
                dv = self.oc_get_dv(volume['dataVolume']['name'])
                pvc = dv['status.claimName']
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
        def delete(data, reference):
            args = reference.split('.')
            for x in args:
                try:
                    parent = data
                    data = data[x]
                except KeyError:
                    return
            parent.pop(args[-1])

        vm = self.oc_get_vm(name)
        vm.delete("status")
        vm.delete('spec.preference.revisionName')
        vm.set('metadata', { 'name': name, 'namespace': self.dest_namespace })
        vm.delete_any("macAddress")

        # convert each volume entry into a DataVolume with a corresponding DataVolumeTemplate
        # entry referencing the original volumes backing PVC
        self.convert_volumes_to_dv_clones(vm)

        return vm.data
    


args = parser.parse_args()

result = subprocess.run(['oc', 'get', 'vm' '-n', args.src, '-o', 'json'], capture_output=True, text=True, check=True)
vms = json.loads(result.stdout)
migrate = VM_NamespaceMigration(args.src, args.dest)
for vm in vms['items']:
    vm_name = vm['metadata']['name']
    clone = migrate.transform(vm_name)
    with open(os.path.join(args.output_dir, f"clone-{vm_name}.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(clone, indent=4))