SOURCE=$1
DEST=$2

cat << EOF  | oc apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: datavolume-cloner
rules:
- apiGroups: ["cdi.kubevirt.io"]
  resources: ["datavolumes/source"]
  verbs: ["*"]
EOF

cat << EOF  | oc apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: datavolume-cloner
  namespace: $SOURCE
subjects:
- kind: ServiceAccount
  name: default
  namespace: $DEST
roleRef:
  kind: ClusterRole
  name: datavolume-cloner
  apiGroup: rbac.authorization.k8s.io
EOF