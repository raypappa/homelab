#!/bin/bash

namespace=$1
if [[ -z $namespace ]];then
    echo missing namespace;
    exit 1
fi

kubectl api-resources --namespaced=true -o json | jq '.resources[].name' -r | while read kind;do
  kubectl delete -n $namespace $kind --all --wait=false --force
  kubectl get -n $namespace $kind -o json | jq '.items[].metadata.name' -r | while read item;do
    kubectl delete -n $namespace $kind/$item --force=true --wait=false
  done
done

kubectl delete namespace $namespace --wait=false

kubectl api-resources --namespaced=true -o json | jq '.resources[].name' -r | while read kind;do
  kubectl get -n $namespace $kind -o json | jq '.items[].metadata.name' -r | while read item;do echo $kind/$item;done
done
