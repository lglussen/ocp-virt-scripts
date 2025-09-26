function assert_single_pvc_volume {
  local NUM_VOLUMES=$(yq '.spec.template.spec.volumes | length' ${1})
  if [ "$NUM_VOLUMES" == "1" ]; then echo "single PVC volume configuration detected"; else
    echo -e "\tcase with multiple volumes. "
    return -1
  fi
}

function assert_dv_plus_cloud_init {
	ASSERT_DV=$(yq '.spec.template.spec.volumes[] | select(.dataVolume) | has("name")' $1)
	ASSERT_CINC=$(yq '.spec.template.spec.volumes[] | select(.cloudInitNoCloud) | has("cloudInitNoCloud")' $1)
	ASSERT_NV_2=$(yq '.spec.template.spec.volumes | length' ${1})
	if [ "${ASSERT_DV}" == "true" ] && [ "${ASSERT_CINC}" == "true" ] && [ "${ASSERT_NV_2}" == "2" ]; then
	  echo -e "\tknown DataVolume + CloudInitNoCloud configuration: proceeding ..."
	else
	  echo -e "\tNot a DataVolume + CloudInitNoCloud 2 volume configuration"
	  return -1
	fi
}

function set_VARS {
	local YAML_FILE=$1
	local NAMESPACE=$(yq .metadata.namespace $YAML_FILE)
	local NAME=$(yq .metadata.name $YAML_FILE)
	if assert_single_pvc_volume ${YAML_FILE}; then 
		# the typical migrated VM
		export PVC=$(yq '.spec.template.spec.volumes[0].persistentVolumeClaim.claimName' ${YAML_FILE})
	elif assert_dv_plus_cloud_init  ${YAML_FILE}; then
		# if we are here it is because we are testing vms that were probably provisioned directly in opneshift and not something that was imported
		# TODO: if we here, this solution is currently dependent on the disk order. see: ...devices.disks[0].name
		DV_NAME=$(yq '.spec.template.spec.volumes[] | select(.dataVolume).dataVolume.name' ${YAML_FILE}) 
		echo "DV_NAME: $DV_NAME"
		export PVC=$(oc get datavolume $DV_NAME -n $NAMESPACE -o yaml | yq '.status.claimName')
	else
	# special case migrated VMs with multiple disks. Out of scope.
		echo -e "\t[WARN] skipping transform for untested / unexplored multi volume configuration"
	    exit -1
	fi

	export PVC_STORAGE=$(oc get pvc $PVC -n $NAMESPACE -o yaml | yq '.status.capacity.storage')
	export DV_CLONE="${NAME}-${NAMESPACE}-clone"

	echo "\tPVC_STORAGE:  $PVC_STORAGE"
	echo "\tDV_CLONE: $DV_CLONE"
	echo "\tPVC:  $PVC"
	
}