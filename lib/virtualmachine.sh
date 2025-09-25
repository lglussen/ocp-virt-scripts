function assert_single_pvc_volume {
  NUM_VOLUMES=$(yq '.spec.template.spec.volumes | length' ${1})
  if [ "$NUM_VOLUMES" == "1" ]; then echo "single PVC volume configuration detected"; else
    echo "unsupported case with multiple volumes. "
    return -1
  fi
}

function assert_dv_plus_cloud_init {
	ASSERT_DV=$(yq '.spec.template.spec.volumes[] | select(.dataVolume) | has("name")' $1)
	ASSERT_CINC=$(yq '.spec.template.spec.volumes[] | select(.cloudInitNoCloud) | has("userData")' $1)
	ASSERT_NV_2=$(yq '.spec.template.spec.volumes | length' ${1})
	if [ "${ASSERT_DV}" == "true" && "${ASSERT_CINC}" == "true" && "${ASSERT_NV_2}" == "2" ]; then
	  echo "known configuration"
	else
	  echo Not of standard Datavolume+CloudInitNoCloud configuration
	  return -1
	fi
}

