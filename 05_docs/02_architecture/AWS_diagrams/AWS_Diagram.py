from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda, EC2, EC2ImageBuilder
from diagrams.aws.network import APIGateway, CloudFront
from diagrams.aws.security import Cognito, SecretsManager
from diagrams.aws.database import Elasticache
from diagrams.aws.storage import S3
from diagrams.aws.management import SystemsManager, Cloudwatch
from diagrams.aws.devtools import Codepipeline, Codebuild
from diagrams.aws.general import Users
from diagrams.aws.cost import Budgets
from diagrams.generic.blank import Blank

graph_attr = {
    "fontsize": "20",
    "splines": "ortho",
    "penwidth": "2",
    "nodesep": "1.0",
    "ranksep": "1.0"
}
edge_attr = {
    "fontsize": "16",
    "penwidth": "2",
    "fontcolor": "black",
    "color": "#333333"
}

for ext in ["png", "svg"]:
    with Diagram(
        name="tinyllama_architecture",
        filename=f"tinyllama_architecture",
        outformat=ext,
        show=False,
        graph_attr=graph_attr,
        edge_attr=edge_attr,
        direction="LR",
    ):

        # User & Entry Point
        mobile_app = Users("Mobile App\nFlutter")

        # Edge/API
        with Cluster("Edge / API"):
            cf = CloudFront("CloudFront (optional)")
            api_gw = APIGateway("API Gateway")
            cognito = Cognito("Cognito JWT Auth")
        mobile_app >> Edge(label="HTTPS") >> cf >> api_gw
        mobile_app >> Edge(style="dotted", label="Auth flow") >> cognito
        cognito >> Edge(style="dotted", label="Authorizer") >> api_gw

        lambda_router = Lambda("Lambda Router")
        api_gw >> lambda_router

        redis = Elasticache("ElastiCache (Redis)")
        lambda_router >> Edge(label="Enqueue (job)") >> redis

        # CI/CD Pipeline
        with Cluster("CI/CD Pipeline"):
            secrets = SecretsManager("Secrets Manager\nAPI & Keys")
            codepipe = Codepipeline("CodePipeline")
            codebuild = Codebuild("CodeBuild\nbuild+tests")
            img_builder = EC2ImageBuilder("EC2 Image Builder\n(AMI bake)")
            terraform = Blank("Terraform Cloud")
            ebs_snap = Blank("EBS Snapshot\n(/model + /docker_cache)")

        codepipe >> codebuild
        codebuild >> Edge(label="Build AMI") >> img_builder
        codebuild >> Edge(label="Create snapshot\n/model + /docker_cache") >> ebs_snap
        codebuild >> Edge(label="IaC plan/apply") >> terraform
        terraform >> Edge(label="Update Launch Template\nAMI & Snapshot") >> img_builder
        terraform >> Edge(label="Update Launch Template\nAMI & Snapshot") >> ebs_snap
        terraform >> Edge(label="StopInstances\n(post-deploy)", style="dotted") >> Blank("X1\nHibernated EC2 (g4dn/g5)")  # visual aid for reviewers
        secrets >> Edge(label="Get/Put") >> lambda_router
        secrets >> Edge(label="Get") >> codebuild

        # Compute: X1 (Inference), Y1 (Trainer)
        with Cluster("Compute Nodes"):
            # X1 persistent hibernating inference node
            x1 = EC2("X1\nHibernated EC2 (g4dn/g5)")
            ebs = Blank("Hibernate EBS\n100GB NVMe")
            redis >> Edge(label="Dequeue\n(wake if hibernated)") >> x1
            x1 >> Edge(label="RAM→EBS\n(hibernate)", style="dotted") >> ebs

            # Inference response path (green dashed) ALL the way back
            x1 >> Edge(label="Response", style="dashed", color="green") >> lambda_router
            lambda_router >> Edge(label="Response", style="dashed", color="green") >> api_gw
            api_gw >> Edge(label="Response", style="dashed", color="green") >> cf
            cf >> Edge(label="Response", style="dashed", color="green") >> mobile_app

            # Y1 transient strong training node
            y1 = EC2("Y1\nTraining EC2 (p4/p5, ephemeral)")
            y1 >> Edge(label="Upload new weights") >> S3("S3\n(LoRA, weights, ckpt)")
            y1 >> Edge(label="Trigger artefact rebuild") >> codepipe

        # Model Registry & Logging
        model_s3 = S3("Model Registry\nS3 + LakeFS")
        x1 << Edge(label="Copy weights on wake") >> model_s3
        ssm = SystemsManager("SSM RunCommand")
        cw = Cloudwatch("CloudWatch\nlogs + metrics")
        x1 >> ssm >> cw
        lambda_router >> cw
        budget = Budgets("AWS Budgets\n$ guardrail")
        cw >> budget

        legend = Blank(
            "Legend:\nsolid = data path\n dashed = external/optional\n dotted = Mgmt/ops\n green = response"
        )
