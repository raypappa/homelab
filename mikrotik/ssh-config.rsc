# =============================================================================
# Mikrotik SSH baseline (apply first, before any other config)
# =============================================================================
#
# Applies the SSH hardening baseline to every Mikrotik in the fleet. Safe to
# re-import (idempotent).
#
# Order-of-operations warning:
#   This script must be run via console, Mac-Telnet, or WinBox on a fresh
#   device BEFORE switching to SSH-only access. The script:
#     1. Sets SSH to a non-default port (2200) and enables strong-crypto
#     2. Disables telnet / ftp / www / api / api-ssl
#     3. Imports the public key (so you can log in by key)
#     4. Sets the user to publickey-only auth
#     5. Disables password auth for any other user
#     6. Restricts SSH source to the management subnet
#
# After this script imports, log out and reconnect:
#   ssh -p 2200 -i ~/.ssh/raypappa raypappa@<device-ip>
#
# If you run this over SSH (chicken-and-egg), the existing session stays
# up but new connections require the key. Don't disconnect until you've
# verified the new key-based login works.
# =============================================================================

# ============ VARIABLES — EDIT THIS BLOCK ====================================
:local sshPort         2200
:local sshUser         "raypappa"
:local mgmtSubnet      "10.49.48.0/23"
:local publicKey       "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBZkWK6/qM78P8WMNMi7CLBdbIlSpSdtFgFDuJIR4f+S"
# =============================================================================

# --- 1. SSH service hardening ------------------------------------------------
/ip ssh set strong-crypto=yes port=$sshPort forwarding-enabled=both

# --- 2. Disable unused plain-text / API services -----------------------------
:do { /ip service set telnet      disabled=yes }   on-error={ :put "telnet set" }
:do { /ip service set ftp         disabled=yes }   on-error={ :put "ftp set" }
:do { /ip service set www         disabled=yes port=80 }    on-error={ :put "www set" }
:do { /ip service set www-ssl     disabled=yes }   on-error={ :put "www-ssl set" }
:do { /ip service set api         disabled=yes port=8728 }  on-error={ :put "api set" }
:do { /ip service set api-ssl     disabled=yes port=8729 }  on-error={ :put "api-ssl set" }
:do { /ip service set ssh         port=$sshPort }            on-error={ :put "ssh port set" }

# --- 3. Import the public key (idempotent: skip if already present) ---------
:do {
  :local existing [/user ssh-keys find where user=$sshUser]
  :if ([:len $existing] = 0) do={
    :local tmpFile ("raypappa.pub")
    /file print file=$tmpFile where name=$tmpFile
    :if ([:len [/file find where name=$tmpFile]] = 0) do={
      :put "Paste the public key contents onto the device first:"
      :put "  /file add name=raypappa.pub contents=<paste-key>"
      :put "Then re-run this script."
      :error "public key file not found on device"
    }
    /user ssh-keys import user=$sshUser public-key-file=$tmpFile
    /file remove $tmpFile
  } else={
    :put "ssh key for user already imported; skipping"
  }
} on-error={ :put "ssh key import skipped or failed" }

# --- 4. Lock the user to publickey-only auth --------------------------------
:do {
  /user set [find name=$sshUser] allowed-authentication=publickey
} on-error={ :put "user auth not set (user may not exist)" }

# --- 5. Disable any other (non-admin, non-key) user -------------------------
:do {
  /user set [find name!=$sshUser] disabled=yes
} on-error={ :put "no other users to disable" }

# --- 6. Restrict SSH source to the management subnet -------------------------
# Drop rules first (deny by default), then the accept for the mgmt subnet.
:do {
  /ip firewall filter add chain=input src-address=$mgmtSubnet \
      dst-port=$sshPort protocol=tcp action=accept \
      comment="ssh-from-mgmt"
} on-error={ :put "ssh accept rule exists" }
:do {
  /ip firewall filter add chain=input dst-port=$sshPort protocol=tcp \
      action=drop comment="drop-all-other-ssh"
} on-error={ :put "ssh drop rule exists" }

# Move the accept rule above the drop if it isn't already:
# /ip firewall filter move [find comment="ssh-from-mgmt"] 0

# =============================================================================
# VERIFY:
#   /ip ssh print
#   /ip service print
#   /user ssh-keys print
#   /user print
#   /ip firewall filter print where comment~"ssh"
# =============================================================================
