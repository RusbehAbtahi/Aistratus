from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda, EC2, EC2ImageBuilder
from diagrams.aws.network import APIGateway, CloudFront
from diagrams.aws.security import Cognito, SecretsManager
from diagrams.aws.database import Elasticache
from diagrams.aws.storage import S3, EBS
from diagrams.aws.management import SystemsManager, Cloudwatch
from diagrams.aws.devtools import Codepipeline, Codebuild
from diagrams.aws.cost import Budgets
from diagrams.generic.blank import Blank

graph_attr = {"fontsize": "20", "splines": "ortho", "penwidth": "2"}
edge_attr  = {"fontsize": "16", "penwidth": "2", "color": "#333333"}

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

        # Entry (Desktop app or CLI) – generic user icon
        desktop_user = Blank("Desktop Client\n(HTTP + JWT)")

        with Cluster("Edge / API"):
            cf = CloudFront("CloudFront (optional)")
            api_gw = APIGateway("API Gateway\nHTTP API")
            cognito = Cognito("Cognito\nJWT Auth")

        desktop_user >> Edge(label="HTTPS") >> cf >> api_gw
        desktop_user >> Edge(style="dotted", label="Auth flow") >> cognito
        cognito >> Edge(style="dotted", label="Authorizer") >> api_gw

        # Core router
        lambda_router = Lambda("Lambda Router v2\n(modular providers)")
        api_gw >> lambda_router

        # Job queue
        redis = Elasticache("ElastiCache Redis\nTTL 5 min")
        lambda_router >> Edge(label="Enqueue job") >> redis

        # CI/CD
        with Cluster("CI / Image Pipeline"):
            secrets = SecretsManager("Secrets Manager")
            codepipe = Codepipeline("CodePipeline")
            codebuild = Codebuild("CodeBuild\nunit tests ≥90 %")
            img_builder = EC2ImageBuilder("EC2 Image Builder\nAMI bake")
            budgets = Budgets("AWS Budgets\n€15 warn / €20 stop")

        secrets >> lambda_router            # get OpenAI / provider keys
        secrets >> codebuild

        codepipe >> codebuild
        codebuild >> Edge(label="Build AMI") >> img_builder

        # Compute cluster
        with Cluster("Inference & Training"):

            # Inference node (hibernated)
            x1 = EC2("X1 Hibernated EC2\ng4dn/g5")
            ebs_cache = EBS("100 GB gp3 cache")
            redis >> Edge(label="Dequeue / wake") >> x1
            x1 >> Edge(style="dotted", label="RAM→EBS (hibernate)") >> ebs_cache
            x1 >> Edge(style="dashed", color="green", label="Response") >> lambda_router

            # Trainer node (ephemeral)
            y1 = EC2("Y1 Trainer EC2\np4d (ephemeral)")
            s3_models = S3("S3 tinyllama-models")
            y1 >> Edge(label="Upload new LoRA") >> s3_models
            y1 >> Edge(label="Notify rebuild") >> codepipe

        # Router response path to user (green dashed)
        lambda_router >> Edge(style="dashed", color="green", label="Response") >> api_gw
        api_gw >> Edge(style="dashed", color="green", label="Response") >> cf
        cf >> Edge(style="dashed", color="green", label="Response") >> desktop_user

        # Ops & Monitoring
        ssm = SystemsManager("SSM RunCommand")
        cloudwatch = Cloudwatch("CloudWatch\nlogs + metrics")
        sns_training = Blank("SNS training-complete")
        budgets >> Edge(style="dotted", label="Alerts") >> desktop_user

        x1 >> ssm >> cloudwatch
        lambda_router >> cloudwatch
        s3_models >> cloudwatch
        y1 >> sns_training
        sns_training >> desktop_user    # optional desktop alert

        # Legend
        legend = Blank("Legend:\nsolid = data path\n dashed green = inference response\n dotted = ops/alerts")
