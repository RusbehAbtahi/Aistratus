# tinyllama_architecture_intermediate.py
#
# Generates tinyllama_architecture_intermediate.{png,svg}
# Architecture covers RQL 1 – Intermediate stage with EPIC labels.
# Run: python tinyllama_architecture_intermediate.py

from diagrams import Diagram, Cluster, Edge, Node
from diagrams.onprem.client import User
from diagrams.aws.network import APIGateway, CloudFront, NATGateway
from diagrams.aws.security import Cognito, SecretsManager, KMS
from diagrams.aws.compute import Lambda, EC2, EC2ImageBuilder
from diagrams.aws.database import Elasticache
from diagrams.aws.storage import S3, EBS
from diagrams.aws.management import SystemsManager, Cloudwatch
from diagrams.aws.devtools import Codepipeline, Codebuild
from diagrams.aws.cost import Budgets
from diagrams.generic.blank import Blank

# Styling
graph_attr = {
    "fontsize": "18", "splines": "ortho", "penwidth": "2",
    "ranksep": "0.7", "nodesep": "0.8", "ratio": "1.7",
    "size": "14,8.3!", "pad": "0.3,0.3", "dpi": "300",
}
edge_attr = {"fontsize": "12", "penwidth": "2", "color": "#333333"}

for fmt in ("png", "svg"):
    with Diagram(
        "tinyllama_architecture_intermediate",
        filename="tinyllama_architecture_intermediate",
        outformat=fmt,
        direction="LR",
        graph_attr=graph_attr,
        edge_attr=edge_attr,
        show=False,
    ):
        # EPIC: GUI
        desktop = User("Desktop GUI\n[EPIC: GUI]")

        # EPIC: API
        with Cluster("Edge / API\n[EPIC: API]", graph_attr={"rank": "same"}):
            cf      = CloudFront("CloudFront\n(optional)")
            api_gw  = APIGateway("API Gateway\nHTTP API")
            cognito = Cognito("Cognito JWT")

        desktop >> Edge(label="HTTPS") >> cf >> api_gw
        desktop >> Edge(style="dotted", label="OAuth flow") >> cognito
        cognito >> Edge(style="dotted", label="Authorizer") >> api_gw

        # EPIC: Lambda
        lambda_router = Lambda("Lambda Router v2\n[EPIC: Lambda]")
        api_gw >> lambda_router

        # EPIC: Queue
        redis = Elasticache("ElastiCache Redis\n(job TTL 5m)\n[EPIC: Queue]")
        lambda_router >> Edge(label="Enqueue") >> redis

        # EPIC: EC2
        with Cluster("VPC Private\n[EPIC: EC2]"):
            gpu = EC2("EC2 g4dn.xlarge\n(vLLM)\n[EPIC: EC2]")
            ebs_cache = EBS("100 GiB gp3 cache")
            redis >> Edge(label="Dequeue / wake") >> gpu
            gpu >> Edge(style="dotted", label="Stop/Start") >> ebs_cache

            nat = NATGateway("NAT GW")
            gpu >> Edge(style="dotted", label="HTTPS egress") >> nat

            s3_models = S3("S3 tinyllama-models")
            nat >> s3_models

            kms = KMS("KMS CMK")
            s3_models >> Edge(style="dotted", label="Encrypt") >> kms
            gpu >> Edge(style="dotted", label="Encrypt EBS") >> kms

            gpu >> Edge(style="dashed", color="green", label="Inference response") >> lambda_router

        # EPIC: CI/CD
        with Cluster("CI / AMI Pipeline\n[EPIC: CI/CD]", graph_attr={"rank": "same"}):
            secrets   = SecretsManager("Secrets Manager\n[EPIC: CI/CD]")
            codepipe  = Codepipeline("CodePipeline")
            codebuild = Codebuild("CodeBuild >=90%\n[EPIC: CI/CD]")
            img_build = EC2ImageBuilder("Image Builder\n[EPIC: CI/CD]")
            budgets   = Budgets("AWS Budgets\n€15 warn / €20 stop")

            secrets >> Edge(label="OpenAI key") >> lambda_router
            codepipe >> codebuild
            codebuild >> Edge(label="Build AMI") >> img_build
            codebuild >> Edge(label="Deploy Lambda") >> lambda_router

        # EPIC: CostOps
        ssm = SystemsManager("SSM RunCommand\n[EPIC: CostOps]")
        cw  = Cloudwatch("CloudWatch\nmetrics + logs\n[EPIC: CostOps]")
        budgets >> Edge(style="dotted", label="Alarm -> desktop") >> desktop

        config = Node("AWS Config rules\n[EPIC: CostOps]")
        config >> Edge(style="dotted", label="Compliance") >> cw

        gpu >> ssm >> cw
        lambda_router >> cw

        # Responses
        lambda_router >> Edge(style="dashed", color="green", label="Response") >> api_gw
        api_gw >> Edge(style="dashed", color="green", label="Response") >> cf
        cf >> Edge(style="dashed", color="green", label="Response") >> desktop

        # Legend
        Blank("Legend:\nsolid=data\n-dashed green=response\n...dotted=ops/security")
