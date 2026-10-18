# Headscale Role

Manages the headscale coordination server and its ACL policy.

## Layout

- `tasks/main.yaml` — service install, config + policy deploy, pre-auth key mint
- `templates/config.yaml.j2` — headscale server config (rendered to /etc/headscale/config.yaml)
- `files/policy.json` — Tailscale ACL policy (rendered to /etc/headscale/policy.json)
- `handlers/main.yml` — restart handler, fired on policy change

## Policy

The ACL policy at `files/policy.json` is the source of truth. It is
deployed to the headscale host as `/etc/headscale/policy.json` and
headscale is restarted on every change. **Do not edit the policy live
on the server** — it will be overwritten on the next role run.

The current tag layout:

| Tag                    | Purpose                                                  |
| ---------------------- | -------------------------------------------------------- |
| `tag:headscale`        | the headscale host itself (weasel)                       |
| `tag:homelab-server`   | non-k8s homelab nodes (storage, homeassistant, ...)      |
| `tag:k8s-controlplane` | k3s control plane nodes                                  |
| `tag:k8s-agent`        | k3s agent nodes (panda)                                  |
| `tag:k8s-service`      | services running on k8s (advertised via subnet routes)   |
| `tag:ci`               | GitHub Action runners                                    |
| `tag:ssh-target`       | legacy single-tag for the existing SSH rule (deprecated) |

## Pre-auth keys

The role mints pre-auth keys under the **`homelab`** user, not the
personal `stoney` user. The `homelab` user is the machine identity
shared across the fleet, and is in `tagOwners` for every tag the
role's host_vars reference.

Each host's `tailscale_tag` host_var controls the tag baked into
the pre-auth key. Example (`host_vars/storage-0001.stoneydavis.internal`):

```yaml
tailscale_tag: tag:homelab-server
```

The minted key is stored in AWS Secrets Manager at
`weasel.stoneydavis.com/headscale/pre-auth-key`. Re-runs of the role
fetch the existing key from Secrets Manager instead of minting a new
one (idempotency).

## Migration from `stoney@`-owned keys

The legacy fleet was registered with pre-auth keys owned by
`stoney@`. To migrate a node to the new `homelab@`-owned keys:

1. **On weasel**, mint a single-use pre-auth key for the new tag. `--single`
   is the default, so don't pass it; `--tags` bakes the tag into the
   registration so the client doesn't need `--advertise-tags`:
   ```bash
   KEY=$(headscale preauthkeys create -u homelab \
     --tags tag:homelab-server --expiration 8760h -o json \
     | jq -r .key)
   ```
1. **On the node**, wipe the local tailscaled state and re-register.
   The client must forget its old machine key (otherwise headscale
   sees the stale key, returns a misleading "tags invalid" error
   even though the policy is fine). Then re-register using **only**
   the auth key — do not pass `--advertise-tags` because headscale
   already pinned the tag to the key:
   ```bash
   sudo systemctl stop tailscaled \
     && sudo rm -rf /var/lib/tailscale/* \
     && sudo systemctl start tailscaled \
     && sleep 3 \
     && sudo tailscale up --login-server=https://headscale.<your-domain> \
       --authkey="$KEY"
   ```
1. **After all nodes have migrated**, expire the old stoney keys:
   ```bash
   for ID in $(headscale preauthkeys list -u stoney -o json | jq -r '.[].id'); do
     headscale preauthkeys expire -u stoney -i "$ID"
   done
   ```
1. The old nodes continue to work (they're already registered);
   only new registrations are blocked by expired keys.

## CI runner key

The GitHub Action's Tailscale step uses a `ci-node@`-owned pre-auth
key with `--tags tag:ci` baked in. The key must be marked
`--reusable` (multiple ephemeral runners may consume it) and live as
the `TAILSCALE_AUTHKEY` GitHub repository secret.

To rotate:

1. **On weasel**, mint a fresh CI key:
   ```bash
   headscale preauthkeys create -u ci-node \
     --tags tag:ci --expiration 8760h --reusable -o json
   ```
1. **In GitHub repo settings → Secrets**, replace `TAILSCALE_AUTHKEY`
   with the new value.
1. The next CI run re-registers as `ci-node@` with `tag:ci`. The
   `tailscale/github-action` correctly omits `--advertise-tags` when
   the auth key has tags baked in; the tag is set at the headscale
   layer.

**Important**: never pass `--advertise-tags` on the `tailscale up`
invocation when the pre-auth key already has `--tags`. v0.28.0
returns a misleading "tags invalid" error in that case even when
the policy is correct.
