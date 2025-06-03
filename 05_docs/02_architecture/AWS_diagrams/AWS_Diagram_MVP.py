from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.network import APIGateway
from diagrams.aws.security import SecretsManager
from diagrams.aws.storage import S3
from diagrams.aws.devtools import Codepipeline, Codebuild
from diagrams.aws.general import Users

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
        name="tinyllama_mvp_architecture",
        filename=f"tinyllama_mvp_architecture",
        outformat=ext,
        show=False,
        graph_attr=graph_attr,
        edge_attr=edge_attr,
        direction="LR",
    ):
        # ... your diagram code ...


        # User & Entry Point
        mobile_app = Users("Mobile App\nFlutter")

        with Cluster("API Layer"):
            api_gw = APIGateway("API Gateway")
            lambda_router = Lambda("Lambda Router")

        mobile_app >> Edge(label="HTTPS") >> api_gw >> lambda_router

        with Cluster("CI/CD Pipeline"):
            secrets = SecretsManager("Secrets Manager\nAPI & Keys")
            codepipe = Codepipeline("CodePipeline")
            codebuild = Codebuild("CodeBuild\nbuild+tests")

        codepipe >> codebuild
        secrets >> Edge(label="Get/Put") >> lambda_router
        secrets >> Edge(label="Get") >> codebuild

        # Dummy S3 storage (for future model/weights or simple data)
        s3 = S3("S3 (data or weights)")
        lambda_router >> Edge(label="Get/Put data") >> s3

        legend = Users("Legend:\nMVP components only.\nAdd more blocks as you expand.")
