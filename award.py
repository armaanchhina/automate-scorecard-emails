import requests #import library
import logging

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
    now = datetime.now()
    df = pd.DataFrame(data, columns=['Driver ID', 'Driver Name', 'Idle Deduct', 'Idle Percent', 'MPG Deduct', 'Efficiency (MPG)', "Harsh Deduct", "Harsh Events","Safety Deduct","Safety Score", "Total Bonus"])
    df = df.sort_values(by="Total Bonus", ascending=False)
    df.drop(['Driver Name','Idle Deduct', 'MPG Deduct', 'Harsh Deduct', 'Safety Deduct', 'Total Bonus'], axis=1).to_csv(f"{now.date()}-without-deducts.csv", index=False)
    df.to_csv(f"{now.date()}-with-deducts.csv", index=False)
    return df

def find_driver(df: pd.DataFrame, driver_id: str, start, end):
    data = []
    try:
        df = df[df['driver'].apply(lambda x: x['id'] if isinstance(x, dict) and 'id' in x else None) == driver_id]
    except Exception as e:
        return (f"An error occurred: {e}")

    row, (safety_score_driver, harsh_event, error) = get_safety_score_and_event_count(df.iloc[0],start,end)
    if error:
        row, (safety_score_driver, harsh_event, error) = get_safety_score_and_event_count(row, start, end)
        if(error):
            print(f"Error processing row {row['driver']['name']}: {error}")
            return
    mpg_deduct = calculate_mpg_deduction(row["efficiencyMpge"])
    idle_perct, idle_deduct = calculate_idle_deduction(row["engineRunTimeDurationMs"], row["engineIdleTimeDurationMs"])
    id = row["driver"]["id"]
    name = row["driver"]["name"]
    harsh_cost = calculate_harsh_deduction(harsh_event)

    safety_deduct = calculate_safety_deduction(safety_score_driver)
    final_bonus = INITAL_BONUS - (mpg_deduct + idle_deduct + harsh_cost + safety_deduct)

    data.append([id, name, idle_deduct, idle_perct, mpg_deduct,row["efficiencyMpge"], harsh_cost, harsh_event,safety_deduct, safety_score_driver, final_bonus])
    print(data)
    return data

def parse_df(df: pd.DataFrame, start_date_unix: str, end_date_unix: str):
    data = []
    # print(df['driver'].head())
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


# This function will get safety score and event count for a driver in a certain period
def get_safety_score_and_event_count(row, start_time: str, end_time: str):
    driver_id = row["driver"]["id"]
    max_retries = 5  # You can adjust this number as needed
    retries = 0

    while retries < max_retries:
        try:
            url = f"https://api.samsara.com/v1/fleet/drivers/{driver_id}/safety/score?startMs={start_time}&endMs={end_time}"
            headers = {
                "accept": "application/json",
                "authorization": f"Bearer {SAMSARA_API_TOKEN}"
            }
            response = requests.get(url, headers=headers)

            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')  # Retrieve the value of Retry-After header
                time.sleep(0.5)  # Delay the execution of the next request
                retries += 1
                continue  # Go to next iteration of loop, re-running the request

            # If response is successful, parse json and return
            json_data = response.json()
            return row, (json_data["safetyScore"], json_data["totalHarshEventCount"], None)

        except Exception as e:
            return row, (None, None, f"An error occurred: {e}")
    
    # If the loop completes without a successful request, return an error
    return row, (None, None, f"An error occurred: Maximum retries reached")




def get_in_unix_epoch(start_date: str, end_date: str):
    decoded_start = unquote(start_date)
    decoded_end = unquote(end_date)
    date_start = decoded_start.split("T")[0]
    date_end = decoded_end.split("T")[0]
    date_start_final = f'{date_start} 01:01:00'
    date_end_final = f'{date_end} 23:00:00'

    unix_epoch_start = (calendar.timegm(time.strptime(date_start_final, '%Y-%m-%d %H:%M:%S'))) * 1000
    unix_epoch_end = (calendar.timegm(time.strptime(date_end_final, '%Y-%m-%d %H:%M:%S'))) * 1000

    print(unix_epoch_end, unix_epoch_start)
    return unix_epoch_start, unix_epoch_end





def get_past_week_dates():
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    # Format the dates as strings with the format you've specified
    now_str = now.strftime('%Y-%m-%dT%H%%3A%M%%3A%S.%f%%2B00%%3A00')
    week_ago_str = week_ago.strftime('%Y-%m-%dT%H%%3A%M%%3A%S.%f%%2B00%%3A00')
    print(week_ago_str)
    print(now_str)

    return (week_ago_str, now_str)

def get_past_quarter_dates():
    now = datetime.now()
    print(now.date())
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


    


def update_year(year):
    global CURRENT_YEAR, QUARTERLY
    CURRENT_YEAR = year
    QUARTERLY = {
            #2023-07-05T10%3A05%3A26.240948%2B00%3A00
        1: (f"{CURRENT_YEAR}-01-01T23%3A59%3A59.394843%2B00%3A00", f"{CURRENT_YEAR}-03-31T23%3A59%3A59.394843%2B00%3A00"), 
        2: (f"{CURRENT_YEAR}-04-01T23%3A59%3A59.394843%2B00%3A00", f"{CURRENT_YEAR}-06-30T23%3A59%3A59.394843%2B00%3A00"),
        3: (f"{CURRENT_YEAR}-07-01T23%3A59%3A59.394843%2B00%3A00", f"{CURRENT_YEAR}-09-30T23%3A59%3A59.394843%2B00%3A00"), 
        4: (f"{CURRENT_YEAR}-10-01T23%3A59%3A59.394843%2B00%3A00", f"{CURRENT_YEAR}-12-31T23%3A59%3A59.394843%2B00%3A00")
    }


def get_current_quarter():
    now = datetime.now()
    year_curr = now.year
    if(now.month < 4):
        return f"{year_curr}-01-01T23%3A59%3A59.394843%2B00%3A00"
    elif(now.month<7):
        return f"{year_curr}-04-01T23%3A59%3A59.394843%2B00%3A00"
    elif(now.month<10):
        return f"{year_curr}-07-01T23%3A59%3A59.394843%2B00%3A00"
    else:
        return f"{year_curr}-10-01T23%3A59%3A59.394843%2B00%3A00"


# def send_email():
#     # Create a multipart message
#     msg = MIMEMultipart()
#     body_part = MIMEText(MESSAGE_BODY, 'plain')
#     msg['Subject'] = EMAIL_SUBJECT
#     msg['From'] = EMAIL_FROM
#     msg['To'] = EMAIL_TO
#     # Add body to email
#     msg.attach(body_part)
#     # open and read the CSV file in binary
#     with open(PATH_TO_CSV_FILE,'rb') as file:
#     # Attach the file with filename to the email
#         msg.attach(MIMEApplication(file.read(), Name=FILE_NAME))
#     # Create SMTP object    smtp_obj = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
#     # Login to the server    smtp_obj.login(SMTP_USERNAME, SMTP_PASSWORD)
#     # Convert the message to a string and send it
#     smtp_obj.sendmail(msg['From'], msg['To'], msg.as_string())
#     smtp_obj.quit()

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