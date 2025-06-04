#!/usr/bin/env bash
set -euo pipefail

ROLE_NAME_BUILD="Aistratus-CodeBuildRole"
ROLE_NAME_PIPELINE="Aistratus-CodePipelineRole"
POLICY_BUILD="arn:aws:iam::aws:policy/AWSCodeBuildDeveloperAccess"
POLICY_PIPELINE_CP="arn:aws:iam::aws:policy/AWSCodePipeline_FullAccess"
POLICY_PIPELINE_CB="arn:aws:iam::aws:policy/AWSCodeBuildDeveloperAccess"

#--------------------------------------------------
# CodeBuild service role
#--------------------------------------------------
if aws iam get-role --role-name "$ROLE_NAME_BUILD" >/dev/null 2>&1; then
    echo "Role $ROLE_NAME_BUILD already exists, skipping creation."
else
    aws iam create-role \
        --role-name "$ROLE_NAME_BUILD" \
        --assume-role-policy-document file://00_infra/codebuild_trust_policy.json
    echo "Created role $ROLE_NAME_BUILD."
fi

if aws iam list-attached-role-policies --role-name "$ROLE_NAME_BUILD" \
     --query "AttachedPolicies[?PolicyArn=='$POLICY_BUILD']" --output text | grep -q "$POLICY_BUILD"; then
    echo "Policy $POLICY_BUILD already attached to $ROLE_NAME_BUILD."
else
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME_BUILD" \
        --policy-arn "$POLICY_BUILD"
    echo "Attached policy $POLICY_BUILD to $ROLE_NAME_BUILD."
fi

#--------------------------------------------------
# CodePipeline service role
#--------------------------------------------------
if aws iam get-role --role-name "$ROLE_NAME_PIPELINE" >/dev/null 2>&1; then
    echo "Role $ROLE_NAME_PIPELINE already exists, skipping creation."
else
    aws iam create-role \
        --role-name "$ROLE_NAME_PIPELINE" \
        --assume-role-policy-document file://00_infra/codepipeline_trust_policy.json
    echo "Created role $ROLE_NAME_PIPELINE."
fi

if aws iam list-attached-role-policies --role-name "$ROLE_NAME_PIPELINE" \
     --query "AttachedPolicies[?PolicyArn=='$POLICY_PIPELINE_CP']" --output text | grep -q "$POLICY_PIPELINE_CP"; then
    echo "Policy $POLICY_PIPELINE_CP already attached to $ROLE_NAME_PIPELINE."
else
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME_PIPELINE" \
        --policy-arn "$POLICY_PIPELINE_CP"
    echo "Attached policy $POLICY_PIPELINE_CP to $ROLE_NAME_PIPELINE."
fi

if aws iam list-attached-role-policies --role-name "$ROLE_NAME_PIPELINE" \
     --query "AttachedPolicies[?PolicyArn=='$POLICY_PIPELINE_CB']" --output text | grep -q "$POLICY_PIPELINE_CB"; then
    echo "Policy $POLICY_PIPELINE_CB already attached to $ROLE_NAME_PIPELINE."
else
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME_PIPELINE" \
        --policy-arn "$POLICY_PIPELINE_CB"
    echo "Attached policy $POLICY_PIPELINE_CB to $ROLE_NAME_PIPELINE."
fi
