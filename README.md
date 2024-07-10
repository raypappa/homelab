# Homelab

This is the CI/CD and infrastructure for my home network.

The idea behind this is to manage all(or as many as I can accomplish) using infrastructure as code with no hand holding.

I accomplish this with [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/home.html), [Ansible](https://www.ansible.com/), [Kubernetes](https://kubernetes.io/), [ArgoCD](https://argo-cd.readthedocs.io/en/stable/), [Taskfile](https://taskfile.dev/), [Dependabot](https://docs.github.com/en/code-security/dependabot/working-with-dependabot), [Renovate](https://docs.renovatebot.com/), [Github Actions](https://docs.github.com/en/actions), [Cloudflare](https://www.cloudflare.com/).

______________________________________________________________________

## Kubernetes

Ansible configures the hosts and bootstraps Kubernetes and ArgoCD. After that any additional work should be managed by ArgoCD.

### ArgoCD

#### App of Apps

If you're deploying an app of apps or any Application which is self-referential it must be within the default AppProject.

In order to resolve this issue we would need to reconfigure ArgoCD to support [applications in any namespace](https://argo-cd.readthedocs.io/en/stable/operator-manual/app-any-namespace/)

When deleting the App of Apps that is self referential you'll need to remove the finalizer once all other resources are removed.

#### Deployment Strategies

Many strategies were tried and some worked okay others didn't work at all.

Presently I'm using a straight `kubectl apply -f` by hand, my plan is to re-orchestrate things to be in AppSet's with ArgoCD, then I should be able to deploy 1 app to bootstrap the full cluster without lifting a hand.

##### Ansible using kubernetes.core.k8s and an inline definition

This has the benefit of having the apps define in one place but doesn't allow for a very DRY or touch once approach.

No need for files in the roots like argocd/metallb/metallb-app.yaml just the manifests.

Variation can use src or templated files and pass them in. This will help with an array of files.

This does support multiple sources as this is just moving the app declaration to another yaml file really.

Possible issue with using real sources is where does the file exist. I'd rather the deploy server not have the infra repo on it.

##### Ansible using argocd

Call argocd app create and pass in all of the arguments.

This is nice because like the above no need for extra files to define the apps themselves.

There is a kind of nasty aspect of this which doesn't support multiple sources.

Variation is using github actions instead of ansible, which is worse as i can't leverage yaml and iterative code in ansible.

##### kubectl apply github actions

This is by far the simplest solution so far and would be just adding a new entry in the workflow to add a new app.

`kubectl apply -n argocd -f argocd/metallb/metallb-app.yaml`

##### kubectl

This is by far the simplest solution and would be just running once per new app.

`kubectl apply -n argocd -f argocd/metallb/metallb-app.yaml`

### Application Notes

I will store notes I find helpful in making sure I don't break things.

#### Rook/Ceph

Deploy the operator first then the cluster

If you need to check on the status from cli use the following command

```
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- bash
```

#### Flood/rTorrent

If you need to reconfigure flood to talk to rTorrent the socket path is `/config/.local/share/rtorrent/rtorrent.sock`

#### Whisparr

After creating the application, you will need to populate the secret `whisparr_token` for use by other applications.

```shell
api_key=$(kubectl -n homelab exec -it deploy/whisparr-svc -- cat /config/config.xml | grep -oP '<ApiKey>\K[^<]+' | tr -d '\n')
kubectl -n homelab create secret generic --from-literal="api_key=${api_key}" whisparr-secret
```

It's a similar command for most of the \*arr services

______________________________________________________________________

## External Accessibility

Making use of [Cloudflare Tunnel](https://www.cloudflare.com/products/tunnel/) to expose endpoints. Each application which should be exposed has it's own tunnel and secret in most cases. They are grouped by the ArgoCD application, so the combined monitoring stack exposes both grafana and prometheus.

In order to ensure tunnels are managed with the config specified and not in the dashboard it's important to not create any items in the Cloudflare dashboard.

1. Determine application name
1. Determine namespace
1. Determine tunnel name
1. Create tunnel
1. Get tunnel secret and make credentials file
1. Create secret in kubernetes
1. Create DNS entry in Cloudflare
1. Create Application in Cloudflare so the endpoint is protected.

All steps except creation of the Application in Cloudflare are accomplished with the [create-secret](./scripts/setup-tunnel.sh) script.

## Github Actions

In order to have a functioning pipeline and make it easier for others I have some variables and secrets defined.

### Variables

| NAME                    | VALUE              |
| ----------------------- | ------------------ |
| ANSIBLE_STDOUT_CALLBACK | gha                |
| AWS_ASSUME_ROLE_ARN     | <cdk creates this> |
| AWS_DEFAULT_REGION      | us-west-2          |
| AWS_REGION              | us-west-2          |
| BASTION_HOST            | <REDACTED>         |
| BASTION_PORT            | <REDACTED>         |
| NODE_VERSION            | 20                 |
| PYTHON_VERSION          | 3.10.13            |
| RUNS_ON                 | ubuntu-latest      |
| TASK_VERSION            | 3.31.0             |

______________________________________________________________________

## :handshake: Thanks

Thanks to all the people who donate their time to the [Kubernetes @Home](https://discord.gg/k8s-at-home) Discord community. A lot of inspiration for my cluster comes from the people that have shared their clusters using the [k8s-at-home](https://github.com/topics/k8s-at-home) GitHub topic. Be sure to check out the [Kubernetes @Home search](https://nanne.dev/k8s-at-home-search/) for ideas on how to deploy applications or get ideas on what you can deploy. Also a fantastic resource was [bjw-s](https://github.com/bjw-s) own homelab [repo](https://github.com/bjw-s/home-ops/tree/main) and [helm charts](https://github.com/bjw-s/helm-charts) of which without the community would be worse for.

______________________________________________________________________
