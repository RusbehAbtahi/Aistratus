# tinyllama_architecture_intermediate.py
#
# Generates tinyllama_architecture_intermediate.{png,svg}
# Architecture covers **RQL 1 – Intermediate stage** (on‑demand GPU inference,
# GUI → API Gateway → Lambda Router → Redis → EC2, plus CI/AMI pipeline and
# basic cost‑governance).  Training EC2 + multi‑tenant extras are **not** yet
# included – they arrive in the Final stage.
# Run:  python tinyllama_architecture_intermediate.py

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

# ------------------------------------------------------------------ #
# Graph‑wide style (A4 landscape – slightly wider for readability)
graph_attr = {
    "fontsize": "18",
    "splines": "ortho",
    "penwidth": "2",
    "ranksep": "0.7",
    "nodesep": "0.8",
    "ratio": "1.7",        # widen
    "size": "14,8.3!",     # 14‑inch width, A4 height
    "pad": "0.3,0.3",
    "dpi": "300",
}
edge_attr = {"fontsize": "12", "penwidth": "2", "color": "#333333"}
# ------------------------------------------------------------------ #

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
        # 1) Desktop → Edge / API
        desktop = User("Desktop GUI\n(HTTPS + JWT)")

        with Cluster("Edge / API", graph_attr={"rank": "same"}):
            cf      = CloudFront("CloudFront\n(optional)")
            api_gw  = APIGateway("API Gateway\nHTTP API")
            cognito = Cognito("Cognito\nHosted UI + JWT")

        desktop >> Edge(label="HTTPS") >> cf >> api_gw
        desktop >> Edge(style="dotted", label="OAuth flow") >> cognito
        cognito >> Edge(style="dotted", label="Authorizer") >> api_gw

        # 2) Lambda Router & Redis Queue
        lambda_router = Lambda("Lambda Router v2")
        api_gw >> lambda_router

        redis = Elasticache("ElastiCache Redis\n(job TTL 5 min)")
        lambda_router >> Edge(label="Enqueue job") >> redis

        # 3) Inference VPC (private subnet)
        with Cluster("VPC – private subnets"):
            gpu = EC2("X1 EC2\ng4dn.xlarge\n(hibernated)")
            ebs_cache = EBS("100 GiB gp3 cache")
            redis >> Edge(label="Dequeue / wake") >> gpu
            gpu >> Edge(style="dotted", label="RAM→EBS\n(hibernate)") >> ebs_cache

            # NAT Gateway for outbound S3 / updates
            nat = NATGateway("NAT GW")
            gpu >> Edge(style="dotted", label="HTTPS egress") >> nat

            s3_models = S3("S3 tinyllama‑models")
            nat >> s3_models  # implicit outbound path

            kms = KMS("KMS CMK")
            s3_models >> Edge(style="dotted", label="Encrypt") >> kms
            gpu >> Edge(style="dotted", label="Encrypt EBS") >> kms

            # Inference result path (green dashed)
            gpu >> Edge(style="dashed", color="green", label="Inference response") >> lambda_router

        # 4) CI / AMI Pipeline
        with Cluster("CI / AMI Pipeline", graph_attr={"rank": "same"}):
            secrets    = SecretsManager("Secrets Manager")
            codepipe   = Codepipeline("CodePipeline")
            codebuild  = Codebuild("CodeBuild\nunit tests ≥90%")
            img_build  = EC2ImageBuilder("EC2 Image Builder\nAMI bake")
            budgets    = Budgets("AWS Budgets\n€15 warn / €20 stop")
            config     = Node("AWS Config\nrules")

        secrets >> Edge(label="OpenAI key") >> lambda_router
        codepipe >> codebuild
        codebuild >> Edge(label="Build AMI") >> img_build
        codebuild >> Edge(label="Deploy Lambda") >> lambda_router

        # 5) Management & Monitoring
        ssm = SystemsManager("SSM RunCommand\n(sync‑lora)")
        cw  = Cloudwatch("CloudWatch\nmetrics + logs")

        gpu >> ssm >> cw
        lambda_router >> cw

        budgets >> Edge(style="dotted", label="Alarm → desktop") >> desktop
        config >> Edge(style="dotted", label="Compliance") >> cw

        # 6) Router → user response (green dashed)
        lambda_router >> Edge(style="dashed", color="green", label="Response") >> api_gw
        api_gw >> Edge(style="dashed", color="green", label="Response") >> cf
        cf >> Edge(style="dashed", color="green", label="Response") >> desktop

        # 7) Legend (right‑most)
        Blank("Legend:\n• solid = data path\n• dashed green = inference response\n• dotted = ops / security / alerts")
