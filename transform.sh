export VM_NAME=$1
export SOURCE_NAMESPACE=$2
export TARGET_NAMESPACE=$3
source lib/virtualmachine.sh

mkdir -p source_vm
mkdir -p dest_vm
SOURCE=source_vm/${VM_NAME}.yaml

# Get the existing Virtual Machine configuration
oc get virtualmachine $VM_NAME -n $SOURCE_NAMESPACE -o yaml > ${SOURCE}

if assert_single_pvc_volume ${SOURCE}; then 
    export PVC=$(yq '.spec.template.spec.volumes[0].persistentVolumeClaim.claimName' ${SOURCE})
elif assert_dv_plus_cloud_init  ${SOURCE}; then
    DV_NAME=$(yq '.spec.template.spec.volumes[] | select(.dataVolume).dataVolume.name' ${SOURCE}) 
    echo "DV_NAME: $DV_NAME"
    export PVC=$(oc get datavolume $DV_NAME -n $SOURCE_NAMESPACE -o yaml | yq '.status.claimName')
    echo "PVC:  $PVC"
else 
  exit -1
fi

export PVC_STORAGE=$(oc get pvc $PVC -n $SOURCE_NAMESPACE -o yaml | yq '.status.capacity.storage')
echo "PVC_STORAGE:  $PVC_STORAGE"

export DV_CLONE="${VM_NAME}-${SOURCE_NAMESPACE}-clone"
echo "DV_CLONE: $DV_CLONE"

# Transform source configuration to destination configuration

yq 'del(.status) | 
    del(.metadata) | 
    del(.. | select(has("macAddress")).macAddress) |
    .metadata = { "namespace": strenv(TARGET_NAMESPACE), "name": strenv(VM_NAME) } |
    .spec.dataVolumeTemplates = {
        "metadata":{"name": strenv(DV_CLONE)},
        "spec": {
                "storage": { 
                    "accessModes": [ "ReadWriteOnce" ], 
                    "resources": { "requests": { "storage": strenv(PVC_STORAGE) }}
                },
                "source": {"pvc": {"namespace": strenv(SOURCE_NAMESPACE), "name":strenv(PVC) }}
        }
    } |
    .spec.template.spec.volumes = { "dataVolume": { "name": strenv(DV_CLONE) }, "name": "root-disk" } |
    .spec.template.spec.domain.devices.disks[0].name = "root-disk"
   ' ${SOURCE} > dest_vm/new-${VM_NAME}.yaml
