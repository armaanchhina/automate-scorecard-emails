import pandas as pd
import logging
import os
import tempfile
import award
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timedelta
from typing import Tuple, Any

load_dotenv()
EMAIL = "armaan_45@hotmail.com"
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
logging.info(EMAIL_PASSWORD)

# import docraptor

# doc_api = docraptor.DocApi()
# doc_api.api_client.configuration.username = 'YOUR_API_KEY_HERE'
import smtplib
import zipfile
import shutil
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
def process_quarter():
    """Process the file and delete it afterwards."""
    result = award.main()
    if result is None:
        raise ValueError('award.main() returned None')
    return result

def job():
    # Create a temporary directory in the current working directory
    os.makedirs('/tmp/scorecards', exist_ok=True)

    # Load templates
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('scorecard.html')

    # Connect to your database and get driver ids
    df = process_quarter()
    driver_ids = df["Driver ID"]

    # Iterate over drivers and generate scorecards
    for driver_id in driver_ids:
        driver_name = df[df['Driver ID'] == driver_id]["Driver Name"].values[0]
        driverData = df[df['Driver ID'] == driver_id][["Total Bonus", "Idle Deduct", "Idle Percent", "MPG Deduct", "Efficiency (MPG)", "Harsh Deduct", "Harsh Events", "Safety Deduct", "Safety Score"]].iloc[0].to_dict()
        df = df.sort_values('Total Bonus')
        html_out = template.render(driverData=driverData, driverId=driver_id, year="2023", quarter="1")


        with open(f'/tmp/scorecards/{driver_name}_scorecard.html', 'w') as f:
            f.write(html_out)
            
    # Create zip file in the same directory
    with zipfile.ZipFile('/tmp/scorecards/scorecards.zip', 'w') as zipf:
        for file in os.listdir('/tmp/scorecards'):
            if file.endswith(".html"):
                zipf.write(os.path.join('/tmp/scorecards', file), arcname=file)


def send_zip_file() -> None:
    """
    Sends a zip file and two csv files as attachments to a specific email address.
    """
    
    # Create a MIME multipart message object
    msg = MIMEMultipart()
    msg['From'] = EMAIL
    msg['To'] = 'armaan_47@outlook.com'
    msg['Subject'] = 'Scorecard HTMLs'

    # Prepare the ZIP file attachment
    part_zip = MIMEBase('application', "octet-stream")
    with open("/tmp/scorecards/scorecards.zip", 'rb') as file:
        part_zip.set_payload(file.read())
    encoders.encode_base64(part_zip)
    part_zip.add_header('Content-Disposition', 'attachment', filename='scorecards.zip')
    msg.attach(part_zip)

    # Prepare the first CSV file attachment without deducts
    part_csv = MIMEBase('application', 'octet-stream')
    now = datetime.now()
    with open(f'{now.date()}-without-deducts.csv', 'rb') as file:
        part_csv.set_payload(file.read())
    encoders.encode_base64(part_csv)
    part_csv.add_header('Content-Disposition', 'attachment', filename=f'{now.date()}-without-deducts.csv')
    msg.attach(part_csv)

    # Prepare the second CSV file attachment with deducts
    part_csv_with_deduct = MIMEBase('application', 'octet-stream')
    now = datetime.now()
    with open(f'{now.date()}-with-deducts.csv', 'rb') as file:
        part_csv_with_deduct.set_payload(file.read())
    encoders.encode_base64(part_csv_with_deduct)
    part_csv_with_deduct.add_header('Content-Disposition', 'attachment', filename=f'{now.date()}-with-deducts.csv')
    msg.attach(part_csv_with_deduct)

    # Connect to the SMTP server and send the email
    server = smtplib.SMTP('smtp-mail.outlook.com', 587)  # SMTP server for Hotmail
    server.starttls()  # Upgrade the connection to a secure encrypted SSL/TLS connection
    server.login(EMAIL, EMAIL_PASSWORD)  # Login with sender's credentials
    text = msg.as_string()
    server.sendmail(EMAIL, 'armaan_47@outlook.com', text)
    server.quit()

    # Clean up the directory after sending the files
    shutil.rmtree('/tmp/scorecards')

def main():
    job()
    send_zip_file()

if __name__ == "__main__":
    # Call the main function
    main()