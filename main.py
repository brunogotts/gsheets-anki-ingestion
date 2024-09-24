import argparse
import requests
import logging
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)

ENDPOINT='http://localhost:8765'

class Ingestion:
    def __init__(self, url):
        self.sheet_html=self.import_public_sheet(url)
        self.sheet_nested_list=self.html_to_nested_list(self.sheet_html)

    def import_public_sheet(self,url):
        return requests.get(url).text

    def html_to_nested_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        table = html.find('table')
        nested_list = []
        table = soup.find('table')  # Adjust the selector based on the actual HTML structure
        for row in table.find_all('tr'):
            columns = row.find_all('td')
            if len(columns) >= 2:
                word = columns[0].get_text(strip=True)
                meaning = columns[1].get_text(separator='<br>', strip=True) # Adding <br> when newline so anki understands it
                tag = columns[2].get_text(strip=True)
                nested_list.append([word, meaning, tag])
        return nested_list

class DataOperations:
    def __init__(self, nested_list, filter_start_row=None, filter_end_row=None, filter_tags=None):
        self.nested_list=nested_list
        self.format_note_to_anki_structure(self.nested_list)
        self.raw_notes=self.format_note_to_anki_structure(self.nested_list)
        self.filtered_notes=self.filter_notes(self.raw_notes,start_row=filter_start_row,end_row=filter_end_row,tags=filter_tags)
        logging.info(f'Number of notes: {len(self.filtered_notes)}')
        self.filtered_notes_without_now_number=[item['anki_note_dict'] for item in self.filtered_notes]

    def format_note_to_anki_structure(self, nested_list):
        # Use list comprehension to construct the list of dictionaries
        notes = [
            {
                "row_number": idx + 1,  # Add row number (1-based index)
                "anki_note_dict": {
                    "front": row[0],
                    "back": row[1],
                    "tags": [row[2]] if row[2] != "" else []
                }
            }
            for idx, row in enumerate(nested_list) if len(row) >= 2
        ]
        return notes

    def filter_notes(self, notes, start_row=None, end_row=None, tags=None):
        filtered_notes = [note for note in notes if note['anki_note_dict'].get('front') not in ('xxx', '') and note['anki_note_dict'].get('back') not in ('xxx', '')]

        filtered_notes = [
            note for note in filtered_notes
            if 'back' in note['anki_note_dict']
        ]

        if start_row is not None:
            filtered_notes = [
                note for note in filtered_notes
                if note['row_number'] >= start_row
            ]
        elif end_row is not None:
            filtered_notes = [
                note for note in filtered_notes
                if note['row_number'] <= end_row
            ]
        else:
            filtered_notes = filtered_notes

        if tags:
            filtered_notes = [
                note for note in filtered_notes
                if any(tag in note['anki_note_dict']['tags'] for tag in tags)
            ]
        else:
            filtered_notes = filtered_notes

        return filtered_notes

class AnkiOperations:
    def __init__(self, deck_name, notes, create_deck_flag, delete_deck_flag, add_notes_flag, delete_all_notes_from_dataset_flag):
        self.create_deck(deck_name)
        
        if delete_all_notes_from_dataset_flag:
            logging.info(f"Delete all notes from deck operation started")
            self.delete_all_notes_from_deck(deck_name)

        if delete_deck_flag:
            logging.info(f"Delete deck operation started")
            response = self.delete_deck(deck_name)
            logging.info(f"Delete a deck response: {response}")
        
        if create_deck_flag:
            logging.info(f"Create deck operation started")
            response = self.create_deck(deck_name)
            logging.info(f"Create a deck response: {response}")
        
        if add_notes_flag:
            logging.info(f"Add notes operation started")
            self.add_notes_to_deck(deck_name, notes)

    def delete_deck(self, deck_name, cards_too=True):
        payload = {
            "action": "deleteDecks",
            "version": 6,
            "params": {
                "decks": [deck_name],
                "cardsToo": cards_too # remove this?
            }
        }
        response = requests.post(ENDPOINT, json=payload)
        return response.json()

    def create_deck(self, deck_name):
        payload = {
            "action": "createDeck",
            "version": 6,
            "params": {
                "deck": deck_name
            }
        }
        response = requests.post(ENDPOINT, json=payload)
        
        return response.json()

    def add_note_to_deck(self, deck_name, note):
        payload = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": deck_name,
                    "modelName": "Basic",
                    "fields": {
                        "Front": note['front'],
                        "Back": note['back']
                    },
                    "options": {
                        "allow_duplicate": False
                    },
                    "tags": note.get('tags', [])
                }
            }
        }
        response = requests.post(ENDPOINT, json=payload)
        return response.json()

    def add_notes_to_deck(self, deck_name, notes):

        for note in notes:
            response = self.add_note_to_deck(deck_name, note)
            logging.info(f"Add note to deck response: {response}")

    def delete_notes(self, note_ids):
        payload = {
            "action": "deleteNotes",
            "version": 6,
            "params": {
                "notes": note_ids
            }
        }

        # Send the request to AnkiConnect
        response = requests.post("http://localhost:8765", json=payload)

        # Check the response
        if response.status_code == 200:
            result = response.json()
            if result.get("error") is None:
                print("Notes deleted successfully.")
            else:
                print(f"Error: {result['error']}")
        else:
            print(f"Failed to connect to AnkiConnect. Status code: {response.status_code}")

    def delete_all_notes_from_deck(self, deck_name):
        # Get all note IDs from the specified deck
        note_ids = self.get_note_ids_from_deck(deck_name)
        if note_ids:
            # Delete the notes
            self.delete_notes(note_ids)
        else:
            print(f"No notes found in deck: {deck_name}")

    def get_note_ids_from_deck(self, deck_name):
        payload = {
            "action": "findNotes",
            "version": 6,
            "params": {
                "query": f"deck:{deck_name}"
            }
        }

        # Send the request to AnkiConnect
        response = requests.post("http://localhost:8765", json=payload)

        # Check the response
        if response.status_code == 200:
            result = response.json()
            if result.get("error") is None:
                return result.get("result", [])
            else:
                print(f"Error: {result['error']}")
                return []
        else:
            print(f"Failed to connect to AnkiConnect. Status code: {response.status_code}")
            return []

def main():
    parser = argparse.ArgumentParser(description='Process Google Sheets file & Anki Operations')
    # # Arguments
    # General purposes
    parser.add_argument('--extract_and_ingest_notes', action='store_true', default=False, help='Flag to extract and add notes')
    # Ingestion
    parser.add_argument('--url', type=str, help='Public URL of the Google Sheets document in html format')
    # Data Operations
    parser.add_argument('--filter_start_row', type=int, default=None, help='Start row for filtering (optional)')
    parser.add_argument('--filter_end_row', type=int, default=None, help='End row for filtering (optional)')
    parser.add_argument('--filter_tags', type=str, nargs='*', default=None, help='Tags for filtering (optional)')
    # Anki Operations
    parser.add_argument('--deck-name', type=str, default='Default Deck', help='Deck name')
    parser.add_argument('--create-deck', action='store_true', default=False, help='Flag to create a deck')
    parser.add_argument('--delete-deck', action='store_true', default=False, help='Flag to delete a deck')
    parser.add_argument('--delete_all_notes_from_dataset_flag', action='store_true', default=False, help='Flag to delete all notes from a deck')
    
    args = parser.parse_args()
    
    if args.extract_and_ingest_notes:
        # # gsheets = GoogleSheets(args.url)
        gsheets = Ingestion(args.url)
        data_ops = DataOperations(
            nested_list=gsheets.sheet_nested_list,
            filter_start_row=args.filter_start_row,
            filter_end_row=args.filter_end_row,
            filter_tags=args.filter_tags
        )
    # Determine the value of notes based on the condition
    if args.extract_and_ingest_notes:
        notes = data_ops.filtered_notes_without_now_number
    else:
        notes = []
    
    AnkiOperations(
        deck_name=args.deck_name,
        notes=notes,
        create_deck_flag=args.create_deck,
        delete_deck_flag=args.delete_deck,
        add_notes_flag=args.extract_and_ingest_notes,
        delete_all_notes_from_dataset_flag=args.delete_all_notes_from_dataset_flag
    )

if __name__ == "__main__":
    main()
