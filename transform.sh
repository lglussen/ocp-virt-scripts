export VM_NAME=$1
export SOURCE_NAMESPACE=$2
export TARGET_NAMESPACE=$3
source lib/virtualmachine.sh

# Get the existing Virtual Machine configuration
oc get virtualmachine $VM_NAME -n $SOURCE_NAMESPACE -o yaml > ${VM_NAME}.yaml

if assert_single_pvc_volume ${VM_NAME}.yaml; then 
    export PVC=$(yq '.spec.template.spec.volumes[0].persistentVolumeClaim.claimName' ${VM_NAME}.yaml)
elif assert_dv_plus_cloud_init  ${VM_NAME}.yaml; then
    DV_NAME=$(yq '.spec.template.spec.volumes[] | select(.dataVolume).dataVolume.name)' ${VM_NAME}.yaml) 
    export PVC=$(oc get datavolume $DV_NAME -n $SOURCE_NAMESPACE -o yaml | yq '.status.claimName')
else 
  exit -1
fi

export PVC_STORAGE=$(oc get pvc $PVC -n $SOURCE_NAMESPACE -o yaml | yq '.status.capacity.storage')

mkdir -p new_vm_config

# get the Persistent Volume Claim (PVC) name

export PVC_STORAGE=30Gi
export DV_CLONE="${VM_NAME}-${SOURCE_NAMESPACE}-clone"
# Transform source configuration to destination configuration
yq 'del(.status) | 
    del(.metadata) | 
    del(.. | select(has("macAddress")).macAddress) |
    .metadata = { "namespace": strenv(TARGET_NAMESPACE), "name": strenv(VM_NAME) } |
    .spec.dataVolumeTemplates = {
        "metadata":{"name": strenv(DV_CLONE)},
        "spec": {
                "storage": { 
                    "accessModes": [ ReadWriteOnce ], 
                    "resources": { "requests": { "storage": strenv(PVC_STORAGE) }
                },
                "source": {"pvc": {"namespace": strenv(SOURCE_NAMESPACE), "name":strenv(PVC) }}
        }
    }
   ' ${VM_NAME}.yaml > new_vm_config/new-${VM_NAME}.yaml

 
