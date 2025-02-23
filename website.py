from flask import flash, Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, Response
from functools import wraps
import webbrowser
import json
import os
from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from authlib.integrations.flask_client import OAuth 
import boto3 
from botocore.exceptions import ClientError
import mysql.connector
from botocore.config import Config
from spire.doc import *
from spire.doc.common import *
import tempfile
import mimetypes
import pandas as pd
from io import BytesIO
import traceback
#BEFORE EXECUTING THE CODE PLEASE DO "pip install -r requirements.txt" in your terminal and also if pandas is somewhat not installed, just do "pip install pandas" in your terminal.
#Database Credentials
host = "primary-database.cdou8g0ag1na.ap-southeast-1.rds.amazonaws.com"
port = 3306
database = "primarydatabase"
username = "admin"
password = "______________"

def connection_func():
    connection = mysql.connector.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    print("Connected to the database successfully!")
    return connection

#Testing if it can read
'''try:
    #Connect to the RDS instance
    connection = connection_func()
    cursor = connection.cursor()
    cursor.execute("SHOW TABLES;")
    for table in cursor.fetchall():
        print(table)

    cursor.close()
    connection.close()
except mysql.connector.Error as err:
    print(f"Error: {err}")'''

#AWS S3 Configurations
S3_BUCKET = "submissionsbucketfyp"
S3_REGION = "ap-southeast-1"
S3_FOLDER = "uploads"

S3_IMAGE_FOLDER = "images"
S3_SCHEDULE_FOLDER = "schedules"
S3_SLIDESHOW_FOLDER = "slideshow"

kms_key_id = 'arn:aws:kms:ap-southeast-1:794038236090:key/42702622-69d7-4c1b-be53-a6558f53595a'

#Initialize the S3 client
s3_client = boto3.client(
    's3',
    config=Config(signature_version='s3v4')
)

'''ses_client = boto3.client(
    'ses',
    region_name='ap-southeast-1',  #Change to the appropriate SES region
    aws_access_key_id='AKIA3RYC56O5J6KZDWFU',  #Replace with your AWS Access Key
    aws_secret_access_key='BAnrmj8QU0jWnb9mSxkxiWDiSVLEN7ruqRN9O2CR0ERb'  #Replace with your AWS Secret Key
)'''

#Initialize the Cognito client
cognito_client = boto3.client('cognito-idp')

#FUNCTIONS
#Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:  #Check if user is logged in
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

#Upload folder to S3
def upload_to_s3(file, filename, folder):
    try:
        s3_file_path = f"{folder}/{filename}"

        #Upload the file with KMS encryption
        s3_client.upload_fileobj(
            file,
            S3_BUCKET,
            s3_file_path,
            ExtraArgs={
                'ServerSideEncryption': 'aws:kms',
                'SSEKMSKeyId': kms_key_id
            }
        )

        return s3_file_path

    except Exception as e:
        print(f"Error: {e}")
        raise

#Delete existing folder in S3 (For resubmission)
def delete_from_s3(file_path):
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=file_path)
        print(f"Deleted old file: {file_path}")
    except Exception as e:
        print(f"Error deleting file: {e}")

#Load tables from database (submissions/islp)
def load_table(table):
    connection = connection_func()
    cursor = connection.cursor(dictionary=True)  #Use dictionary=True for dict results
    cursor.execute("SELECT * FROM " +table+ ";")
    table = cursor.fetchall()

    #Close the connection
    cursor.close()
    connection.close()

    return table

#Send email to the applicant
def send_email(recipient_email, subject, body):
    sender_email = "22023942@myrp.edu.sg"
    sender_password = "_______________________"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP('smtp.office365.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

#Send email using SES
'''def send_email_ses(recipient_email, subject, body):
    sender_email = "soi.islpnoreply@gmail.com"  #Your verified SES email address

    try:
        #Send the email through SES
        response = ses_client.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': [recipient_email],
            },
            Message={
                'Subject': {
                    'Data': subject,
                },
                'Body': {
                    'Text': {
                        'Data': body,
                    },
                },
            }
        )
        print(f"Email sent! Message ID: {response['MessageId']}")
    except ClientError as e:
        print(f"Error sending email: {e.response['Error']['Message']}")
'''

#Checking if it is a student/staff
def check_role(student_email, role_name):
    try:
        #Get the user's attributes from Cognito
        response = cognito_client.admin_list_groups_for_user(
            UserPoolId='ap-southeast-1_COvd8teW6',  #Replace with your Cognito User Pool ID
            Username=student_email
        )
        
        #Look for the group name in the user's group membership
        for group in response.get('Groups', []):
            if group['GroupName'] == role_name:
                return True
        
        #If group is not found, return False
        return False

    except ClientError as e:
        print(f"Error getting user from Cognito: {e}")
        return False


app = Flask(__name__)
#Use a secure random key in production
app.secret_key = os.urandom(24)
oauth = OAuth(app)

#Amazon Cognito
oauth.register(
  name='oidc',
  authority='https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_COvd8teW6',
  client_id='5beatj5fm3dfd30ldtm6g8418l',
  client_secret='10b7mttfmb9ap8e2p86gdtjjfn3b0gd3ec19ihmnie10k07n3975',
  server_metadata_url='https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_COvd8teW6/.well-known/openid-configuration',
  client_kwargs={'scope': 'email openid phone'}
)

#Main Page
@app.route('/')
def base():
    user = session.get('user')
    connection = connection_func()
    cursor = connection.cursor(dictionary=True)

    try:
        #Fetch all ISLP data
        cursor.execute("SELECT * FROM islpdata")
        islps = cursor.fetchall()

        present_islps = []
        past_islps = []

        for islp in islps:
            #Format deadline date
            if islp.get('deadline'):
                deadline_date = islp['deadline']
                islp['formatted_deadline'] = deadline_date.strftime('%d %B %Y')
                islp['is_registration_open'] = deadline_date >= date.today()

            #Fetch trip dates
            cursor.execute("SELECT trip_date FROM tripdates WHERE ISLP = %s ORDER BY trip_date", (islp['ISLP'],))
            trip_dates = [row['trip_date'] for row in cursor.fetchall()]

            if trip_dates:
                last_trip_date = trip_dates[-1]  #Get the latest trip date
                
                #Format trip dates
                if len(trip_dates) == 1:
                    formatted_trip_dates = trip_dates[0].strftime('%d %B %Y')
                else:
                    consecutive = all(
                        (trip_dates[i + 1] - trip_dates[i]).days == 1 for i in range(len(trip_dates) - 1)
                    )
                    if consecutive:
                        start_date, end_date = trip_dates[0], trip_dates[-1]
                        if start_date.month == end_date.month:
                            formatted_trip_dates = f"{start_date.day} - {end_date.day} {start_date.strftime('%B %Y')}"
                        else:
                            formatted_trip_dates = f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}"
                    else:
                        formatted_trip_dates = ', '.join(date.strftime('%d %B %Y') for date in trip_dates)

                islp['formatted_trip_dates'] = formatted_trip_dates

                #Categorize into Present or Past
                if last_trip_date >= date.today():
                    present_islps.append(islp)
                else:
                    past_islps.append(islp)
            else:
                present_islps.append(islp)

            #Check if user is approved
            if user:
                email = user['email']
                cursor.execute("SELECT status FROM submissions WHERE email = %s AND ISLP = %s", (email, islp['ISLP']))
                result = cursor.fetchone()
                islp['is_user_approved'] = result and result['status'] == 'Approved'
            else:
                islp['is_user_approved'] = False

        #Fetch slideshow images from S3
        slideshow_images = []
        try:
            response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix='slideshow/')
            if 'Contents' in response:
                slideshow_images = [obj['Key'] for obj in response['Contents'] if obj['Key'] != 'slideshow/']
        except Exception as e:
            print(f"Error fetching slideshow images: {e}")

    finally:
        cursor.close()
        connection.close()

    if user:
        email = user['email']
        if email.endswith('@rp.edu.sg'):
            return redirect(url_for('staff'))
        else:
            return render_template('public.html', user=user, present_islps=present_islps, past_islps=past_islps, user_email=email, slideshow_images=slideshow_images)
    else:
        return render_template('public.html', present_islps=present_islps, past_islps=past_islps, user=None, user_email="", slideshow_images=slideshow_images)
    
#Display images in main page
@app.route('/get-image/')
def get_image():
    image_key = request.args.get('filename')
    if not image_key:
        return "Filename parameter is required", 400
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=image_key)
        image_content = response['Body'].read()

        mime_type, _ = mimetypes.guess_type(image_key)
        mime_type = mime_type or 'application/octet-stream'

        return Response(image_content, content_type=mime_type)
    
    except Exception as e:
        return str(e), 404

#Login for staff and users
@app.route('/login')
def login():
    #Redirect to OAuth authorization endpoint (Cognito)
    return oauth.oidc.authorize_redirect("https://127.0.0.1:5000/authorize")

@app.route('/authorize')
def authorize():
    #Fetch the token after redirect
    token = oauth.oidc.authorize_access_token()
    user = token['userinfo']

    session['user'] = user
    
    #Redirect to the base route (public.html)
    return redirect(url_for('base'))

@app.route('/logout')
def logout():
    #Clear the local session
    session.pop('user', None)

    #Construct Cognito logout URL
    cognito_logout_url = (
        "https://ap-southeast-1covd8tew6.auth.ap-southeast-1.amazoncognito.com/logout?"
        "client_id=5beatj5fm3dfd30ldtm6g8418l&"
        "logout_uri=https://127.0.0.1:5000/"
    )
    #Redirect to Cognito logout
    return redirect(cognito_logout_url)

#ISLP details
@app.route('/learnmore')
@login_required
def learnmore():
    islp_name = request.args.get('islp')
    user_email = session.get('user', {}).get('email', '')
    connection = connection_func()
    cursor = connection.cursor(dictionary=True)

    try:
        #Check if the student is approved for this ISLP
        cursor.execute("SELECT status FROM submissions WHERE email = %s AND ISLP = %s", (user_email, islp_name))
        submission_status = cursor.fetchone()

        if not submission_status or submission_status['status'] != 'Approved':
            return "You are not approved for this ISLP trip", 403

        #Fetch the ISLP details
        cursor.execute("SELECT more_details, schedule_file FROM islpdata WHERE ISLP = %s", (islp_name,))
        islp_data = cursor.fetchone()

        if not islp_data:
            return "ISLP not found", 404

        #Fetch the schedule file from S3
        schedule_path = islp_data['schedule_file']
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=schedule_path)
        schedule_content = response['Body'].read()

        #Parse the Excel file
        excel_data = pd.read_excel(BytesIO(schedule_content))
        #Replace '\n' with '<br>' in all columns and rows
        excel_data = excel_data.applymap(
            lambda x: x.replace('\n', '<br>') if isinstance(x, str) else x
        )
        #Convert to HTML table
        schedule_table = excel_data.to_html(index=False, classes='table table-bordered', escape=False)

    finally:
        cursor.close()
        connection.close()

    return render_template(
        'learnmore.html', more_details=islp_data['more_details'], schedule_table=schedule_table, islp_name=islp_name)



#Form for ISLP
@app.route('/form', methods=['GET'])
@login_required
def form():
    user_email = session.get('user', {}).get('email', '')
    islp = request.args.get('islp')

    connection = connection_func()
    cursor = connection.cursor(dictionary=True)

    #Check if a submission exists for the user and ISLP
    cursor.execute(
        "SELECT * FROM submissions WHERE email = %s AND ISLP = %s",
        (user_email, islp)
    )
    submission = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template('form.html', user_email=user_email, islp=islp, submission=submission)

#Upload the folder and save in mySQL
@app.route('/upload', methods=['POST'])
@login_required
def upload():
    user_email = session.get('user', {}).get('email', '')
    islp = request.form.get('islp')
    form_data = request.form
    file = request.files.get('testimonials')

    connection = connection_func()
    cursor = connection.cursor(dictionary=True)

    try:
        #Check if a submission already exists
        cursor.execute(
            "SELECT * FROM submissions WHERE email = %s AND ISLP = %s",
            (user_email, islp)
        )
        submission = cursor.fetchone()

        #Handle file upload
        file_path = submission['file_path'] if submission else None
        file_name = submission['file_name'] if submission else None

        if file and file.filename:
            #Delete old file if it exists
            if file_path:
                delete_from_s3(file_path)

            #Upload new file
            file_path = upload_to_s3(file, file.filename, S3_FOLDER)
            file_name = file.filename

        if submission:
            #Update existing submission
            cursor.execute(
                """
                UPDATE submissions
                SET name = %s, diploma = %s, interest = %s, file_path = %s, file_name = %s, personal_email = %s
                WHERE email = %s AND ISLP = %s 
                """,
                (
                    form_data['name'],
                    form_data['diploma'],
                    form_data.get('interest', ''),
                    file_path,
                    file_name,
                    form_data['personalemail'],
                    user_email,
                    islp
                )
            )

            body = f"""
            Dear {form_data['name']},

            You have successfully updated your submission. Here are the details we received:
            \t- Name: {form_data['name']}
            \t- Email: {user_email}
            \t- Personal Email: {form_data['personalemail']}
            \t- Diploma: {form_data['diploma']}
            \t- Interest: {form_data.get('interest', '')}
            \t- ISLP: {islp}

            Your uploaded file: {file.filename}

            Best regards,
            Republic Polytechnic
            """

            send_email(form_data['personalemail'], "Updated Submission Confirmation", body)


        else:
            #Create a new submission
            cursor.execute(
                """
                INSERT INTO submissions (name, email, diploma, interest, ISLP, status, file_path, file_name, personal_email)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    form_data['name'],
                    user_email,
                    form_data['diploma'],
                    form_data.get('interest', ''),
                    islp,
                    'Pending',
                    file_path,
                    file_name,
                    form_data['personalemail']
                )
            )

            body = f"""
            Dear {form_data['name']},

            Thank you for your submission! Here are the details we received:
            \t- Name: {form_data['name']}
            \t- Email: {user_email}
            \t- Personal Email: {form_data['personalemail']}
            \t- Diploma: {form_data['diploma']}
            \t- Interest: {form_data.get('interest', '')}
            \t- ISLP: {islp}

            Your uploaded file: {file.filename}

            Best regards,
            Republic Polytechnic
            """

            send_email(form_data['personalemail'], "Submission Confirmation", body)

        connection.commit()
        return redirect(url_for('form', islp=islp))

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connection.close()

@app.route('/staff', methods=['GET', 'POST'])
@login_required
def staff():
    user = session.get('user')
    user_email = user['email']

    if user_email.endswith('@rp.edu.sg'):
        connection = connection_func()
        cursor = connection.cursor(dictionary=True)

        try:
            #Fetch ISLP names and submission counts
            cursor.execute("""
                SELECT i.ISLP, COUNT(s.ISLP) AS submission_count
                FROM islpdata i
                LEFT JOIN submissions s ON i.ISLP = s.ISLP
                GROUP BY i.ISLP
            """)
            islps = cursor.fetchall()

        finally:
            cursor.close()
            connection.close()

        return render_template('staff.html', islps=islps, user_email=user_email)
    else:
        return redirect(url_for('base'))


#View all submissions
@app.route('/submissions')
@login_required
def view_submissions():
    user = session.get('user')
    user_email = user['email']

    if user_email.endswith('@rp.edu.sg'):
        submissions = json.dumps(load_table("submissions"), indent=4)
        return jsonify(submissions)

#View a certain ISLP
@app.route('/submissions/<islp>')
@login_required
def view_submissions_by_islp(islp):
    user = session.get('user')
    user_email = user['email']

    if user_email.endswith('@rp.edu.sg'):
        connection = connection_func()
        cursor = connection.cursor(dictionary=True)

        try:
            #Fetch ISLP details
            cursor.execute("SELECT * FROM islpdata WHERE ISLP = %s", (islp,))
            islp_details = cursor.fetchone()

            if not islp_details:
                return jsonify({"error": "ISLP not found"}), 404

            #Fetch trip dates
            cursor.execute("SELECT trip_date FROM tripdates WHERE ISLP = %s", (islp,))
            trip_dates = [row['trip_date'].strftime('%Y-%m-%d') for row in cursor.fetchall()]
            islp_details['trip_dates'] = trip_dates

            #Generate S3 URLs for photo and schedule file
            islp_details['photo_url'] = s3_client.generate_presigned_url(
                'get_object', Params={'Bucket': S3_BUCKET, 'Key': islp_details['photo_file']}, ExpiresIn=3600
            )
            islp_details['schedule_url'] = s3_client.generate_presigned_url(
                'get_object', Params={'Bucket': S3_BUCKET, 'Key': islp_details['schedule_file']}, ExpiresIn=3600
            )

            #Fetch submissions related to this ISLP
            cursor.execute("SELECT * FROM submissions WHERE ISLP = %s", (islp,))
            submissions = cursor.fetchall()

            #Include submissions in the response
            islp_details['submissions'] = submissions

            return jsonify(islp_details)

        finally:
            cursor.close()
            connection.close()



#View document
@app.route('/submissions/document')
@login_required
def view_document():
    filename = request.args.get('filename')
    user = session.get('user')
    user_email = user['email']

    if not user_email:
        return jsonify({"error": "Unauthorized access. Please log in."}), 401

    connection = connection_func()
    cursor = connection.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT file_path, email
            FROM submissions 
            WHERE file_name = %s
        """, (filename,))
        result = cursor.fetchone()  #Ensure you fetch the result before closing the cursor

        if not result:
            return "Document not found", 404

        #Check access rights
        if not check_role(user_email, "staff") and result['email'] != user_email:
            return jsonify({"error": "You are not authorized to access this document."}), 403

        #Fetch the document from S3
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=result['file_path'])
        document = Document()
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(response['Body'].read())
            tmp_file_path = tmp_file.name
        document.LoadFromFile(tmp_file_path)

        #Convert to PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf_file:
            tmp_pdf_file.close()
            document.SaveToFile(tmp_pdf_file.name, FileFormat.PDF)
            with open(tmp_pdf_file.name, 'rb') as pdf_file:
                pdf_content = pdf_file.read()

        return Response(pdf_content, content_type='application/pdf')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connection.close()













#To let them approve or decline
@app.route('/submissions/action', methods=['POST'])
@login_required
def handle_submission_action():
    user = session.get('user')
    user_email = user['email']

    if user_email.endswith('@rp.edu.sg'):
        data = request.get_json()
        email = data['email']
        action = data['action']
        islp = data['islp']
        personal_email = data['personal_email']

        #Load submissions and find the target submission
        connection = connection_func()
        cursor = connection.cursor(dictionary=True)

        #Fetch the submission from the database
        cursor.execute("SELECT * FROM submissions WHERE email = %s AND ISLP = %s;", (email, islp))
        submission = cursor.fetchone()

        if not submission:
            cursor.close()
            connection.close()
            return jsonify({"error": "Submission not found"}), 404

        #Update the status of the submission based on the action
        if action == 'approve':
            new_status = 'Approved'
            send_email(
                personal_email,
                "You have been selected!",
                f"Dear {submission['name']},\n\nCongratulations! You have been selected for the ISLP: {islp}.\n\nBest regards,\nRepublic Polytechnic"
            )
        elif action == 'decline':
            new_status = 'Declined'
            send_email(
                personal_email,
                "Thank you for your application",
                f"Dear {submission['name']},\n\nWe regret to inform you that you have not been selected for the ISLP: {islp}. "
                "We truly appreciate your interest and encourage you to apply again in the future.\n\nBest regards,\nRepublic Polytechnic"
            )
        else:
            cursor.close()
            connection.close()
            return jsonify({"error": "Invalid action"}), 400

        #Update the submission's status in the database
        cursor.execute("UPDATE submissions SET status = %s WHERE email = %s AND ISLP = %s;", (new_status, email, islp))
        connection.commit()

        #Close the connection
        cursor.close()
        connection.close()

        return jsonify({"success": True})

@app.route('/createislp', methods=['GET', 'POST'])
@login_required
def createislp():
    user = session.get('user')
    user_email = user['email']

    if user_email.endswith('@rp.edu.sg'):
        if request.method == 'POST':
            islp = request.form['islp']
            deadline = request.form['deadline']
            public_information = request.form['public_information']
            schedule_file = request.files['schedule_file']
            more_details = request.form['more_details']
            photo_file = request.files['photo_file']
            trip_dates = request.form.getlist('trip_dates')  #Get list of trip dates

            #Save files to a location (e.g., S3 or local folder)
            schedule_path = upload_to_s3(schedule_file, schedule_file.filename, S3_SCHEDULE_FOLDER)
            photo_path = upload_to_s3(photo_file, photo_file.filename, S3_IMAGE_FOLDER)

            #Save ISLP data to the database
            connection = connection_func()
            cursor = connection.cursor()
            try:
                cursor.execute("""
                    INSERT INTO islpdata (ISLP, deadline, public_information, schedule_file, more_details, photo_file)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (islp, deadline, public_information, schedule_path, more_details, photo_path))

                #Save trip dates to the database
                for trip_date in trip_dates:
                    cursor.execute("""
                        INSERT INTO tripdates (ISLP, trip_date)
                        VALUES (%s, %s)
                    """, (islp, trip_date))

                connection.commit()
            finally:
                cursor.close()
                connection.close()

            flash("ISLP and trip dates created successfully!")
            return redirect(url_for('staff'))

@app.route('/update-details', methods=['POST'])
@login_required
def update_details():
    user = session.get('user')
    user_email = user['email']

    if user_email.endswith('@rp.edu.sg'):
        islp = request.form.get('islp') 
        details = request.form.get('details')
        more_details = request.form.get('more_details')
        photo_file = request.files.get('photo')
        schedule_file = request.files.get('schedule')

        
        try:
            trip_dates = json.loads(request.form.get('trip_dates', '[]'))
            trip_dates = [date for date in trip_dates if date.strip()]  #Remove empty values
        except json.JSONDecodeError as e:
            return jsonify({"error": f"Invalid trip_dates format: {e}"}), 400

        connection = connection_func()
        cursor = connection.cursor(dictionary=True)  #Enable dictionary mode

        try:
            cursor.execute("SELECT photo_file FROM islpdata WHERE ISLP = %s", (islp,))
            existing_data1 = cursor.fetchone()

            if existing_data1:
                existing_photo_file = existing_data1["photo_file"]
            else:
                existing_photo_file = None

            cursor.execute("SELECT schedule_file FROM islpdata WHERE ISLP = %s", (islp,))
            existing_data2 = cursor.fetchone()

            if existing_data2:
                existing_schedule_path = existing_data2["schedule_file"]
            else:
                existing_schedule_path = None

            #Update ISLP public information and more details
            cursor.execute(
                "UPDATE islpdata SET public_information = %s, more_details = %s WHERE ISLP = %s",
                (details, more_details, islp)
            )

            
            cursor.execute("DELETE FROM tripdates WHERE ISLP = %s", (islp,))
            for trip_date in trip_dates:
                cursor.execute(
                    "INSERT INTO tripdates (ISLP, trip_date) VALUES (%s, %s)",
                    (islp, trip_date)
                )
                
            
            if photo_file and photo_file.filename:
                if existing_photo_file:
                    delete_from_s3(existing_photo_file)

                photo_path = upload_to_s3(photo_file, photo_file.filename, S3_IMAGE_FOLDER)
                cursor.execute(
                    "UPDATE islpdata SET photo_file = %s WHERE ISLP = %s",
                    (photo_path, islp)
                )


            if schedule_file and schedule_file.filename:
                if existing_schedule_path:
                    delete_from_s3(existing_schedule_path)

                schedule_path = upload_to_s3(schedule_file, schedule_file.filename, S3_SCHEDULE_FOLDER)
                cursor.execute(
                    "UPDATE islpdata SET schedule_file = %s WHERE ISLP = %s",
                    (schedule_path, islp)
                )

            connection.commit()
            return jsonify({"success": True}), 200

        except Exception as e:
            connection.rollback()
            print("Error occurred:", str(e)) 
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

        finally:
            cursor.close()
            connection.close()


@app.route('/TestHeavyLoad') 
def TestHeavyLoad(): 
    while True: 
        print('Load') 
        return 'HeavyLoad' 
 
@app.route('/Healthcheck') 
def Healthcheck(): 
    return 'HealthChecked'

def open_webbrowser():
    webbrowser.open_new('https://127.0.0.1:5000')

if __name__ == '__main__':
    open_webbrowser()
    app.run(ssl_context=('cert.pem', 'key.pem'), debug=True)
