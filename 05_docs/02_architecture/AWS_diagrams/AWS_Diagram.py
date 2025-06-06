# tinyllama_architecture_final.py
#
# Generates tinyllama_architecture_final.{png,svg}
# Aspect-ratio tuned for A4 – run:  python tinyllama_architecture_final.py

from diagrams import Diagram, Cluster, Edge, Node
from diagrams.onprem.client import User
from diagrams.aws.network import APIGateway, CloudFront
from diagrams.aws.security import Cognito, SecretsManager, KMS
from diagrams.aws.compute import Lambda, EC2, EC2ImageBuilder
from diagrams.aws.database import Elasticache
from diagrams.aws.storage import S3, EBS
from diagrams.aws.management import SystemsManager, Cloudwatch
from diagrams.aws.devtools import Codepipeline, Codebuild
from diagrams.aws.cost import Budgets
from diagrams.aws.integration import SNS
from diagrams.generic.blank import Blank

# ------------------------------------------------------------------ #
# Graph-wide style (shrunk fonts & spacing for better A4 fit, slightly wider)
graph_attr = {
    "fontsize": "18",
    "splines": "ortho",
    "penwidth": "2",
    "ranksep": "0.7",
    "nodesep": "0.8",
    "ratio": "1.7",        # Wider than sqrt(2) to push horizontal expansion
    "size": "14,8.3!",     # Increase width to 14 inches, keep 8.3 inches height
    "pad": "0.3,0.3",
    "dpi": "300"           # Ensure high-resolution PNG output
}
edge_attr = {"fontsize": "12", "penwidth": "2", "color": "#333333"}
# ------------------------------------------------------------------ #

for fmt in ("png", "svg"):
    with Diagram(
        "tinyllama_architecture_final",
        filename="tinyllama_architecture_final",
        outformat=fmt,
        direction="LR",
        graph_attr=graph_attr,
        edge_attr=edge_attr,
        show=False,
    ):
        # ------------------------------------------------------------------ #
        # 1) Entry & Edge/API
        desktop = User("Desktop Client\n(HTTPS + JWT)")

        with Cluster("Edge / API", graph_attr={"rank": "same"}):
            cf      = CloudFront("CloudFront\n(optional)")
            api_gw  = APIGateway("API Gateway\nHTTP API")
            cognito = Cognito("Cognito\nJWT Auth")

        desktop >> Edge(label="HTTPS") >> cf >> api_gw
        desktop >> Edge(style="dotted", label="Auth flow") >> cognito
        cognito >> Edge(style="dotted", label="Authorizer") >> api_gw

        # ------------------------------------------------------------------ #
        # 2) Lambda Router & Queue
        lambda_router = Lambda("Lambda Router v2\n(modular providers)")
        api_gw >> lambda_router

        redis = Elasticache("ElastiCache Redis\nTTL 5 min")
        lambda_router >> Edge(label="Enqueue job") >> redis

        # ------------------------------------------------------------------ #
        # 3) Inference & Training VPC
        with Cluster("VPC – Private Subnets"):
            x1 = EC2("X1 Hibernated EC2\n(g4dn/g5)")
            ebs_cache = EBS("100 GB gp3 cache")
            redis >> Edge(label="Dequeue / wake") >> x1
            x1 >> Edge(style="dotted", label="RAM→EBS\n(hibernate)") >> ebs_cache

            # Insert a Blank node to push NAT Gateway to the right
            nat_spacer = Blank("")
            nat = Node("NAT Gateway\n(S3 egress)")
            nat_spacer >> nat

            y1 = EC2("Y1 Trainer EC2\np4d (ephemeral)")
            s3_models = S3("S3 tinyllama-models")
            y1 >> Edge(label="Upload LoRA") >> s3_models
            y1 >> Edge(label="Trigger CI") >> Codepipeline("CodePipeline")  # arrow only, node repeated later

            ebs_snapshot = Blank("EBS Snapshot\n(daily)")
            ebs_cache >> Edge(style="dotted", label="Backup") >> ebs_snapshot

            kms = KMS("KMS CMK")
            s3_models >> Edge(style="dotted", label="Encrypt") >> kms
            x1 >> Edge(style="dotted", label="Encrypt") >> kms
            y1 >> Edge(style="dotted", label="Encrypt") >> kms

            # Response path from inference
            x1 >> Edge(style="dashed", color="green", label="Inference response") >> lambda_router

        # ------------------------------------------------------------------ #
        # 4) CI / Image Pipeline
        with Cluster("CI / Image Pipeline", graph_attr={"rank": "same"}):
            secrets    = SecretsManager("Secrets Manager")
            codepipe   = Codepipeline("CodePipeline")
            codebuild  = Codebuild("CodeBuild\nunit tests ≥90%")
            img_build  = EC2ImageBuilder("EC2 Image Builder\nAMI bake")
            # Insert Blank to push config and budgets to the right
            ci_spacer = Blank("")
            config     = Node("AWS Config\nrules")
            budgets    = Budgets("AWS Budgets\n€15 warn / €20 stop")

        secrets >> Edge(label="Get keys") >> lambda_router
        secrets >> codebuild
        codepipe >> codebuild
        codebuild >> Edge(label="Build AMI") >> img_build
        codebuild >> Edge(label="Deploy Lambda") >> lambda_router

        # ------------------------------------------------------------------ #
        # 5) Management, Monitoring, Alerts
        ssm = SystemsManager("SSM RunCommand\n(sync-lora)")
        cw  = Cloudwatch("CloudWatch\nlogs + metrics")

        x1 >> ssm >> cw
        lambda_router >> cw
        s3_models >> cw

        sns_training = SNS("SNS training-complete")
        y1 >> sns_training
        sns_training >> Edge(label="Notify Desktop") >> desktop

        budgets >> Edge(style="dotted", label="Alarm / Slack / Desktop") >> desktop
        config >> Edge(style="dotted", label="Compliance findings") >> cw

        # ------------------------------------------------------------------ #
        # 6) Router → user response (green dashed)
        lambda_router >> Edge(style="dashed", color="green", label="Response") >> api_gw
        api_gw >> Edge(style="dashed", color="green", label="Response") >> cf
        cf >> Edge(style="dashed", color="green", label="Response") >> desktop

        # ------------------------------------------------------------------ #
        # 7) Legend
        # Insert a Blank to push the legend to the far right
        legend_spacer = Blank("")
        Blank(
            "Legend:\n"
            "• solid        = data-path\n"
            "• dashed green = inference response\n"
            "• dotted       = ops / alerts"
        )  # The Blank node itself will render the legend on the far right
