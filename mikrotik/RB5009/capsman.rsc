# =============================================================================
# RB5009 — CAPsMAN controller configuration
# =============================================================================
#
# Manages the two cAP ac access points (AP1 = 10.49.48.4, AP2 = 10.49.48.7).
# AP2 daisy-chains off AP1 — both are PoE-fed from the RB5009 directly.
#
# SSIDs:
#   - "Pretty Penguin"  (5GHz ac, main)
#   - "Sassy Penguin"   (2GHz, fallback / IoT)
#
# This config was taken from the live device. No changes — kept here for
# version control and to back out the wifi configuration if needed.
# =============================================================================

/caps-man channel
add band=2ghz-onlyg name=2ghz
add band=5ghz-onlyac name=5ghz-ac

/caps-man security
add authentication-types=wpa2-psk name=security1

/caps-man configuration
add channel=5ghz-ac country="united states" datapath.bridge=bridge mode=ap \
    name=cfg1 security=security1 ssid="Pretty Penguin"
add channel=2ghz datapath.bridge=bridge distance=indoors name=cfg2 \
    security=security1 ssid="Sassy Penguin"

/caps-man manager set enabled=yes

/caps-man provisioning
add action=create-dynamic-enabled hw-supported-modes=ac master-configuration=cfg1
add action=create-dynamic-enabled hw-supported-modes=g master-configuration=cfg2

# =============================================================================
# VERIFY:
#   /caps-man manager print
#   /caps-man provisioning print
#   /caps-man registration-table print
#   /caps-man interface print
# =============================================================================
