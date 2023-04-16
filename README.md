# ibooks_annotation_export

## Overview
An easy-to-use tool to export all the highlights and notes from your Apple iBooks Library into markdown files.

## How to use
Use argument --directory to specify the path to save your markdown files.
If not specified, it would create a new directory called `books` by default.
```
$ python3 ibooks_export.py
```

## Output
- Markdown files for each book containing its highlights and notes (under the directory specified)
- CSV files for books metadata and annotations metadata (under a `raw_data` sub-folder)