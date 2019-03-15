import pickle
import getpass
import os
import os.path
import stat


def get_auth():
    fname = 'auth.pickle'
    if os.path.exists(fname):
        auth = pickle.load( open( fname, "rb" ) )
    else:
        # Define file params
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL  # Refer to "man 2 open".
        mode = stat.S_IRUSR | stat.S_IWUSR  # This is 0o600 in octal
        
        # For security, remove file with potentially elevated mode
        try:
            os.remove(fname)
        except OSError:
            pass
        
        # Open file descriptor
        umask_original = os.umask(0)
        try:
            fdesc = os.open(fname, flags, mode)
        finally:
            os.umask(umask_original)
        
        user = input("Username: ")
        password = getpass.getpass()
        auth=(user, password)

        # Open file handle and write to file
        with os.fdopen(fdesc, 'wb') as fout:
            pickle.dump(auth, fout)

    return auth

