import mwclient
import getpass
import os
import os.path
import stat
import pickle
import mwparserfromhell

fname = 'auth.pickle'
if os.path.exists(fname):
    auth = pickle.load( open( fname, "rb" ) )
    user = auth[0]
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


ua = 'factuator/0.1 run by User:' + user
mother = mwclient.Site(('https', 'wiki.keck.waisman.wisc.edu'), path='/wikis/mother/', httpauth=auth)

category = mother.categories['Study']
for page in category:
    text = page.text()
    p =  mwparserfromhell.parse(text)
    for template in p.filter_templates():
        print("Page %s has template %s with these params:" % (page.name, template.name.rstrip()))
        print(template.params)
        try:
            jarvis_id = template.get("JARVIS ID").value.rstrip()
            print(jarvis_id)
        except ValueError:
            # We just skip JARVIS integration if there's no id
            pass
