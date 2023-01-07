import json
import boto3
import mailparser
import os
from datetime import datetime
from datetime import timedelta
from botocore.exceptions import ClientError
from io import StringIO
from sms_spam_classifier_utilities import one_hot_encode
from sms_spam_classifier_utilities import vectorize_sequences

ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
SENDER = "Spam Detector <"+os.environ['SENDER']+">"
AWS_REGION = "us-east-1"

vocabulary_length = 9013
sageClient= boto3.client('sagemaker-runtime')
sageAdminClient= boto3.client('sagemaker')
s3Client = boto3.client('s3')

def get_emailbody(key, bucket):
    try:
        response = s3Client.get_object(Bucket=bucket, Key=key)
        contents = response['Body'].read()
        print("s3response: ", contents)
        mail = mailparser.parse_from_bytes(contents)
        mailtext_list = mail.text_plain
        for i in range(len(mailtext_list)):
            mailtext_list[i] = mailtext_list[i].replace('\r\n',' ')
        return mailtext_list, mail
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e

def reply_email(ori_mail, CLASSIFICATION, CONFIDENCE_SCORE):
    SUBJECT = "Email Detection Results"
    RECIPIENT = ori_mail.from_[0][1]
    print("mail_sendto: ", RECIPIENT)
    print("mail_date: ",ori_mail.date)
    MAIL_BODY = ori_mail.text_plain[0]
    if len(MAIL_BODY) > 240:
        MAIL_BODY = MAIL_BODY[:240]
    MAIL_LEN = len(MAIL_BODY)
    # mail_time_ori = datetime.strptime(ori_mail.date, '%y-%m-%d %H:%M:%S') #2022-12-08 03:22:10
    MAIL_TIME = ori_mail.date - timedelta(hours=5)
    BODY_TEXT = (f"We received your email sent at {MAIL_TIME.strftime('%y-%m-%d %H:%M:%S')} with the subject \" {ori_mail.subject}\". \r\n"
             f"Here is a {MAIL_LEN} character sample of the email body: \r\n"
             f"{MAIL_BODY}\r\n"
             "\r\n"
             f"The email was categorized as {CLASSIFICATION} with a {CONFIDENCE_SCORE}% conﬁdence."
            )
    CHARSET = "UTF-8"
    sesClient = boto3.client('ses',region_name=AWS_REGION)
    # Try to send the email.
    try:
        #Provide the contents of the email.
        response = sesClient.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])
       
def proceed_result(detect_rst):
    prob = detect_rst["predicted_probability"][0][0]
    label = detect_rst["predicted_label"][0][0]
    CLASSIFICATION = "SPAM"
    CONFIDENCE_SCORE = prob*100
    if label == 0:
        CLASSIFICATION = "HAM"
        CONFIDENCE_SCORE = 100 - CONFIDENCE_SCORE
        
    return CLASSIFICATION, CONFIDENCE_SCORE

def get_endpoint():
    endpoints = sageAdminClient.list_endpoints(
                    SortBy='CreationTime',
                    SortOrder='Descending',
                    NameContains='sms-spam-classifier-mxnet',
                    StatusEquals='InService'
                )
    
    latest_endpoint = endpoints["Endpoints"][0]["EndpointName"]
    
    # print("latest_endpoint:", latest_endpoint)
    return latest_endpoint
    

def lambda_handler(event, context):
    # TODO implement
    print("event:", event)

    email_filename = event["Records"][0]["s3"]["object"]["key"]
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    print("email_filename:", email_filename)
    email_body, mail = get_emailbody(email_filename, bucket_name)
    print("email_body: \n")
    print(email_body)
    
    # check with spam model
    one_hot_test_messages = one_hot_encode(email_body, vocabulary_length)
    encoded_test_messages = vectorize_sequences(one_hot_test_messages, vocabulary_length)
    io = StringIO()
    json.dump(encoded_test_messages.tolist(), io)
    body = bytes(io.getvalue(), 'utf-8')
    
    
    latest_endpoint = ENDPOINT_NAME
    
    try:
        sageAdminClient.describe_endpoint(EndpointName=latest_endpoint)
    except ClientError:
        latest_endpoint = get_endpoint()
    
    print("latest_endpoint: ", latest_endpoint)
    response = sageClient.invoke_endpoint(
        EndpointName=latest_endpoint, 
        Body=body
    )
    
    resp = response['Body'].read().decode('utf-8')
    print(resp)
    resp_json = json.loads(resp)
    CLASSIFICATION, CONFIDENCE_SCORE = proceed_result(resp_json)
    

    reply_email(mail, CLASSIFICATION, CONFIDENCE_SCORE)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
