# WORDLE Sheets Loader

## Overview
This project can extract Wordle scores from an iMessage thread and load them to a Google Sheet. It was developed using Mac OS X Ventura 13.5.2 on Apple Silicon (M1 chip) and Python 3.11.5.

There is a Jupyter Notebook that will step you through some required exporatory steps that are needed in order to fill out the `config.yaml` file that is needed to run this tool (e.g. finding the IDs for the iMessage threads in question). Once the `config.yaml` is set up correctly, the `wordle_sheets_loader.py` script can be called from the command line.

## Required Setup
* (Optional): If you have conda installed, create a Conda environment using env.txt file:
    * conda env create --file wordle-py-env.txt
* Allow access Full Disk Access for Terminal application so Python can read iMessage database:
    * System Settings > Privacy & Security > Full Disk Access > enable Terminal (use `+` icon to add if needed)
    * Confirm you can access the `chat.db` file from Terminal by running `ls -l ~/Library/Messages/chat.db`
    * Add the full file path (`/Users/<username>/Library/Messages/chat.db`) to `config.yaml` under `message_db_path`
* Create a Google Sheet
    * [Click here for a link to a Google Sheets template](https://docs.google.com/spreadsheets/d/1EwmcvUiSpH96aSp_1WPyiRNOgkXEi9m7SnZVAY5fHVw/template/preview) > click `USE TEMPLATE` > save a copy in your own account
    * Once you've created your own sheet, copy and paste the `sharing link` into the `sheets_link` value in `config.yaml`
* Create a Service Account to allow access to your Google Sheet
    * The [Authentication section of the gspread docs](https://docs.gspread.org/en/latest/oauth2.html) have good instructions. I opted to create a Service Account and a Service Account key JSON file.
    * Save the JSON file to a safe location on your local system and add the path as the `service_account_key_path` value in `config.yaml`
* Follow steps below to find one (or more) `chat_ids` that correspond to the iMessage threads your Wordle score messages are in
    * fill in `chat_ids` in `config.yaml`
    * Create entries in `handle_dict` in `config.yaml` to translate phone numbers and/or iMessage email IDs into names
    * Put your own name in the `is_from_me_name` in `config.yaml`

## Screenshot
Here is a screenshot of what the score sheet might look like after loading up a number of scores:
![Sample score sheet](./images/sheet_screenshot.png)

### References:
* Article: https://towardsdatascience.com/heres-how-you-can-access-your-entire-imessage-history-on-your-mac-f8878276c6e9
* GitHub code - iMessage DB analysis: https://github.com/yortos/imessage-analysis
* iMessage reader - incl. bytestring decoding: https://github.com/niftycode/imessage_reader
