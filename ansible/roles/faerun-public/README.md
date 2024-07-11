# Faerun Public

This is an odd role. The role is executed on the host that is part of the faerun's local network dmz as it were, but the only task present is delegated to localhost.

Update the R53 record representing the home network with the public ip. Delegated to localhost as localhost has AWS credentials and it's not a guarantee the remote host would.
