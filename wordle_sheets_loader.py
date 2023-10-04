#!/usr/bin/env python
# coding: utf-8

import argparse
import json
import os
import sqlite3

import gspread
import pandas as pd
import yaml


def parse_args() -> dict:
    """Configures and parses command line arguments.

    Returns
    -------
    dict
        Dictionary containing parsed command line arguments
    
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_path', '-c', help="path to config.yaml file", type=str, default="./config.yaml")
    return parser.parse_args()


def decode_streamtyped_blob(blob: str) -> str:
    """Extracts messages contained in binary blob under the attributedBody field
    in messages table in iMessage chat.db.

    Parameters
    ----------
    blob : str
        Binary blob from attributedBody field from iMessage db

    Returns
    -------
    str
        Decoded message string

    """
    try:
        text = blob.split(b"NSString")[1]
        text = text[5:]  # stripping some preamble which generally looks like this: b'\x01\x94\x84\x01+'
        
        # this 129 is b'\x81, python indexes byte strings as ints,
        # this is equivalent to text[0:1] == b'\x81'
        if text[0] == 129:
            length = int.from_bytes(text[1:3], "little")
            text = text[3: length + 3]
        else:
            length = text[0]
            text = text[1: length + 1]
        return text.decode()

    except Exception as e:
        print(blob)
        print(e)
        return "ERROR: Can't decode message."

def load_messages(config: dict) -> pd.DataFrame:
    """Connects to iMessage database and downloads messages.

    Parameters
    ----------
    config : dict
        Dictionary containing configuration settings

    Returns
    -------
    pd.DataFrame
        Pandas DataFrame containing iMessage contents and metadata

    """
    try:
        # find local chat.db and establish a connection
        conn = sqlite3.connect(config['message_db_path'])

        # Main SQL query to load all non-reaction messages from specified iMessage threads
        chat_id_list = [f"c.chat_id = {x}" for x in config['chat_ids']]
        chat_id_string = ' OR '.join(chat_id_list)
        query = f"""
        SELECT h.id AS handle
            , c.message_id
            , c.chat_id
            , m.is_from_me
            , m.date
            , m.text
            , m.attributedBody
        FROM message m
            LEFT JOIN chat_message_join c
                ON m.ROWID = c.message_id
            LEFT JOIN handle h
                ON m.handle_id = h.ROWID
        WHERE m.associated_message_guid IS NULL --filters out reaction messages
            AND m.attributedBody IS NOT NULL --filters out messages with no body
            AND ({chat_id_string})
        ORDER BY date DESC
        """

        return pd.read_sql_query(query, conn)
    
    finally:
        conn.close()

def format_scores(emojis_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Takes a DataFrame with decoded messages and metadata and a config file and returns a dataframe with just scores.

    Parameters
    ----------
    emojis_df : pd.DataFrame
        DataFrame with decoded messages and metadata
    config : dict
        Dictionary containing configuration settings

    Returns
    -------
    pd.DataFrame
        Pandas DataFrame containing only game numbers and scores

    """
    emojis_df.drop(['text', 'attributedBody'], axis=1, inplace=True)

    # Keep only messages with 'Wordle ?/6' syntax
    filtered_df = emojis_df[emojis_df['decoded_message'].str.contains('Wordle.*\/6.*', regex=True, na=False)]

    # Keep only messages with wordle emoji squares in them
    filtered_df = filtered_df[filtered_df['decoded_message'].str.contains('(?:⬛|⬜|🟨|🟦|🟩|🟧)',
                                                                          regex=True, na=False)]

    # Create new column with just extracted scores and fill in X / did not finish scores
    filtered_df['score'] = filtered_df['decoded_message'].str.extract('(?:Wordle \d+ )(\d)(?:/\d)', expand=True)
    filtered_df['score'] = filtered_df['score'].fillna(config['did_not_finish_score']).astype(int)

    # Create new column with game numbers
    filtered_df['game_num'] = filtered_df['decoded_message'].str.extract('(?:Wordle )(\d\d\d)(?: ./6)', expand=True)

    print(f"Found {len(filtered_df.index)} scores in iMessage threads.")

    # Use dictionary from config.yaml to translate numbers & emails to names
    filtered_df['name'] = filtered_df['handle'].replace(config['handle_dict'])

    # Use `is_from_me` flags to fill in name from config.yaml
    filtered_df.loc[filtered_df['is_from_me'] == 1, 'name'] = config['is_from_me_name']

    # make sure there are no unassigned scores
    assert len(filtered_df[filtered_df['name'].isnull()]) == 0
    assert len(filtered_df[filtered_df['name'] == '']) == 0

    scores_df = filtered_df[['name','game_num','score']].copy()

    # make sure there is only one score per game per person
    dedup_scores_df = scores_df.groupby(['name', 'game_num']).head(1)
    game_idx_df = dedup_scores_df.set_index('game_num')

    # Pivot table & clean up
    df_format_asc = game_idx_df.pivot(columns='name')
    df_format_desc = df_format_asc.sort_index(ascending=False)
    df_format_desc.fillna('', inplace=True)

    # Change game numbers from index to column
    df_format_desc.reset_index(inplace=True)

    # cast game numbers to int
    df_format_desc.game_num = df_format_desc.game_num.astype(int)

    return df_format_desc


def write_to_sheets(config: dict, names_list: list, scores_list: list) -> str:
    """Uses gspread to write score information to Google Sheet.

    Parameters
    ----------
    config : dict
        Dictionary containing configuration settings
    names_list : list
        List of player names
    scores_list : list
        List of lists containing game numbers and scores for each game

    Returns
    -------
    response : str
        Response from gspread write operation

    """
    # Google Sheets API
    gc = gspread.service_account(filename=config['service_account_key_path'])
    sh = gc.open_by_url(config['sheets_link'])
    wks = sh.get_worksheet(0)

    # Update list of names in case order changed - edit cell range if needed
    wks.update('B1:G1', [names_list])

    # Write scores to Google Sheet - edit cell range if needed
    response = wks.update(f'A5:G{len(scores_list) + 4}', scores_list)
    
    return response


def main() -> None:
    args = parse_args()
    config = yaml.safe_load(open(args.config_path))
    
    print(f'Accessing local iMessage chat.db...')
    emojis_df = load_messages(config)
    emojis_df['decoded_message'] = emojis_df['attributedBody'].apply(lambda x: decode_streamtyped_blob(x))
    formatted_scores_df = format_scores(emojis_df, config)

    # get list of names to upload them separately
    names_list = formatted_scores_df.columns.levels[1][:-1].tolist()
    # Extract values only as list
    scores_list = formatted_scores_df.values.tolist()

    game_nums = formatted_scores_df.game_num
    print(f'Writing scores to Google Sheet. Game number range: {game_nums.min()} - {game_nums.max()}')

    sheets_response = write_to_sheets(config, names_list, scores_list)

    print(f'Google Sheet update confirmation:\n{json.dumps(sheets_response, indent = 4)}')
    print(f"Google Sheet link:\n{config['sheets_link']}")

    # open Google sheet in Safari
    os.system(f"open -a Safari {config['sheets_link']}")

if __name__ == "__main__":
    main()
