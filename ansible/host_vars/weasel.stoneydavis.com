---
# yaml-language-server: $schema=https://raw.githubusercontent.com/ansible/ansible-lint/refs/heads/main/src/ansiblelint/schemas/vars.json
# vim: ft=yaml
certbot_admin_email: cdavis@stoneydavis.com
certbot_create_if_missing: true
certbot_create_standalone_stop_services:
  - headscale
certbot_certs:
  - name: &domain weasel.stoneydavis.com
    domains:
      - *domain
coturn_static_auth_secret: "{{ lookup('amazon.aws.aws_secret', 'weasel.stoneydavis.com/coturn/auth',
  region=lookup('env', 'AWS_REGION')) }}"
coturn_realm: *domain
coturn_install: "src"
coturn_listening_port: 3479
coturn_tls_cert: &cert_path /etc/letsencrypt/live/weasel.stoneydavis.com/fullchain.pem
coturn_tls_key: &key_path /etc/letsencrypt/live/weasel.stoneydavis.com/privkey.pem
coturn_alt_listening_port: 0
coturn_tls_listening_port: 5349
coturn_alt_tls_listening_port: 0
coturn_install_src_version: "4.8.0"
coturn_tls: True
coturn_no_rfc5780: False
# renovate: datasource=github-releases depName=livekit/livekit
livekit_version: "1.9.11"
livekit_config:
  port: 7880
  bind_addresses:
    - ""
  rtc:
    tcp_port: 7881
    port_range_start: 50000
    port_range_end: 60000
    use_external_ip: true
    enable_loopback_candidate: false
  redis:
    address: localhost:6379
    username: ""
    password: ""
    db: 0
    use_tls: false
    sentinel_master_name: ""
    sentinel_username: ""
    sentinel_password: ""
    sentinel_addresses: []
    cluster_addresses: []
    max_redirects: null
  turn:
    relay_range_start: 60100
    relay_range_end: 60200
    enabled: true
    domain: *domain
    tls_port: 5350
    udp_port: 3480
    cert_file: *cert_path
    key_file: *key_path
  keys: "{{ lookup('amazon.aws.aws_secret', 'weasel.stoneydavis.com/livekit/keys',
    region=lookup('env', 'AWS_REGION')) | from_json }}"
livekit_jwt_homeservers: "matrix.rvn.moe"
