# Syntecxhub_EmailSenderBot
Email Sender Bot - Syntecxhub Python Internship Project 3
# Email Sender Bot
Syntecxhub Python Programming Internship - Project 3

## About This Project
This project automates sending personalized emails to multiple 
people using Python. Instead of sending emails one by one manually,
this bot reads a CSV file with names and emails, sends each person
a personalized email, retries if sending fails, and saves a full
report of every send.

## Features
- Read recipients from CSV file
- Send personalized emails using name placeholder
- Attach files like PDF or Excel if needed
- Retry logic - tries 3 times if email fails
- Secure Gmail SMTP using App Password
- TLS encryption for safe connection
- Full logging to file and console
- JSON report saved after every run
- Protects credentials using .env file

## Project Structure
EmailSenderBot/
├── email_sender.py     - Main Python script
├── recipients.csv      - List of people to email
├── .env                - Gmail credentials (never uploaded)
├── .env.example        - Template for credentials
├── requirements.txt    - Required Python packages
├── .gitignore          - Keeps .env safe from GitHub
├── README.md           - Project documentation
└── logs/               - Auto created log files

## Technologies Used
- Python 3.14
- smtplib - Built in Python library to send emails
- email.mime - Builds HTML emails with attachments
- csv - Reads recipient list from CSV file
- logging - Logs all activity to file and console
- json - Saves structured send report
- python-dotenv - Loads credentials from .env securely
- os and time - File handling and delays between sends

## Setup Instructions

Step 1 - Install required package:
pip install -r requirements.txt

Step 2 - Generate Gmail App Password:
1. Go to myaccount.google.com
2. Click Security
3. Enable 2-Step Verification
4. Search App Passwords
5. Type EmailBot and click Create
6. Copy the 16 character password

Step 3 - Create .env file:
SENDER_EMAIL=yourgmail@gmail.com
SENDER_PASSWORD=xxxx xxxx xxxx xxxx

Step 4 - Add your recipients in recipients.csv:
name,email
Person1,person1@gmail.com
Person2,person2@gmail.com

Step 5 - Run the bot:
python email_sender.py

## Sample Output
Loaded 4 valid recipients from recipients.csv
Authenticated successfully
[1/4] Sending to: Person1
Sent to person1@gmail.com (attempt 1/3)
Success : 4
Failed  : 0
Total   : 4
Email Sender Bot Done!

## How Retry Logic Works
- Attempt 1 - Tries to send email
- If fails - Waits 5 seconds
- Attempt 2 - Tries again
- If fails - Waits 5 seconds
- Attempt 3 - Final attempt
- If still fails - Marks as FAILED in report

## Security
- Gmail App Password used instead of real password
- Credentials stored in .env file on local machine only
- .env file added to .gitignore so never uploaded to GitHub
- TLS encryption used for all email connections

## Real World Uses
- Sending internship offer letters to candidates
- Distributing weekly reports with attachments
- Sending certificates after course completion
- Automated notifications and alerts
- Order confirmation emails

## Author
Name    : Ponagani Harshini
Program : Syntecxhub Python Programming Internship
Project : Project 3 - Email Sender Bot
