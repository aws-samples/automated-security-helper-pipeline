# This sample, non-production-ready template describes an CI/CD pipeline solution with security scans.  
# © 2022 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.  
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at  
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

from constructs import Construct
from cdk_nag import NagSuppressions
from aws_cdk import (
    Aws,
    Duration,
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
    aws_codepipeline as codepipeline,
    aws_codecommit as codecommit,
    aws_codebuild as codebuild,
    aws_codepipeline_actions as codepipeline_actions
)

class AshPipline(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Supressing Errors
        NagSuppressions.add_stack_suppressions(self, [{"id":"AwsSolutions-IAM5", "reason":"Policies that is being created by CFN"}])
        NagSuppressions.add_stack_suppressions(self, [{"id":"AwsSolutions-S1", "reason":"Not needed at this time"}])
        NagSuppressions.add_stack_suppressions(self, [{"id":"AwsSolutions-KMS5", "reason":"The bucket artifect is by default using KMS MANAGED"}])
        # Supressing Warnings
        NagSuppressions.add_stack_suppressions(self, [{"id":"AwsSolutions-CB3", "reason":"This is needed for ASH pipeline to run"}])
        
        # S3 Bucket which will be used to store the reports
        repo_name = self.node.try_get_context("repo_name")
        codebuild_project_name = self.node.try_get_context("codebuild_project_name")
        pipeline_name = self.node.try_get_context("pipeline_name")
        ash_reports_bucket = s3.Bucket(self, "ash_reports_bucket", encryption=s3.BucketEncryption.KMS_MANAGED, block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True)
        ash_pipeline = codepipeline.Pipeline(self, pipeline_name)
        ash_source_repository = codecommit.Repository(self, repo_name,
            repository_name=repo_name
        )
        ash_codebuild_project = codebuild.Project(self, codebuild_project_name,
        environment=codebuild.BuildEnvironment(
            privileged=True,
            build_image=codebuild.LinuxBuildImage.AMAZON_LINUX_2_3
        ),
        build_spec=codebuild.BuildSpec.from_object({
        "version": 0.2,
        "phases": {
            "install": {
            "commands": [
                "echo Cloning ASH",
                "git clone https://github.com/aws-samples/automated-security-helper.git /tmp/ash"
            ]
            },
            "pre_build": {
            "commands": [
                "export codebuild_build_arn=${CODEBUILD_BUILD_ARN}",
                "export codecommit_commit_id=${CODEBUILD_RESOLVED_SOURCE_VERSION}",
                f"export s3_bucket={ash_reports_bucket.bucket_name}",
                "export codecommit_repo=${PWD##*/}",
                "export report_name=ash_report-$(date +%Y-%m-%d).txt",
                "export report_location=s3://\"${s3_bucket}\"/\"${codecommit_repo}\"/\"${codecommit_commit_id}\"/\"${report_name}\"",
                "date_iso=\"$(date -u +\"%Y-%m-%dT%H:%M:%SZ\")\"",
                "accountid=$(aws sts get-caller-identity --query \"Account\" --output text)",
                "printenv"
            ]
            },
            "build": {
            "commands": [
                "echo Running ASH...",
                "if /tmp/ash/ash --source-dir .; then echo scan completed; else echo found vulnerabilies && echo Sending alert to SecHub && scan_fail=1 ;fi"
            ]
            },
            "post_build": {
            "commands": [
                "echo Uploading report to ${report_location}",
                "aws s3 cp aggregated_results.txt $report_location",
                "sechub_finding='[\n    {\n        \"AwsAccountId\": \"'${accountid}'\",\n        \"CreatedAt\": \"'${date_iso}'\",\n        \"UpdatedAt\": \"'${date_iso}'\",\n        \"Description\": \"The Automated Security Helper scan failed for repository '${codecommit_repo}' , review the report\",\n        \"ProductArn\": \"arn:aws:securityhub:'${AWS_REGION}':'${accountid}':product/'${accountid}'/default\",\n        \"Remediation\": {\n            \"Recommendation\": {\n                \"Text\": \"Review the report at '${report_location}'\"\n            }\n        },\n        \"Resources\": [\n            {\n                \"Type\": \"CodeBuild\",\n                \"Id\": \"'${codebuild_build_arn}'\",\n                \"Partition\": \"aws\",\n                \"Region\": \"'${AWS_REGION}'\"\n            }\n        ],\n        \"FindingProviderFields\": {\n            \"Severity\": {\n                \"Label\": \"HIGH\"\n            },\n            \"Types\": [\n                \"IaC and software scan - ASH\"\n            ]\n        },\n        \"GeneratorId\": \"'${codebuild_build_arn}'\",\n        \"Id\": \"'${codecommit_commit_id}'\",\n        \"SchemaVersion\": \"2018-10-08\",\n        \"Title\": \"Automated Security Helper - Scan Failed for '${codecommit_repo}'\"\n    }\n]'\n",
                "echo \"$sechub_finding\"",
                "if [ \"$scan_fail\" -eq \"1\" ];then aws securityhub batch-import-findings --findings \"$sechub_finding\"; fi"
            ]
            }
        }
        }),
    )
        ash_reports_bucket.grant_put(ash_codebuild_project)
        ash_codebuild_project.role.add_to_policy(
            iam.PolicyStatement(
                resources=[f"arn:aws:securityhub:{Aws.REGION}:{Aws.ACCOUNT_ID}:product/*/*"],
                actions=["securityhub:BatchImportFindings"]
            )
        )
        source_output = codepipeline.Artifact()
        codepipeline_actions.CodeBuildAction(
            action_name=codebuild_project_name,
            project=ash_codebuild_project,
            input=source_output
        )
        source_stage = ash_pipeline.add_stage(stage_name="SourceRepository")
        source_stage.add_action(codepipeline_actions.CodeCommitSourceAction(
            branch="main",
            action_name="SourceRepository",
            output=source_output,
            repository=ash_source_repository
        ))
        destination_stage = ash_pipeline.add_stage(stage_name="ash_codebuild_project")
        destination_stage.add_action(codepipeline_actions.CodeBuildAction(
            action_name="ash_codebuild_project",
            project=ash_codebuild_project,
            input=source_output
        ))