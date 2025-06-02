## Add a samba user and set a password to it
```bash
# smb.conf is under /etc/samba/
# $USER is the current user of the system
sudo smbpasswd -a $USER
```

## Exp: Add a samba user pi and set a password to it
```bash
sudo smbpasswd -a pi
# New SMB password:
```

## Check the samba version
```bash
dpkg -l samba
```
