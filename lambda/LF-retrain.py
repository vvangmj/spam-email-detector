#references: https://towardsdatascience.com/automating-aws-sagemaker-notebooks-2dec62bc2c84
import json
import boto3, os, datetime
import time

sagemakerClient = boto3.client('sagemaker')

def lambda_handler(event, context):
    # TODO implement
    notebooks = sagemakerClient.describe_notebook_instance(NotebookInstanceName='6998-hw3-notebook-instance')
    if notebooks["NotebookInstanceStatus"] == "InService":
        sagemakerClient.stop_notebook_instance(NotebookInstanceName='6998-hw3-notebook-instance')
    while True:
        notebooks = sagemakerClient.describe_notebook_instance(NotebookInstanceName='6998-hw3-notebook-instance')
        if notebooks["NotebookInstanceStatus"] == "Stopped":
            break
        time.sleep(10)
    sagemakerClient.start_notebook_instance(NotebookInstanceName='6998-hw3-notebook-instance')
    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
