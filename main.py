import pandas as pd
import subprocess
import os
import io
import tempfile
import plotly.express as px
import plotly.io as pio
from award import main
import pdfkit
import yagmail
from dotenv import load_dotenv

import time
from jinja2 import Environment, FileSystemLoader
load_dotenv()
from weasyprint import HTML
EMAIL = "armaan_45@hotmail.com"
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
print(EMAIL_PASSWORD)


import smtplib
import zipfile
import shutil
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
def process_quarter():
    """Process the file and delete it afterwards."""
    return main()

def job():
    # Create a temporary directory in the current working directory
    os.makedirs('scorecards', exist_ok=True)

    # Load templates
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('scorecard.html')

    # Connect to your database and get driver ids
    df = process_quarter()
    driver_ids = df["Driver ID"]

    # Iterate over drivers and generate scorecards
    for driver_id in driver_ids:
        driver_name = df[df['Driver ID'] == driver_id]["Driver Name"].values[0]
        print(driver_name)
        driverData = df[df['Driver ID'] == driver_id][["Total Bonus", "Idle Deduct", "Idle Percent", "MPG Deduct", "Efficiency", "Harsh Deduct", "Harsh Events", "Safety Deduct", "Safety Score"]].iloc[0].to_dict()
        print(driverData)
        df = df.sort_values('Total Bonus')
        html_out = template.render(driverData=driverData, driverId=driver_id, year="2023", quarter="1")
        with open(f'scorecards/scorecard_{driver_name}.html', 'w') as f:
            f.write(html_out)
    
    # Create zip file in the same directory
    with zipfile.ZipFile('scorecards/scorecards.zip', 'w') as zipf:
        for file in os.listdir('scorecards'):
            if file.endswith(".html"):
                zipf.write(os.path.join('scorecards', file), arcname=file)

# def zip_html_files(directory):
#     # Create a ZipFile object
#     with zipfile.ZipFile('/tmp/html_files.zip', 'w') as zipf:
#         # Iterate over all the files in directory
#         for foldername, subfolders, filenames in os.walk(directory):
#             for filename in filenames:
#                 # Check if the file is an HTML file
#                 if filename.endswith('.html'):
#                     # Create complete filepath of file in directory
#                     filepath = os.path.join(foldername, filename)
#                     # Add file to zip
#                     zipf.write(filepath)

# def send_zip_file():
#     # Create a yagmail.SMTP object
#     yag = yagmail.SMTP('armaanchhina872@gmail.com', password="Apple.ca1")
    
#     # Send an email with the ZIP file as an attachment
#     yag.send(
#         to='armaan_490@outlook.com',
#         subject='HTML Files',
#         contents='Please find attached a ZIP file containing all the HTML files.',
#         attachments='/tmp/html_files.zip',  # Path to your ZIP file
#     )

def send_zip_file():
    msg = MIMEMultipart()
    msg['From'] = EMAIL
    msg['To'] = 'armaan_47@outlook.com'
    msg['Subject'] = 'Scorecard HTMLs'

    part = MIMEBase('application', "octet-stream")
    with open("scorecards/scorecards.zip", 'rb') as file:  # Corrected the path here
        part.set_payload(file.read())
    encoders.encode_base64(part)

    part.add_header('Content-Disposition', 'attachment', filename='scorecards.zip')  # or whatever the zip is named
    msg.attach(part)

    server = smtplib.SMTP('smtp-mail.outlook.com', 587)  # SMTP server for Hotmail
    server.starttls()
    server.login(EMAIL, EMAIL_PASSWORD)
    text = msg.as_string()
    server.sendmail(EMAIL, 'armaan_47@outlook.com', text)
    server.quit()

    # Clean up the directory
    shutil.rmtree('scorecards')


if __name__ == "__main__":
    job()
    # zip_html_files('/tmp')
    send_zip_file()



# # Open the HTML file and read its contents
# with open('your_html_file.html', 'r') as file:
#     html_string = file.read()

# # Convert the HTML string to PDF
# HTML(string=html_string).write_pdf('output.pdf')