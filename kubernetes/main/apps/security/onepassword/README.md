# onepasswordSDK

<!-- spell-checker: disable -->

The connect server with external-secrets is deprecated. As such this is moving towards the sdk method using service tokens.

## Deployment

```shell
op.exe read "op://Homelab/2hjc2nmfmurqbjsuzk6i4whelm/credential" > .token
kubectl create -n external-secrets secret generic onepassword-connect-token-homelab --from-file=token=.token

```

TODO: Securely store this in the repository to enable bootstrapping the cluster.
