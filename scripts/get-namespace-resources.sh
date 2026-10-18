#!/bin/bash

namespace=$1
if [[ -z $namespace ]];then
    echo missing namespace;
    exit 1
fi

kubectl api-resources --namespaced=true -o json 2>/dev/null | jq '.resources[].name' -r | while read kind;do
  kubectl get -n $namespace $kind -o json 2>/dev/null | jq '.items[].metadata.name' -r | while read item;do echo $kind/$item;done
done
