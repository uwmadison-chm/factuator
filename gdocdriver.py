import mwparserfromhell
import logging
import requests
import os
import time

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from gdocmappings import GDocMappings 
from gdocconverter import GDocConverter
from gdoclinks import GDocLinks

SCOPES = ['https://www.googleapis.com/auth/documents',
          'https://www.googleapis.com/auth/drive',
          'https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/drive.metadata']
MAPPINGS_FILE = "mappings.google.json"

# Limit to how many parents to request via Drive API
MAX_PARENTS = 500

class GDocDriver:
    """
    Class that controls a connection to the Drive and Docs APIs
    and knows how to run conversions from MediaWiki into Docs files.

    Also beginning to add "walking" functionality to run arbitrary
    updates on docs in a given folder
    """

    def __init__(self, mappings_path, drive_id):
        """
        GDocDriver needs a path to mappings. See `gdocmappings.py`.

        Google services auth is OAuth, so it will try to start $BROWSER
        if there is no cached token.

        `file_prefix` is used by the converter to store image and other
        files in a public-internet-accessible location so the Google Docs
        API can read them from `http_prefix`
        """

        self.mappings = GDocMappings(MAPPINGS_FILE)
        self.initialize_google_services()
        self.drive_id = drive_id
        self.folders = {}


    def run_export(self, wiki, wiki_prefix, force, file_prefix, http_prefix, unsorted_folder_id):
        """
        Function that does the conversion from mediawiki to gdoc,
        walking the mediawiki pages
        """

        self.wiki = wiki
        self.wiki_prefix = wiki_prefix
        self.file_prefix = file_prefix
        self.http_prefix = http_prefix
        self.unsorted_folder_id = unsorted_folder_id
        self.load_common_folders()

        # NOTE: For now just pick a single study page
        # self.convert_one("ADNI Study")
        # self.convert_category('Study')
        if force:
            self.convert_all()
        else:
            self.convert_all_new()

        self.mappings.save()


    def run_check_links(self, folder_id):
        docs = self.recursive_docs_in_folder(folder_id)

        for doc_id in docs.keys():
            linker = GDocLinks(self)
            linker.check_links(doc_id)


    def recursive_docs_in_folder(self, folder_id):
        relevant_folders = [folder_id]
        for folder in self.folders_in_folder(folder_id):
            relevant_folders.append(folder)
        return self.get_relevant_files(relevant_folders)


    def get_relevant_files(self, relevant_folders):
        """
        Get files under the relevant_folders and all their subfolders.
        """
        relevant_files = {}
        chunked_relevant_folders = \
            [relevant_folders[i:i + MAX_PARENTS] \
                for i in range(0, len(relevant_folders), MAX_PARENTS)]
        for folder_list in chunked_relevant_folders:
            query_term = ' in parents or '.join('"{0}"'.format(f) for f in folder_list) + ' in parents'
            relevant_files.update(self.get_all_files_in_folders(query_term))
        return relevant_files


    def get_all_files_in_folders(self, parent_folders):
        """
        Return a dictionary of file IDs mapped to file names for the specified parent folders.
        """
        files_under_folder = {}
        page_token = None
        max_allowed_page_size = 1000
        just_files = f"mimeType != 'application/vnd.google-apps.folder' and trashed = false and ({parent_folders})"
        while True:
            results = self.drive.files().list(
                pageSize=max_allowed_page_size,
                fields="nextPageToken, files(id, name, mimeType, parents)",
                includeItemsFromAllDrives=True, supportsAllDrives=True,
                corpora='drive',
                driveId=self.drive_id,
                pageToken=page_token,
                q=just_files).execute()
            files = results.get('files', [])
            page_token = results.get('nextPageToken', None)
            for file in files:
                files_under_folder[file['id']] = file['name']
            if page_token is None:
                break
        return files_under_folder


    def all_folders_in_drive(self):
        """
        Return a dictionary of all the folder IDs in a drive mapped to their 
        parent folder IDs (or to the drive itself if a top-level folder).
        This flattens the entire folder structure.

        Note that this caches the result, because for our purposes the
        folders will not be changing often enough to matter.
        """
        if len(self.folders) > 0:
            return self.folders

        page_token = None
        max_allowed_page_size = 1000
        just_folders = "trashed = false and mimeType = 'application/vnd.google-apps.folder'"
        while True:
            results = self.drive.files().list(
                pageSize=max_allowed_page_size,
                fields="nextPageToken, files(id, name, mimeType, parents)",
                includeItemsFromAllDrives=True, supportsAllDrives=True,
                corpora='drive',
                driveId=self.drive_id,
                pageToken=page_token,
                q=just_folders).execute()
            result_folders = results.get('files', [])
            page_token = results.get('nextPageToken', None)
            for folder in result_folders:
                self.folders[folder['id']] = folder['parents'][0]
            if page_token is None:
                break

        return self.folders


    def folders_in_folder(self, folder_to_search):
        """
        Yield subfolders of the folder-to-search, and then subsubfolders etc.
        Must be called by an iterator.
        """
        # Get all subfolders
        temp_list = [k for k, v in self.all_folders_in_drive().items() if v == folder_to_search]
        for sub_folder in temp_list:
            yield sub_folder
            # Recurse
            yield from self.folders_in_folder(sub_folder)


    def load_common_folders(self):
        self.category_to_folder = {
            'Study': 'Studies',
            'Self Report Measure': 'Self Report Library',
            'Behavioral Task': 'Behavioral Tasks',
            'Behavioral Task Variant': 'Behavioral Tasks',
            'Imaging Task': 'Imaging Tasks',
            'Demo Task': 'Demo Tasks',
            'Filmable Task': 'Filmable Tasks',
            'BIOPAC': 'BIOPAC',
            'Policies and Procedures': 'Policies and Procedures',
            'CHM Community Meeting': 'Community Meetings',
            'CHM Human Resources': 'HR',
            'CHM Research Support Core': 'RSC',
            'CHM Computing Guides': 'Computing',
            'Computing': 'Computing',
            'Kennedy': 'Kennedy',
            'Keystone': 'Keystone',
            'Brogden': 'Brogden',
        }

        self.namespace_to_folder = {
            'User': 'People',
        }

        self.folders = {}
        for category, name in self.category_to_folder.items():
            self.folders[category] = self.find_folder(name)

        for namespace, name in self.namespace_to_folder.items():
            self.folders[namespace] = self.find_folder(name)


    def convert_one(self, title):
        page = self.wiki.pages[title]
        self.convert(page, debug=True)

    def convert_category(self, category_name):
        category = self.wiki.categories[category_name]
        for page in category:
            self.convert(page)

    def convert_all(self):
        for page in self.wiki.pages:
            self.convert(page, only_if_new=False)

    def convert_all_new(self):
        for page in self.wiki.pages:
            self.convert(page, only_if_new=True)


    def initialize_google_services(self):
        """
        Boilerplate to cache a token and connect to the docs and drive services.
        """

        creds = None
        token_file = 'auth.google_token.json'
        cred_file = 'auth.google_credentials.json'

        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_file, 'w') as token:
                token.write(creds.to_json())

        self.docs = build('docs', 'v1', credentials=creds)
        self.drive = build('drive', 'v3', credentials=creds)


    def find_folder(self, name):
        """
        Find folder across all drives by name.

        NOTE: Not super reliable if folder names are not unique.

        In the future it might be good to take an optional folder id,
        and query the document's folder chain to see if it is inside that
        folder id somewhere.
        """

        result = self.drive.files().list(q = f"mimeType = 'application/vnd.google-apps.folder' and name = '{name}'",
                driveId=self.drive_id, corpora="drive",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                pageSize=10, fields="nextPageToken, files(id, name)").execute()
        folder_id_result = result.get('files', [])
        # If this fails, we couldn't find a folder named `name`
        actual_id = folder_id_result[0].get('id')
        logging.info(f"Found folder named {name} with {actual_id}")
        return actual_id


    def reparent(self, doc_id, folder_id):
        """
        Reparent document to a specific folder using the drive API.
        """

        f = self.drive.files().get(fileId=doc_id, fields='parents').execute()
        previous_parents = ",".join(f.get('parents'))
        if not folder_id in previous_parents:
            result = self.drive.files().update(
                fileId=doc_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields='id, parents',
                supportsAllDrives=True,
            ).execute()



    def get_document(self, doc_id):
        return self.docs.documents().get(documentId=doc_id).execute()


    def batch_update(self, doc_id, requests, debug=False):
        """
        Batch update the document with the given requests.

        If debug is passed, do each request one at a time, slow-ish.
        """
        
        if debug:
            for r in requests:
                try:
                    self.docs.documents().batchUpdate(
                        documentId=doc_id, body={'requests': [r]}).execute()
                except BaseException as e:
                    print(f"Unexpected {e}, {type(e)} with request {r}")
                    raise
                time.sleep(0.1)

        else:
            return self.docs.documents().batchUpdate(
                documentId=doc_id, body={'requests': requests}).execute()


    def traverse(self, f, d, start_index, end_index):
        """
        Recursive method to do a common thing we'll be needing a lot:
        store current start_index and end_index, while traversing
        the document tree and calling a function `f` on each dict.
        """
        if 'startIndex' in d:
            start_index = d['startIndex']

        if 'endIndex' in d:
            end_index = d['endIndex']

        f(d, start_index, end_index)

        for key, value in d.items():
            if isinstance(value, dict):
                self.traverse(f, value, start_index, end_index)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self.traverse(f, item, start_index, end_index)


    def convert(self, page, only_if_new=False, debug=False):
        if page.name in self.mappings.title_to_id:
            if only_if_new:
                return
            doc_id = self.mappings.title_to_id[page.name]
            document = self.get_document(doc_id)
            logging.info(f"Converting {page.name} into existing doc {doc_id}")
        else:
            full_title = page.name
            namespace = None
            if ":" in full_title:
                namespace, title = full_title.split(":", 1)
            else:
                title = full_title

            # Create doc fresh
            doc_content = { 
                'title': title,
            }
            document = self.docs.documents().create(body=doc_content).execute()
            doc_id = document['documentId']

            self.mappings.add(full_title, doc_id)

            # Now we move the file into a folder, based on category
            # Default to the unsorted folder
            folder_id = self.unsorted_folder_id

            # But if there is a namespace or mapping to a specific folder, use it
            if namespace:
                for n in self.namespace_to_folder.keys():
                    if n == namespace:
                        folder_id = self.folders[n]
                        break
            else:
                # Note that we just pick the first possible mapping, so order in category_to_folder is important
                page_categories = [c.name.replace('Category:', '') for c in page.categories()]
                for c in self.category_to_folder.keys():
                    if c in page_categories:
                        folder_id = self.folders[c]
                        break
            self.reparent(doc_id, folder_id)
            logging.info(f"Converting {page.name} into new doc {doc_id} in folder {folder_id}")

        c = GDocConverter(
                self,
                self.wiki,
                self.wiki_prefix,
                self.docs,
                self.mappings,
                self.file_prefix,
                self.http_prefix)
        c.convert(page, doc_id, debug=debug)


def export_mediawiki(wiki, wiki_prefix, force, file_prefix, http_prefix, drive_id, unsorted_folder_id):
    x = GDocDriver(MAPPINGS_FILE, drive_id)
    x.run_export(wiki, wiki_prefix, force, file_prefix, http_prefix, unsorted_folder_id)


def link(drive_id, folder_id):
    x = GDocDriver(MAPPINGS_FILE, drive_id)
    x.mappings.ids_that_link_to_id = {}
    x.run_check_links(folder_id)
    x.mappings.save()
