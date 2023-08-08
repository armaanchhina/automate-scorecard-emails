import pandas as pd
import logging
import os
import tempfile
import award
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
load_dotenv()
EMAIL = "armaan_45@hotmail.com"
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
logging.info(EMAIL_PASSWORD)
import pdfkit

import docraptor

doc_api = docraptor.DocApi()
doc_api.api_client.configuration.username = 'YOUR_API_KEY_HERE'
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
        print(driver_name)
        driverData = df[df['Driver ID'] == driver_id][["Total Bonus", "Idle Deduct", "Idle Percent", "MPG Deduct", "Efficiency (MPG)", "Harsh Deduct", "Harsh Events", "Safety Deduct", "Safety Score"]].iloc[0].to_dict()
        print(driverData)
        df = df.sort_values('Total Bonus')
        html_out = template.render(driverData=driverData, driverId=driver_id, year="2023", quarter="1")


        with open(f'/tmp/scorecards/scorecard_{driver_name}.html', 'w') as f:
            f.write(html_out)
        pdfkit.from_file(f'/tmp/scorecards/scorecard_{driver_name}.html', 'out.pdf')
        
        response = doc_api.create_doc({
        "test": True,                                                   # test documents are free but watermarked
        "document_content": html_out,    # supply content directly
        # "document_url": "http://docraptor.com/examples/invoice.html", # or use a url
        "name": "docraptor-python.pdf",                                 # help you find a document later
        "document_type": "pdf",                                         # pdf or xls or xlsx
        # "javascript": True,                                           # enable JavaScript processing
        # "prince_options": {
        #   "media": "screen",                                          # use screen styles instead of print styles
        #   "baseurl": "http://hello.com",                              # pretend URL when using document_content
        # },
        })

  
        # send a HTTP request to the server and save
        # the HTTP response in a response object called r
        with open('github-sync.pdf', 'w+b') as f:
            binary_formatted_response = bytearray(response)
            f.write(binary_formatted_response)
            f.close()
        print('Successfully created github-sync.pdf!')
            
    # Create zip file in the same directory
    with zipfile.ZipFile('/tmp/scorecards/scorecards.zip', 'w') as zipf:
        for file in os.listdir('/tmp/scorecards'):
            if file.endswith(".html"):
                zipf.write(os.path.join('/tmp/scorecards', file), arcname=file)


def send_zip_file():
    msg = MIMEMultipart()
    msg['From'] = EMAIL
    msg['To'] = 'armaan_47@outlook.com'
    msg['Subject'] = 'Scorecard HTMLs'

    part = MIMEBase('application', "octet-stream")
    with open("/tmp/scorecards/scorecards.zip", 'rb') as file:  
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
    shutil.rmtree('/tmp/scorecards')

def main():
    job()
    send_zip_file()

if __name__ == "__main__":
    # Call the main function
    main()