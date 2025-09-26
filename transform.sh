#!/usr/bin/bash

export VM_NAME=$1
export SOURCE_NAMESPACE=$2
export TARGET_NAMESPACE=$3
source lib/virtualmachine.sh

mkdir -p source_vm dest_vm
VM_YAML=source_vm/${VM_NAME}.yaml

# Get the existing Virtual Machine configuration
oc get virtualmachine $VM_NAME -n $SOURCE_NAMESPACE -o yaml > $VM_YAML

# exports PVC, PVC_STORAGE, DV_CLONE
set_VARS $VM_YAML

# Transform source configuration to destination configuration
yq 'del(.status) | 
    del(.metadata) | 
    del(.. | select(has("macAddress")).macAddress) |
    del(.spec.preference.revisionName) |
    .metadata = { "namespace": strenv(TARGET_NAMESPACE), "name": strenv(VM_NAME) } |
    .spec.dataVolumeTemplates = [{
        "metadata":{"name": strenv(DV_CLONE)},
        "spec": {
                "storage": { 
                    "accessModes": [ "ReadWriteOnce" ], 
                    "resources": { "requests": { "storage": strenv(PVC_STORAGE) }}
                },
                "source": {"pvc": {"namespace": strenv(SOURCE_NAMESPACE), "name":strenv(PVC) }}
        }
    }] |
    .spec.template.spec.volumes = [{ "dataVolume": { "name": strenv(DV_CLONE) }, "name": "root-disk" }] |
    .spec.template.spec.domain.devices.disks[0].name = "root-disk"
   ' ${VM_YAML} > dest_vm/new-${VM_NAME}.yaml
