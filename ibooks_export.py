import os
import getpass as gt
from glob import glob
import pandas as pd
import sqlite3
import re
import sys


class MDFile:
    def __init__(self, title, directory):
        self.file = ""
        self.filename = os.path.join(directory, f"{title}_notes.md")
        self.headers = []
        self.title = get_title(title)

    def add_header(self, level, title, header_id=""):
        header, header_id = get_header(level, title, header_id)
        self.file += header
        self.headers.append({"level": level, "header": f"[{title}](#{header_id})"})

    def add_paragraph(self, text):
        self.file += f"\n\n{text}"

    def add_table_of_content(self, title, depth):
        toc = []
        title = get_title(title)
        for header in self.headers:
            level = header["level"]
            if level <= depth:
                toc.append("\t"*(level-1) + f"* {header['header']}")
        toc = '\n'.join(toc) + '\n'
        self.file = title + toc + self.file

    def add_line(self, text):
        self.file += " \n" + text

    def add_status(self, title, level):
        header, _ = get_header(level, title)
        self.file = header + self.file

    def write_annotations(self, annotations, chapter):
        self.add_header(level=2, title=chapter)
        index = 1
        for annotation in annotations:
            note = annotation["notes"]
            self.add_header(level=3, title=str(index).rjust(3, '0'))
            self.add_paragraph(annotation["highlights"])
            if note:
                note = note.split('\n')
                if len(note) > 1:
                    for n in note:
                        self.add_line(f"> {n}")
                else:
                    self.add_paragraph(f"> {note[0]}")
            index += 1

    def write_file(self):
        with open(self.filename, 'w') as file:
            file.write(self.title + self.file)


def get_title(title):
    return "\n" + title + "\n" + "".join(["=" for _ in title]) + "\n"


def get_header(level, title, header_id=""):
    header_id = header_id if header_id else re.sub("[^a-z0-9_\-]", "", title.lower().replace(" ", "-"))
    header = f"\n\n{'#' * level} {title} \n"
    return header, header_id


def get_argument():
    if len(sys.argv) == 1:
        return 'books/'
    elif sys.argv[1] == '--directory':
        directory = sys.argv[2]
    else:
        raise ValueError("only argument --directory is supported")

    return directory


def get_database_path(db_dir):
    databases = glob(db_dir + '/*.sqlite')
    if len(databases) == 0:
        raise ValueError("No data found in the database.")
    return databases[0]


def get_database_connection(db_dir):
    db_path = get_database_path(db_dir)
    try:
        database = sqlite3.connect(db_path)
    except sqlite3.Error as error:
        raise ValueError(error)
    database.text_factory = lambda x: str(x, "utf8")
    return database


def get_metadata(db_dir, mode):
    database = get_database_connection(db_dir)
    if mode == 'books':
        query = """
        SELECT 
            ZASSETID as AssetID, ZTITLE AS Title, ZAUTHOR AS Author, ZCOVERURL as CoverURL, ZGENRE as Genre,
            ZISFINISHED as IsFinished
        FROM ZBKLIBRARYASSET 
        WHERE ZTITLE IS NOT NULL
        """
    else:
        query = '''
        SELECT
            ZANNOTATIONREPRESENTATIVETEXT as BroaderText,
            ZANNOTATIONSELECTEDTEXT as HighlightedText,
            ZANNOTATIONNOTE as Note,
            ZFUTUREPROOFING5 as Chapter,
            ZANNOTATIONCREATIONDATE as Created,
            ZANNOTATIONMODIFICATIONDATE as Modified,
            ZANNOTATIONASSETID,
            ZPLLOCATIONRANGESTART,
            ZANNOTATIONLOCATION
        FROM ZAEANNOTATION
        WHERE ZANNOTATIONSELECTEDTEXT IS NOT NULL
        ORDER BY ZANNOTATIONASSETID ASC,Created ASC
        '''
    metadata = pd.read_sql_query(query, database)
    return metadata


def save_refined(data, filename):
    data["Title"] = data["Title"].str.replace(r'(\(|【)(.*?)(】|\))', '', regex=True)
    data.to_csv(filename, index=False)
    return data


def save_combined_data(books, notes, data_path):
    metadata_raw = pd.merge(books, notes, how="inner", left_on="AssetID", right_on="ZANNOTATIONASSETID")
    metadata_raw.drop(["ZANNOTATIONASSETID"], axis=1, inplace=True)
    books = save_refined(books, os.path.join(data_path, "ibooks_library_books.csv"))
    metadata = save_refined(metadata_raw, os.path.join(data_path, "ibooks_library_notes.csv"))
    return books, metadata


def get_chapter(metadata, index):
    chapter = metadata.loc[index, "Chapter"]
    chapter = chapter if chapter else "Unknown"
    return chapter


def create_md_file(book, metadata, directory):
    title = book["Title"]
    md_file = MDFile(title=title, directory=directory)
    md_file.add_header(level=1, title='Book Overview')
    for k, v in book.items():
        if k != 'IsFinished':
            md_file.add_paragraph(f"**{k}**: {v}")
    chapter_collection = []
    notes_collection = {}
    annotation_collection = {}
    for i in metadata.index:
        chapter = get_chapter(metadata, i)
        if chapter not in notes_collection:
            chapter_collection.append(chapter)
            notes_collection[chapter] = []
            annotation_collection[chapter] = []
        annotation = {'highlights': metadata.loc[i, 'HighlightedText'],
                      'notes': metadata.loc[i, 'Note']}
        if metadata.loc[i, 'Note']:
            notes_collection[chapter].append(annotation)
        annotation_collection[chapter].append(annotation)
    md_file.add_header(level=1, title='Notes Collection')
    for chapter in chapter_collection:
        notes = notes_collection[chapter]
        if notes:
            md_file.write_annotations(notes, chapter)
    md_file.add_header(level=1, title='Highlights & Notes')
    for chapter in chapter_collection:
        annotations = annotation_collection[chapter]
        md_file.write_annotations(annotations, chapter)
    md_file.add_table_of_content(title='Contents', depth=2)
    status = "✅ Finished" if book["IsFinished"] else "📖 In Progress"
    md_file.add_status(status, level=3)
    md_file.write_file()


def export_library_data(user, directory):
    data_path = os.path.join(directory, "raw_data/")
    if not os.path.exists(data_path):
        os.makedirs(data_path)
    lib_dir = f"/Users/{user}/Library/Containers/com.apple.iBooksX/Data/Documents"
    books_dir = lib_dir + "/BKLibrary"
    notes_dir = lib_dir + "/AEAnnotation"

    books_metadata_raw = get_metadata(books_dir, mode="books")
    notes_metadata_raw = get_metadata(notes_dir, mode="notes")

    books, metadata = save_combined_data(books_metadata_raw, notes_metadata_raw, data_path)
    for title in books["Title"]:
        book = books[books["Title"] == title].to_dict(orient="records")[0]
        book_meta = metadata[metadata["Title"] == title].reset_index()
        if book_meta.shape[0] > 0:
            create_md_file(book, book_meta, directory)
    print(f"Exported highlights & notes from {len(books)} books.")


if __name__ == "__main__":
    dir_name = get_argument()
    username = gt.getuser()
    export_library_data(username, dir_name)
