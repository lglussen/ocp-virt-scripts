import json
import os
import subprocess

class oc:

    @staticmethod
    def _run(cmd, comment=None, **kwargs):
        output = " ".join(cmd)
        if comment: output += f" # {comment}"
        print(output)
        return subprocess.run(cmd, check=True, **kwargs)

    @staticmethod
    def delete(kind, name, namespace):
        oc._run(['oc', 'delete', kind, name, '-n', namespace])

    @staticmethod
    def create_if_not_exists(object):
        args = ["oc", "get", object['kind'], object['metadata']['name']]
        if "namespace" in object['metadata']:
            args += ['-n', object['metadata']['namespace']]
        try:
            oc._run(args)
        except Exception as e:
            oc._run(["oc", "apply", "-f", "-"], input=json.dumps(object).encode())

    @staticmethod
    def get(kind, name, namespace, *, comment=None):
        result = oc._run(['oc', 'get', kind, name, '-n', namespace, '-o', 'json'], comment, capture_output=True, text=True)
        return json.loads(result.stdout)

    @staticmethod
    def get_all(kind, namespace):
        result = oc._run(['oc', 'get', kind, '-n', namespace, '-o', 'json'], capture_output=True, text=True)
        return json.loads(result.stdout)['items']

    @staticmethod
    def status_check():
        try:
            oc._run(['oc', 'status'], capture_output=True)
        except Exception as e:
            print(e)
            print("Ensure `oc` is on the system path AND is logged into the target cluster")
            exit(-1)

    @staticmethod
    def apply(data):
        print(" ".join(["oc", "apply", "-f", "-"]))
        oc._run(["oc", "apply", "-f", "-"], input=json.dumps(data).encode())

    @staticmethod
    def patch(kind, name, namespace, patch):
        oc._run(["oc", "patch", "-n", namespace, f'{kind}/{name}', '--type', 'json', '--patch', patch ])
        

class Kube_Object:

    def __init__(self, data):
        self.data = data

    def save(self):
        oc.apply(self.data)

    def name(self):
        return self.data['metadata']['name']
    
    def kind(self):
        return self.data['kind']

    def namespace(self):
        return self.data['metadata']['namespace']

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

    def get(self, selector):
        data = self.data
        args = selector.lstrip(".").split(".")
        for x in args:
            data = data[x]
        return data

    def set(self, name, value):
        data = self.data
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
        def _delete_any(d):
            if isinstance(d, dict):
                for k in list(d.keys()):
                    if k == keyname:
                        del d[k]
                    else: _delete_any(d[k])
            if isinstance(d, list) or isinstance(d, tuple):
                for x in d: _delete_any(x)
        _delete_any(self.data)


    def write(self, output_dir=".", name=None):
        if name is None:
            name = f"{self.kind()}.{self.name()}"
        try:
            import yaml
            with open(os.path.join(output_dir, f"{name}.yaml"), 'w', encoding='utf-8') as f:
                yaml.dump(self.data, f)
        except:
            with open(os.path.join(output_dir, f"{name}.json"), 'w', encoding='utf-8') as f:
                    f.write(json.dumps(self.data, indent=4))


class VM(Kube_Object):

    def patch(self, p):
        oc.patch(self.kind(), self.name(), self.namespace(), p)

    def datavolume_sanity_check(self):
        for volume in self.get("spec.template.spec.volumes"):
            if "dataVolume" in volume:
                datavolume_name = volume['dataVolume']['name']
                dv = oc.get("datavolume", datavolume_name, self.namespace(), comment="Getting the .status.phase value to ensure Import is complete")
                if dv['status']['phase'] != 'Succeeded':
                    print(f"[WARNING] datavolume/{datavolume_name} import phase is '{dv['status']['phase']}'")
                    if dv['status']['phase'] == 'PendingPopulation':
                        print("[WARNING] PendingPopulation indicates the process has not started.  You will need to start the VM initiate the import process")
                    else:
                        print("[WARNING] you may want to wait for progress to complete and for the phase to change to Success")
                        print("          run 'oc get datavolume' to see the PHASE and PROGRESS of your datavolume imports in your target namespace")
                    answer = input("Are you sure you want to continue? [y/N]: ")
                    if answer.lower() == "y" or answer.lower() == 'yes':
                        continue
                    else:
                        print("Stopping execution ...")
                        exit()


    def dv_to_pvc(self, *, apply=False, output_dir='.'):
        self.datavolume_sanity_check()
        
        # not really necessary to do to the local object except for generating an output file
        self.delete("spec.dataVolumeTemplates")
        datavolumes = []
        for volume in self.get("spec.template.spec.volumes"):
            if "dataVolume" in volume:
                datavolume_name = volume['dataVolume']['name']
                datavolumes.append(datavolume_name)
                dv = oc.get("datavolume", datavolume_name, self.namespace(), comment="getting the .status.claimName to find the backing PVC")
                volume['persistentVolumeClaim'] = { 'claimName': dv['status']['claimName'] }
                del volume['dataVolume']
                
        if apply:
            # running patch to delete dataVolumeTemplates because the 3 way merge of applying the self.data doesn't remove the element
            patch = [{
                "op":"remove", 
                "path": "/spec/dataVolumeTemplates" 
                },{
                "op": "replace", 
                "path": "/spec/template/spec/volumes",
                "value": self.get("spec.template.spec.volumes")
                }
            ]
            self.patch(json.dumps(patch, indent=4))
            for dv in datavolumes:
                oc.delete('datavolume', dv, self.namespace())
        else:
            self.write(output_dir)
            
                
