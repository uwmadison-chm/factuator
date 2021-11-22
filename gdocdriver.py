import mwparserfromhell
import logging
import requests
import os

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from gdocmappings import GDocMappings 
from gdocconverter import GDocConverter

SCOPES = ['https://www.googleapis.com/auth/documents',
          'https://www.googleapis.com/auth/drive',
          'https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/drive.metadata']
MAPPINGS_FILE = "mappings.google.json"

class GDocDriver:
    def __init__(self, mappings_path, file_prefix, http_prefix, drive_id, unsorted_folder_id):
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
        self.file_prefix = file_prefix
        self.http_prefix = http_prefix
        self.drive_id = drive_id
        self.unsorted_folder_id = unsorted_folder_id


    def run_export(self, wiki, wiki_prefix):
        """
        Function that does the conversion from mediawiki to gdoc,
        walking the mediawiki pages
        """

        self.wiki = wiki
        self.wiki_prefix = wiki_prefix
        self.load_folders()

        # NOTE: For now just pick a single study page
        # self.convert_one("ADNI Study")
        # self.convert_category('Study')
        self.convert_all_new()

        self.mappings.save()

        # TODO: Now we need to walk the pages and 


    def load_folders(self):
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

    def convert_all_new(self):
        skips = [
            "ADNI Study",
            "Autism Preprocessing NEW",
            "Autism Preprocessing Steps",
            "Automated login to COINS",
            "Baby Brain and Behavior Project Recruitment",
            "Baby Brain Behavior Project Recruitment and Contact Information",
            "Brain Imaging Core Information Policy and Procedure",
        ]
        for page in self.wiki.pages:
            if not page.name in skips:
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


    def convert(self, page, only_if_new=False, debug=False):
        if page.name in self.mappings.title_to_id:
            if only_if_new:
                return
            doc_id = self.mappings.title_to_id[page.name]
            document = self.docs.documents().get(documentId=doc_id).execute()
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
                self.wiki,
                self.wiki_prefix,
                self.docs,
                self.mappings,
                self.file_prefix,
                self.http_prefix)
        c.convert(page, doc_id, debug=debug)


def export_mediawiki(wiki, wiki_prefix, file_prefix, http_prefix, drive_id, unsorted_folder_id):
    x = GDocDriver(MAPPINGS_FILE, file_prefix, http_prefix, drive_id, unsorted_folder_id)
    x.run_export(wiki, wiki_prefix)

