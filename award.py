import requests #import library
import logging
from typing import Tuple, Dict, Union, Any

import json
import pandas as pd
import os
import calendar, time
from urllib.parse import unquote
from dotenv import load_dotenv
import concurrent.futures
from datetime import datetime, timedelta
load_dotenv()
SAMSARA_API_TOKEN = os.getenv('SAMSARA_API_TOKEN')
logging.info(SAMSARA_API_TOKEN)

# request = input("Enter url of data needed: " )
# url = "https://api.samsara.com/fleet/reports/vehicles/fuel-energy?startDate=2022-03-31T23%3A59%3A59.394843%2B00%3A00&endDate=2022-03-31T23%3A59%3A59.394843%2B00%3A00"


OUTPUT_FILE = "output.csv"

INITAL_BONUS = 500


ZERO_DEDUCTION = 0 #key value for cost of tier 0 deduction
MID_DEDUCTION = 1 #key value for cost of tier 1 deduction
HIGH_DEDUCTION = 2 #key value for cost of tier 2 deduction

MID_COST = 25
HIGH_COST = 50

DEDUCTION = {
    ZERO_DEDUCTION: 0,
    MID_DEDUCTION: MID_COST,
    HIGH_DEDUCTION: HIGH_COST
}

SAFETY_SCORE_RANGE = [98, (96,97), 95]

IDLE_RANGES = [7.0, (7.1, 24), 24.1]

HARSH_RANGE = [0,1,2]
MPG = [7.0, (6.0,6.9), 5.9]


def calculate_idle_deduction(run_time, idle_time):
    '''
    IDLE_RANGES = [7.0, (7.1, 24), 24.1]
    '''
    idle_perct = float((idle_time/run_time) * 100)
    if idle_perct >= IDLE_RANGES[2]:
        deduct = DEDUCTION[HIGH_DEDUCTION]
    elif isinstance(IDLE_RANGES[1], tuple) and IDLE_RANGES[1][0] <= idle_perct <= IDLE_RANGES[1][1]:
        deduct =  DEDUCTION[MID_DEDUCTION]
    else:
        deduct =  DEDUCTION[ZERO_DEDUCTION]
    return idle_perct, deduct
    
def calculate_safety_deduction(safety_score):
    '''
    SAFETY_SCORE_RANGE = [98, (96,97), 95]
    '''
    if safety_score <= SAFETY_SCORE_RANGE[2]:
        return DEDUCTION[HIGH_DEDUCTION]
    elif isinstance(SAFETY_SCORE_RANGE[1], tuple) and SAFETY_SCORE_RANGE[1][0] <= safety_score <= SAFETY_SCORE_RANGE[1][1]:
        return DEDUCTION[MID_DEDUCTION]
    else:
        return DEDUCTION[ZERO_DEDUCTION]
    
def calculate_mpg_deduction(mpg):
    '''
    MPG = [7.0, (6.0,6.9), 5.9]
    '''
    if mpg <= MPG[2]:
        return DEDUCTION[HIGH_DEDUCTION]
    elif isinstance(MPG[1], tuple) and MPG[1][0] <= mpg <= MPG[1][1]:
        return DEDUCTION[MID_DEDUCTION]
    else:
        return DEDUCTION[ZERO_DEDUCTION]
    
def calculate_harsh_deduction(events) -> int:
    if(events>=HARSH_RANGE[2]):
        return DEDUCTION[HIGH_DEDUCTION]
    elif(events==HARSH_RANGE[1]):
        return DEDUCTION[MID_DEDUCTION]
    else:
        return DEDUCTION[ZERO_DEDUCTION]


def write_to_csv(data: list) -> pd.DataFrame:
    """
    Converts a list of data into a DataFrame, sorts it by "Total Bonus", and writes two CSV files.
    
    Args:
    - data (list): A list containing driver data.
    
    Returns:
    - pd.DataFrame: The DataFrame generated from the provided list.
    """

    # Get the current date
    now = datetime.now()
    
    # Convert the list to a DataFrame
    df = pd.DataFrame(data, columns=['Driver ID', 'Driver Name', 'Idle Deduct', 'Idle Percent', 'MPG Deduct', 
                                     'Efficiency (MPG)', "Harsh Deduct", "Harsh Events", "Safety Deduct", 
                                     "Safety Score", "Total Bonus"])

    # Sort the DataFrame by the "Total Bonus" column in descending order
    df = df.sort_values(by="Total Bonus", ascending=False)

    # Write the DataFrame without certain deduction-related columns to a CSV file
    df.drop(['Driver Name','Idle Deduct', 'MPG Deduct', 'Harsh Deduct', 'Safety Deduct', 'Total Bonus'], axis=1)\
      .to_csv(f"{now.date()}-without-deducts.csv", index=False)
    
    # Write the full DataFrame to another CSV file
    df.to_csv(f"{now.date()}-with-deducts.csv", index=False)
    
    return df


def find_driver(df: pd.DataFrame, driver_id: str, start: str, end: str) -> list:
    """
    Find a specific driver by their ID from the provided DataFrame and calculate various metrics for them.
    
    Args:
    - df (pd.DataFrame): The DataFrame containing driver data.
    - driver_id (str): The ID of the driver to find.
    - start (str): The start date in UNIX epoch milliseconds.
    - end (str): The end date in UNIX epoch milliseconds.
    
    Returns:
    - list: A list containing processed data for the specified driver.
    """
    
    data = []
    
    # Filter the DataFrame for rows with the specified driver ID
    try:
        df = df[df['driver'].apply(lambda x: x['id'] if isinstance(x, dict) and 'id' in x else None) == driver_id]
    except Exception as e:
        return (f"An error occurred: {e}")

    # Fetch safety score and event count for the specific driver
    row, (safety_score_driver, harsh_event, error) = get_safety_score_and_event_count(df.iloc[0], start, end)
    if error:
        row, (safety_score_driver, harsh_event, error) = get_safety_score_and_event_count(row, start, end)
        if error:
            print(f"Error processing row {row['driver']['name']}: {error}")
            return

    # Calculate deductions and bonuses based on various metrics
    mpg_deduct = calculate_mpg_deduction(row["efficiencyMpge"])
    idle_perct, idle_deduct = calculate_idle_deduction(row["engineRunTimeDurationMs"], row["engineIdleTimeDurationMs"])
    id = row["driver"]["id"]
    name = row["driver"]["name"]
    harsh_cost = calculate_harsh_deduction(harsh_event)
    safety_deduct = calculate_safety_deduction(safety_score_driver)
    final_bonus = INITAL_BONUS - (mpg_deduct + idle_deduct + harsh_cost + safety_deduct)

    # Append the processed data to the result list
    data.append([id, name, idle_deduct, idle_perct, mpg_deduct, row["efficiencyMpge"], harsh_cost, harsh_event, safety_deduct, safety_score_driver, final_bonus])
    
    print(data)
    return data

def parse_df(df: pd.DataFrame, start_date_unix: str, end_date_unix: str):
    """
    Processes a DataFrame to get additional safety scores and event counts for each driver. 
    Then, calculates various deductions and bonuses based on multiple metrics.
    
    Args:
    - df (pd.DataFrame): The DataFrame containing driver data.
    - start_date_unix (str): The start date in UNIX epoch milliseconds.
    - end_date_unix (str): The end date in UNIX epoch milliseconds.
    
    Returns:
    - list: A list of lists containing processed data for each driver.
    """
    data = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_row = {executor.submit(get_safety_score_and_event_count, row, start_date_unix, end_date_unix): row for _, row in df.iterrows()}
        for future in concurrent.futures.as_completed(future_to_row):
            row, (safety_score_driver, harsh_event, error) = future.result()
            if error:
                row, (safety_score_driver, harsh_event, error) = get_safety_score_and_event_count(row, start_date_unix, end_date_unix)
                if(error):
                    print(f"Error processing row {row['driver']['name']}: {error}")
                    continue
            mpg_deduct = calculate_mpg_deduction(row["efficiencyMpge"])
            idle_perct, idle_deduct = calculate_idle_deduction(row["engineRunTimeDurationMs"], row["engineIdleTimeDurationMs"])
            id = row["driver"]["id"]
            name = row["driver"]["name"]
            harsh_cost = calculate_harsh_deduction(harsh_event)

            safety_deduct = calculate_safety_deduction(safety_score_driver)
            final_bonus = INITAL_BONUS - (mpg_deduct + idle_deduct + harsh_cost + safety_deduct)

            data.append([id, name, idle_deduct, round(idle_perct, 2), mpg_deduct,round(row["efficiencyMpge"], 2), harsh_cost, harsh_event,safety_deduct, safety_score_driver, final_bonus])
        return data





def fuel_and_energy_call(start_date: int, end_date: int):
    """
    Fetch the fuel and energy data for drivers within a specified date range.

    Args:
    - start_date (int): Start date in UNIX epoch milliseconds.
    - end_date (int): End date in UNIX epoch milliseconds.

    Returns:
    - pd.DataFrame: A DataFrame containing driver reports for the specified date range.
    - str: An error message if an error occurs.
    """
    url = f"https://api.samsara.com/fleet/reports/drivers/fuel-energy?startDate={start_date}&endDate={end_date}"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {SAMSARA_API_TOKEN}"
    }

    # try:
    response = requests.get(url, headers=headers)
    # Extract the JSON data from the response
    json_data = response.json()
    # Extract the driver reports from the JSON data
    driver_reports = json_data['data']['driverReports']
    df = pd.DataFrame(driver_reports)
    # except Exception as e:
    #     return (f"An error occurred: {e}")
    return df



def get_safety_score_and_event_count(row: Dict[str, Dict[str, str]], 
                                     start_time: str, 
                                     end_time: str) -> Tuple[Dict[str, Dict[str, str]], Tuple[Union[int, None], Union[int, None], Union[str, None]]]:
    """
    Fetch the safety score and the total harsh event count for a driver in a specified time period.

    Args:
    - row (Dict[str, Dict[str, str]]): Dictionary containing driver details with nested driver id.
    - start_time (str): Start time in UNIX epoch milliseconds.
    - end_time (str): End time in UNIX epoch milliseconds.

    Returns:
    - Tuple: Original data row and a tuple containing:
      1. Safety Score (int or None)
      2. Total Harsh Event Count (int or None)
      3. Error message if an error occurs, otherwise None (str or None)
    """
    
    driver_id = row["driver"]["id"]
    max_retries = 5  # Maximum number of request retries
    retries = 0

    while retries < max_retries:
        try:
            # Constructing the API URL
            url = f"https://api.samsara.com/v1/fleet/drivers/{driver_id}/safety/score?startMs={start_time}&endMs={end_time}"
            
            # Setting the headers for the request
            headers = {
                "accept": "application/json",
                "authorization": f"Bearer {SAMSARA_API_TOKEN}"
            }

            # Making the API request
            response = requests.get(url, headers=headers)

            # If we get a 'too many requests' response, wait and then retry
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')  # Get the suggested wait time from the API
                time.sleep(0.5)  # Introducing a wait before retrying
                retries += 1
                continue  # Continue to the next iteration to retry

            # If response is successful, parse the returned JSON and extract the needed data
            json_data = response.json()
            return row, (json_data["safetyScore"], json_data["totalHarshEventCount"], None)

        except Exception as e:  # Catching any exception that occurs during the process
            return row, (None, None, f"An error occurred: {e}")
    
    # If maximum retries are reached without a successful request, return with an error message
    return row, (None, None, f"An error occurred: Maximum retries reached")



def get_in_unix_epoch(start_date: str, end_date: str) -> Tuple[int, int]:
    """
    Convert the given URL-encoded ISO8601 date strings to UNIX epoch time.
    
    Parameters:
    - start_date (str): URL-encoded start date string in ISO8601 format.
    - end_date (str): URL-encoded end date string in ISO8601 format.
    
    Returns:
    - tuple: A tuple containing two integers:
        1. UNIX epoch time for the start of the 'start_date' in milliseconds.
        2. UNIX epoch time for the end of the 'end_date' in milliseconds.
    """
    
    # Decode the URL-encoded date strings.
    decoded_start = unquote(start_date)
    decoded_end = unquote(end_date)
    
    # Extract just the date portion from the decoded strings.
    date_start = decoded_start.split("T")[0]
    date_end = decoded_end.split("T")[0]
    
    # Append the time to the extracted dates to represent the start and end of the days respectively.
    date_start_final = f'{date_start} 01:01:00'
    date_end_final = f'{date_end} 23:00:00'
    
    # Convert the final date strings to UNIX epoch time in milliseconds.
    unix_epoch_start = (calendar.timegm(time.strptime(date_start_final, '%Y-%m-%d %H:%M:%S'))) * 1000
    unix_epoch_end = (calendar.timegm(time.strptime(date_end_final, '%Y-%m-%d %H:%M:%S'))) * 1000
    
    # For debugging purposes, print the dates.
    print("Start Epoch:", unix_epoch_start)
    print("End Epoch:", unix_epoch_end)
    
    return unix_epoch_start, unix_epoch_end




def get_past_week_dates() -> Tuple[str, str]:
    """
    Determines the current date and the date exactly one week ago.
    
    Returns:
        tuple: A tuple containing two strings:
            1. Date exactly one week ago in the desired format.
            2. Current date in the same format.
    """
    
    # Get the current date and time
    now = datetime.now()

    # Calculate the date exactly one week ago from 'now'
    week_ago = now - timedelta(days=7)
    
    # Format the dates to the specific format. This format seems to be 
    # tailored for URLs and includes URL-encoded colons and plus signs.
    now_str = now.strftime('%Y-%m-%dT%H%%3A%M%%3A%S.%f%%2B00%%3A00')
    week_ago_str = week_ago.strftime('%Y-%m-%dT%H%%3A%M%%3A%S.%f%%2B00%%3A00')
    
    # For debugging purposes, print the dates
    print("One week ago:", week_ago_str)
    print("Now:", now_str)

    return (week_ago_str, now_str)

def get_past_quarter_dates() -> Tuple[str, str]:
    """
    Determines the start date of the current quarter and the current date.
    
    Returns:
        tuple: A tuple containing two strings:
            1. Start date of the current quarter in a specific format.
            2. Current date in the same format.
    """
    
    now = datetime.now()
    
    # Determine the current quarter
    current_quarter = (now.month - 1) // 3 + 1
    
    # Calculate the start date of the current quarter
    current_quarter_start = datetime(now.year, (current_quarter - 1) * 3 + 1, 1)
    
    # Set the end date as the current day
    current_day = datetime(now.year, now.month, now.day)
    
    # Format the dates as strings with the desired format
    start_date_str = current_quarter_start.strftime('%Y-%m-%dT%H%%3A%M%%3A%S.%f%%2B00%%3A00')
    end_date_str = current_day.strftime('%Y-%m-%dT%H%%3A%M%%3A%S.%f%%2B00%%3A00')
    
    return (start_date_str, end_date_str)

# Example usage:
start, end = get_past_quarter_dates()
print("Start Date:", start)
print("End Date:", end)


    




def get_current_quarter() -> str:
    """
    Returns the start date of the current quarter in a specific string format.

    Returns:
        str: The formatted date string for the start of the current quarter.
    """

    now = datetime.now()
    current_year = now.year

    # Based on the month, determine the quarter and return the appropriate string format.
    if now.month < 4:
        return f"{current_year}-01-01T23%3A59%3A59.394843%2B00%3A00"
    elif now.month < 7:
        return f"{current_year}-04-01T23%3A59%3A59.394843%2B00%3A00"
    elif now.month < 10:
        return f"{current_year}-07-01T23%3A59%3A59.394843%2B00%3A00"
    else:
        return f"{current_year}-10-01T23%3A59%3A59.394843%2B00%3A00"



def main():
    print("arrived")

    start_date, end_date = get_past_quarter_dates()
    start_date = get_current_quarter()
    start_date_unix, end_date_unix = get_in_unix_epoch(start_date, end_date)
    try:
        df_fuel = fuel_and_energy_call(start_date, end_date)
        data = parse_df(df_fuel,start_date_unix,end_date_unix)
        final_df = write_to_csv(data)
        return final_df
    except Exception as e:
        print (f"An error occurred main: {e}")

if __name__ == "__main__":
    main()