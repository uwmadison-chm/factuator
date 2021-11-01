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
WIKI_FOLDER_ID = "1AgX9QXsZsd3ew44W1LXHUPSY-uQ977sk"
WIKI_DRIVE_ID = "0AG2B9Bd2aOIxUk9PVA"

class GDocExporter:
    def __init__(self, mother, mappings_path):
        """
        GDocExporter needs a path to mappings. See `gdocmappings.py`.

        Google services auth is OAuth, so it will try to start $BROWSER
        if there is no cached token.

        We use "mother" here to represent the source wiki
        (because that's what it's called at CHM/BI)
        """

        self.mappings = GDocMappings(MAPPINGS_FILE)
        self.initialize_google_services()
        self.mother = mother


    def run(self):
        """
        Main function that does the conversion.
        """
        category = self.mother.categories['Study']

        # EXPERIMENTAL: Just pick one
        page = next(category)

        self.convert(page)

        self.mappings.save()


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


    def find_folder(name):
        """
        Find folder across all drives by name.

        NOTE: Not super reliable if folder names are not unique.

        In the future it might be good to take an optional folder id,
        and query the document's folder chain to see if it is inside that
        folder id somewhere.
        """

        folderId = self.drive.files().list(q = f"mimeType = 'application/vnd.google-apps.folder' and name = '{name}'",
                driveId=WIKI_DRIVE_ID, corpora="drive",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                pageSize=10, fields="nextPageToken, files(id, name)").execute()
        folderIdResult = folderId.get('files', [])
        actual_id = folderIdResult[0].get('id')
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


    def convert(self, page):
        if page.name in self.mappings.title_to_id:
            doc_id = self.mappings.title_to_id[page.name]
            document = self.docs.documents().get(documentId=doc_id).execute()
            logging.info(f"Converting {page.name} into existing doc {doc_id}")
        else:
            # Create doc fresh
            doc_content = { 
                'title': page.name,
            }
            document = self.docs.documents().create(body=body).execute()
            doc_id = document['documentId']
            self.mappings.add(page.name, doc_id)
            self.reparent(doc_id, WIKI_FOLDER_ID)
            logging.info(f"Converting {page.name} into new doc {doc_id}")

        c = GDocConverter(self.mother, self.docs, self.mappings)
        c.convert(page, doc_id)


def run(mother):
    x = GDocExporter(mother, MAPPINGS_FILE)
    x.run()
