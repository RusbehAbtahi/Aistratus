# Local Project Tree

```
C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2
├── .buildspec.yml
├── conftest.py
├── lambda_entry.py
├── output.json
├── setup.py
├── sitecustomize.py
├── tl_upload_bucket_policy.json
├── tl_upload_trust.json
├── tools.py
├── terraform\10_global_backend
│   ├── .terraform
│   ├── .terraform.lock.hcl
│   ├── allow-delete-route.json
│   ├── allow-manage-router.json
│   ├── backend.auto.tfvars
│   ├── backend.tf
│   ├── ci_role.tf
│   ├── locals_ids.tf
│   ├── main.tf
│   ├── modules
│   │   ├── core
│   │   │   ├── auth
│   │   │   │   └── main.tf
│   │   │   ├── networking
│   │   │   │   └── main.tf
│   │   │   ├── security
│   │   │   └── ssm_params
│   │   │       └── main.tf
│   │   ├── observability
│   │   │   └── monitoring
│   │   │       └── main.tf
│   │   └── services
│   │       ├── apigateway
│   │       │   ├── main.tf
│   │       │   ├── outputs.tf
│   │       │   └── variables.tf
│   │       ├── compute
│   │       │   ├── main.tf
│   │       │   ├── outputs.tf
│   │       │   └── variables.tf
│   │       ├── iam_router
│   │       │   └── main.tf
│   │       └── lambda_layers
│   │           ├── main.tf
│   │           └── variables.tf
│   ├── outputs.tf
│   ├── updated-policy.json
│   └── variables.tf
├── 01_src\tinyllama
│   ├── __init__.py
│   ├── __pycache__
│   ├── gui
│   │   ├── Appendpy.py
│   │   ├── Epics1
│   │   ├── MakeTrees.py
│   │   ├── __init__.py
│   │   ├── app_state.py
│   │   ├── controllers
│   │   │   ├── __init__.py
│   │   │   ├── auth_controller.py
│   │   │   ├── cost_controller.py
│   │   │   ├── gpu_controller.py
│   │   │   └── prompt_controller.py
│   │   ├── gui_view.py
│   │   ├── main.py
│   │   └── thread_service.py
│   ├── router
│   │   ├── __pycache__
│   │   └── handler.py
│   └── utils
│       ├── __init__.py
│       ├── __pycache__
│       ├── auth.py
│       ├── jwt_tools.py
│       ├── schema.py
│       └── ssm.py
├── 01_src\lambda_layers
│   └── shared_deps
│       ├── build_layer_ci.py
│       ├── build_layer_launcher.py
├── .github
│   └── workflows
│       ├── api_ci.yml
│       ├── lam_ci.yml
│       └── router_canary.yml
├── api
│   ├── __init__.py
│   ├── __pycache__
│   ├── config.py
│   ├── routes.py
│   └── security.py
└── 02_tests
    ├── __pycache__
    ├── api
    │   ├── __pycache__
    │   ├── conftest.py
    │   ├── data
    │   │   ├── mock_jwks.json
    │   ├── postman
    │   │   ├── API-002.postman_collection.json
    │   │   ├── BACKUP_API-002.postman_collection.json
    │   │   └── tinyllama.postman_env.json
    │   ├── test_auth.py
    │   ├── test_keys.py
    │   └── utils
    ├── conftest.py
    ├── gui
    │   ├── __init__.py
    │   ├── test_app_state.py
    │   ├── test_auth_controller.py
    │   ├── test_cost_controller.py
    │   ├── test_gpu_controller.py
    │   ├── test_gui_view.py
    │   ├── test_main.py
    │   ├── test_output_pane.py
    │   ├── test_prompt_controller.py
    │   └── test_thread_service.py
    └── router
        ├── __init__.py
        ├── __pycache__
        ├── test_handler.py
        ├── test_router_contract.py
        ├── test_router_jwt.py
        └── test_router_skeleton.py
```
