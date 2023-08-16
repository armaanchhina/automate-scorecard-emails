Scorecards Email Sender
This program processes driver scorecard data, generates HTML representations of the scorecards, zips the HTML files, and then sends them as an email attachment along with two CSV files to a predefined email address.

Dependencies:

pandas
os
logging
tempfile
dotenv
jinja2
datetime
smtplib
zipfile
shutil
email
