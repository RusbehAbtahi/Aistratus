#!/usr/bin/env python3
"""
terraform_state_report.py

Creates **terraform_resources.md** in the same folder.

* 100 % standalone – no CLI args, bucket/key are hard-wired
* Produces:
    1. Inventory tables (Compute, API GW, Networking, Cognito, SSM, IAM, CW)
    2. Dependency Map + Mermaid diagram
"""

import json
import os
from datetime import datetime
from collections import defaultdict

import boto3

# ────────────────────────────────────────────────────────────────────────────
# Hard-wired Terraform state location
# ────────────────────────────────────────────────────────────────────────────
STATE_BUCKET = "tinnyllama-terraform-state"
STATE_KEY    = "global/terraform.tfstate"

# Output markdown
MD_FILE = os.path.join(os.path.dirname(__file__), "terraform_resources.md")


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────
def fetch_state(bucket: str, key: str) -> dict:
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())


def assume_principals(inst: dict) -> str:
    policy = json.loads(inst["attributes"]["assume_role_policy"])
    stmt   = policy["Statement"][0]["Principal"]
    # Check for common principal keys
    for key in ("Service","Federated","AWS"):
        if key in stmt:
            val = stmt[key]
            if isinstance(val, list):
                return ", ".join(val)
            else:
                return val
    return "N/A"



def collect_edges(state: dict) -> list[str]:
    edges = []
    # map Lambda ARN -> name
    fn_by_arn = {
        i["attributes"]["arn"]: i["attributes"]["function_name"]
        for r in state["resources"] if r["type"] == "aws_lambda_function"
        for i in r["instances"]
    }
    # API → Lambda
    for r in state["resources"]:
        if r["type"] == "aws_apigatewayv2_integration":
            attr = r["instances"][0]["attributes"]
            api = attr.get("api_id") or attr.get("api_gateway_id")
            uri = attr["integration_uri"]
            # extract function ARN suffix
            fn_arn = uri.split("/functions/")[1].split("/invocations")[0]
            fn = fn_by_arn.get(fn_arn, fn_arn[-12:])
            edges.append(f"API {api} → Lambda {fn}")
    # Subnet → VPC
    vpc_id = next(
        (i["attributes"]["id"]
         for r in state["resources"] if r["type"] == "aws_vpc"
         for i in r["instances"]),
        None
    )
    if vpc_id:
        for r in state["resources"]:
            if r["type"] == "aws_subnet":
                sid = r["instances"][0]["attributes"]["id"]
                edges.append(f"Subnet {sid} → VPC {vpc_id}")
    return edges


def dedupe_ssm(rows):
    seen, out = set(), []
    for row in rows:
        if row not in seen:
            seen.add(row)
            out.append(row)
    return out


# ────────────────────────────────────────────────────────────────────────────
# Markdown sections
# ────────────────────────────────────────────────────────────────────────────
def md_header(state):
    sts = boto3.client("sts").get_caller_identity()
    region = boto3.Session().region_name or "unknown"
    return [
        "# AWS · Terraform-managed Resources",
        "",
        f"*Generated: {datetime.utcnow().isoformat()}Z*",
        "",
        "## Account / Workspace",
        "",
        f"- **Account ID** → `{sts['Account']}`",
        f"- **Region** → `{region}`",
        "- **Workspace/Env** → `default`",
        "",
        "---",
        "",
    ]


def md_lambda(state):
    funcs, layers = [], []
    for r in state["resources"]:
        if r["type"] == "aws_lambda_function":
            a = r["instances"][0]["attributes"]
            funcs.append((
                a["function_name"], a["runtime"],
                a["handler"], a["memory_size"],
                a["timeout"], a["role"]
            ))
        if r["type"] == "aws_lambda_layer_version":
            a = r["instances"][0]["attributes"]
            layers.append((a["layer_name"], a["arn"]))
    lines = ["## Compute · AWS Lambda", ""]
    if funcs:
        lines.append(
            "| Name | Runtime | Handler | Mem(MB) | Timeout(s) | Role ARN |\n"
            "| --- | --- | --- | --- | --- | --- |"
        )
        lines += [f"| {' | '.join(map(str,f))} |" for f in funcs]
        lines.append("")
    if layers:
        lines.append("| Layer name | ARN |\n| --- | --- |")
        lines += [f"| {n} | {arn} |" for n,arn in layers]
        lines.append("")
    return lines


def md_apigw(state):
    lines = ["## API Gateway HTTP APIs", ""]
    for r in state["resources"]:
        if r["type"] == "aws_apigatewayv2_api":
            a = r["instances"][0]["attributes"]
            api_id = a.get("api_id") or a["id"]
            lines += [
                f"### HTTP API · {a['name']}",
                "",
                f"- **API ID** → `{api_id}`",
                f"- **Invoke URL** → `{a['api_endpoint']}`",
                ""
            ]
            # list routes
            routes = [
                x for x in state["resources"]
                if x["type"] == "aws_apigatewayv2_route"
                and x["instances"][0]["attributes"]["api_id"] == api_id
            ]
            for rt in routes:
                rk = rt["instances"][0]["attributes"]["route_key"]
                lines.append(f"  • **Route** `{rk}`")
            lines.append("")
    return lines


def md_network(state):
    lines = ["## Networking", ""]
    # VPC
    vpc = next((r for r in state["resources"] if r["type"]=="aws_vpc"), None)
    if vpc:
        a = vpc["instances"][0]["attributes"]
        lines += [
            f"- **VPC ID** → `{a['id']}`",
            f"- **CIDR** → `{a['cidr_block']}`",
            ""
        ]
    # Subnets
    subs = [
        i["attributes"]
        for r in state["resources"] if r["type"]=="aws_subnet"
        for i in r["instances"]
    ]
    if subs:
        lines.append("| Subnet ID | CIDR | AZ |\n| --- | --- | --- |")
        for s in subs:
            lines.append(f"| {s['id']} | {s['cidr_block']} | {s['availability_zone']} |")
        lines.append("")
    # IGW & RTs
    igw = next((r for r in state["resources"] if r["type"]=="aws_internet_gateway"), None)
    if igw:
        lines.append(f"- **Internet Gateway** → `{igw['instances'][0]['attributes']['id']}`")
    rts = [r for r in state["resources"] if r["type"]=="aws_route_table"]
    if rts:
        lines.append("| Route Table ID | Name |\n| --- | --- |")
        for rt in rts:
            a = rt["instances"][0]["attributes"]
            name = a.get("tags",{}).get("Name","")
            lines.append(f"| {a['id']} | {name} |")
    lines.append("")
    return lines


def md_cognito(state):
    lines = ["## Cognito", ""]
    for r in state["resources"]:
        if r["type"]=="aws_cognito_user_pool":
            a = r["instances"][0]["attributes"]
            lines += [
                f"### aws_cognito_user_pool.main",
                "",
                f"- **Id** → `{a['id']}`",
                f"- **Name** → `{a['name']}`",
                f"- **Endpoint** → `{a['endpoint']}`",
                ""
            ]
        if r["type"]=="aws_cognito_user_pool_client":
            a = r["instances"][0]["attributes"]
            lines += [
                f"### aws_cognito_user_pool_client.gui",
                "",
                f"- **Id** → `{a['id']}`",
                f"- **Name** → `{a['name']}`",
                ""
            ]
    return lines


def md_ssm(state):
    rows = [
        (r["type"]+"."+r["name"], i["attributes"]["name"])
        for r in state["resources"] if r["type"]=="aws_ssm_parameter"
        for i in r["instances"]
    ]
    rows = dedupe_ssm(rows)
    if not rows:
        return []
    lines = ["## SSM Parameters", "", "| Terraform addr | SSM Param |", "| --- | --- |"]
    lines += [f"| {a} | {p} |" for a,p in rows]
    lines.append("")
    return lines


def md_iam(state):
    lines = ["## IAM Roles", "", "| Role | Trusted by | Attached/Inline |", "| --- | --- | --- |"]
    for r in state["resources"]:
        if r["type"]=="aws_iam_role":
            inst = r["instances"][0]
            name = inst["attributes"]["name"]
            principals = assume_principals(inst)
            attached = sum(
                1 for x in state["resources"]
                if x["type"]=="aws_iam_role_policy_attachment"
                and x["instances"][0]["attributes"]["role"]==name
            )
            inline = sum(
                1 for x in state["resources"]
                if x["type"]=="aws_iam_role_policy"
                and x["instances"][0]["attributes"]["role"]==name
            )
            lines.append(f"| {name} | {principals} | {attached}/{inline} |")
    lines.append("")
    return lines


def md_cloudwatch(state):
    rows = []
    for r in state["resources"]:
        if r["type"] in ("aws_cloudwatch_log_group","aws_cloudwatch_metric_alarm"):
            inst = r["instances"][0]["attributes"]
            display = inst.get("name") or inst.get("log_group_name") or inst.get("alarm_name")
            rows.append((r["type"]+"."+r["name"], display))
    if not rows:
        return []
    lines = ["## Observability (CloudWatch)", "", "| Terraform addr | Name |", "| --- | --- |"]
    for addr, name in rows:
        lines.append(f"| {addr} | {name} |")
    lines.append("")
    return lines


def md_dependency_map(edges):
    if not edges:
        return []
    lines = ["## Dependency Map", ""]
    lines += [f"- {e}" for e in edges]
    lines.append("")
    lines.append("```mermaid\nflowchart TD")
    for e in edges:
        a,b = [p.strip() for p in e.split("→")]
        fa = a.replace(" ","_"); fb = b.replace(" ","_")
        lines.append(f"    {fa} --> {fb}")
    lines.append("```")
    lines.append("")
    return lines


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────
def main():
    state = fetch_state(STATE_BUCKET, STATE_KEY)
    edges = collect_edges(state)

    md = []
    md += md_header(state)
    md += md_lambda(state)
    md += md_apigw(state)
    md += md_network(state)
    md += md_cognito(state)
    md += md_ssm(state)
    md += md_iam(state)
    md += md_cloudwatch(state)
    md += md_dependency_map(edges)

    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"✅ Report written to {MD_FILE}")


if __name__ == "__main__":
    main()
