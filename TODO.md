# TODO

## Deploy

1. [gitea](https://github.com/elcattivo66/home-ops/blob/main/kubernetes/main/apps/default/gitea/app/helmrelease.yaml)
1. kubernetes-dashboard
1. [it-tools](https://github.com/CorentinTh/it-tools?tab=readme-ov-file) [it-tools helm release](https://github.com/ahinko/home-ops/blob/main/kubernetes/main/apps/dev/it-tools/app/helm-release.yaml)
1. [coder](https://coder.com/docs/install/kubernetes)
1. joplin
1. headscale
1. MySQL Operator
1. samba
1. ldap
1. [nginx-ingress](https://github.com/bjw-s-labs/home-ops/blob/main/kubernetes/main/apps/network/ingress-nginx/internal/helmrelease.yaml)
1. [external-dns](https://github.com/bjw-s-labs/home-ops/blob/main/kubernetes/main/apps/network/external-dns/unifi/helmrelease.yaml)
1. once I have mikrotik using [external-dns-provider-mikrotik](https://github.com/mirceanton/external-dns-provider-mikrotik)
1. [spotizerr](https://github.com/Xoconoch/spotizerr)
1. [metube](https://github.com/alexta69/metube) or [tubearchivist](https://github.com/tubearchivist/tubearchivist)
1. [Collabora](https://collaboraonline.github.io/online/)

## Migrate to AppSet

1. leantime
1. pterodactyl
1. plex
1. radarr
1. readarr
1. whisparr
1. unpackerr
1. recyclarr
1. sonarr
1. rtorrent

## Fix

1. Dashboard and ArgoCD Dashboard are deploying cert-manager, get them to stop.
1. Immich - complaints about db not having pgvecto.rs set up
1. Joplin - permission denied for schema public
1. PGAdmin - set up users
1. Joplin - update to use dragonfly
1. Immich - update to use dragonfly
1. ollama nginx ingress

## Physical

1. Get rpi set up with nut and a ups to plug into the bigger ups for the office
1. Get rpi set up with nut and a ups to plug into the bigger ups for the bedroom
1. Get rpi set up with nut and a ups to plug into the bigger ups for the network gear

## Other

1. setup router to send syslog to loki
1. setup home assistant to send syslog to loki
1. setup modem to send syslog to loki
