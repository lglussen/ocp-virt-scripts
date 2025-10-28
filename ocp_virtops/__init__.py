import json
import os
import subprocess

class oc:

    @staticmethod
    def delete(ktype, name, namespace):
        subprocess.run(['oc', 'delete', ktype, name, '-n', namespace], check=True)

    @staticmethod
    def create_if_not_exists(object):
        args = ["oc", "get", object['kind'], object['metadata']['name']]
        if "namespace" in object['metadata']:
            args += ['-n', object['metadata']['namespace']]
        try:
            subprocess.run(args, capture_output=True, check=True)
        except Exception as e:
            subprocess.run(["oc", "apply", "-f", "-"], input=json.dumps(object).encode(), check=True)

    @staticmethod
    def get(ktype, name, namespace):
        print(" ".join(['oc', 'get', ktype, name, '-n', namespace, '-o', 'json']))
        result = subprocess.run(['oc', 'get', ktype, name, '-n', namespace, '-o', 'json'], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    @staticmethod
    def get_all(ktype, namespace):
        result = subprocess.run(['oc', 'get', ktype, '-n', namespace, '-o', 'json'], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)['items']

    @staticmethod
    def status_check():
        try:
            subprocess.run(['oc', 'status'], check=True, capture_output=True)
        except Exception as e:
            print("Ensure `oc` is on the system path AND is logged into the target cluster")
            exit(-1)

    @staticmethod
    def apply(data):
        print(" ".join(["oc", "apply", "-f", "-"]))
        subprocess.run(["oc", "apply", "-f", "-"], input=json.dumps(data).encode(), check=True)


class Kube_Object:

    def __init__(self, data):
        self.data = data

    def save(self):
        oc.apply(self.data)
        #subprocess.run(["oc", "apply", "-f", "-"], input=json.dumps(self.data).encode(), check=True)

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

    def dv_to_pvc(self, *, apply=False, delete_dv=False):
        self.delete("spec.dataVolumeTemplates")
        for volume in self.get("spec.template.spec.volumes"):
            if "dataVolume" in volume:
                datavolume_name = volume['dataVolume']['name']
                dv = oc.get("datavolume", datavolume_name, self.namespace())
                volume['persistentVolumeClaim'] = { 'claimName': dv['status']['claimName'] }
                del volume['dataVolume']
                if delete_dv:
                    oc.delete('datavolume', datavolume_name, self.namespace())
                    print("datavolume deleted ...")
                else:
                    print(f"Old Datavolume may be deleted now if desired: oc delete datavolume/{datavolume_name} -n {self.namespace()}")
                if apply:
                    oc.apply(self.data)
                    print("changes applied to VM")
                
