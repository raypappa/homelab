# Software Raid

## Raid Status

`cat /proc/mdstat`

## Add New Disk

1. Locate new drive
   ```bash
   grep sd /var/log/messages*
   dev=/dev/sd
   ```
1. Create label
   ```bash
   parted -s -a optimal $dev -- mklabel gpt
   ```
1. Create partition
   ```bash
   parted -s -a optimal $dev -- unit mib mkpart primary 1 -1
   ```
1. Add drive to raid
   ```bash
   mdadm --add /dev/md0 $dev
   mdadm --grow /dev/md0 -b none
   mdadm --grow --raid-devices=20 --backup-file=/root/grow_md0.bak /dev/md0
   ```
1. After rebuild is complete
   ```bash
   mdadm --grow --bitmap=internal /dev/md0
   ```
1. Resize disk
   ```bash
   resize2fs /dev/md0
   ```

## Update software raid configuration file

`mdadm --detail --scan > /etc/mdadm.conf`
