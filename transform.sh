export VM_NAME=$1
export SOURCE_NAMESPACE=openshift-mtv
export TARGET_NAMESPACE=my-namespace

# Get the existing Virtual Machine configuration
#oc get virtualmachine $VM_NAME -n $SOURCE_NAMESPACE -o yaml > ${VM_NAME}.yaml

# Ensure the machine only has one Volume as this script is currently written with that assumption
NUM_VOLUMES=$(yq '.spec.template.spec.volumes | length' ${VM_NAME}.yaml)
if [ "$NUM_VOLUMES" == "1" ]; then echo OK; else 
  echo "unsupported case with multiple volumes. will have to "
  exit -1  
fi

# get the Persistent Volume Claim (PVC) name
export PVC=$(yq '.spec.template.spec.volumes[0].persistentVolumeClaim.claimName' ${VM_NAME}.yaml)

# Transform source configuration to destination configuration
yq 'del(.status) | 
    del(.metadata) | 
    del(.. | select(has("macAddress")).macAddress) |
    .metadata = { "namespace": strenv(TARGET_NAMESPACE), "name": strenv(VM_NAME) }
   ' ${VM_NAME}.yaml > new-${VM_NAME}.yaml





