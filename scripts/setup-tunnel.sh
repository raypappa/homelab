#!/bin/bash

appName=$1
namespace=$2
endpoint=$3
network=faerun

if [[ -z "$appName" ]];then
    echo "Error: Missing first argument appName"
    exit 1
fi

if [[ -z "$namespace" ]];then
    echo "Error: Missing second argument namespace"
    exit 1
fi

if [[ -z "$endpoint" ]]; then
    echo "Error: Missing third argument endpoint"
    exit 1
fi

tunnelName="$network-$appName"
secretName="$appName-tunnel-credentials"

cloudflared tunnel create "$tunnelName"

cloudflared tunnel token "$tunnelName" | base64 -d | jq '.["AccountTag"] = .a | .["TunnelSecret"] = .s | .["TunnelID"] = .t | del(.a, .s, .t)' > credentials.json

kubectl create secret generic "$secretName" --from-file=credentials.json=./credentials.json -n "$namespace"

rm -f credentials.json

cloudflared tunnel route dns "$tunnelName" "$endpoint"
