#!/usr/bin/env python3

import aws_cdk as cdk

# This sample, non-production-ready template describes an CI/CD pipeline solution with security scans.  
# © 2022 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.  
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at  
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

from cdk.cdk_stack import AshPipline
from aws_cdk import App, Aspects



app = cdk.App()
AshPipline(app, "cdk")

app.synth()
