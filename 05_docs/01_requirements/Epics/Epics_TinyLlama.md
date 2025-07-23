

## **API-003 · Gateway Hardening & Per-User Throttling**

### **Context**:

The public HTTP API (`/infer`, `/stop`, `/ping`) must enforce **Cognito-JWT authentication** and protect against abuse (GUI retry loops, script attacks). Past audits flagged two risks: (1) route settings can be overwritten by stage-level imports, and (2) API Gateway’s default logging obscures the client `sub`, making forensic work tedious.

### **Acceptance Criteria**:

1. **JWT Verification**

   * Requests without `Authorization: Bearer <id token>` → **401** in ≤ 150 ms.
   * Expired or malformed tokens → **403** with body `{"error":"invalid_token"}`.
   * JWKS cached ≤ 10 min; cache-miss latency ≤ 300 ms (cold).

2. **Per-User Throttling**

   * Burst ≤ 5 req/s, rate ≤ 20 req/min **per Cognito `sub`**.
   * Exceeding limits returns **429** and header `Retry-After: 60`.
   * CloudWatch metric `ApiRateLimitBreaches` increments on every 429.

3. **Immutable Route Settings**

   * Terraform resource `aws_apigatewayv2_route_settings` applied to each route with explicit `throttling_burst_limit` and `throttling_rate_limit`.
   * A Terraform **post-apply test** (`tests/api_route_settings_test.py`, using boto3) asserts the burst/rate limits match the Terraform values.

4. **Positive & Negative Tests** (CI job `api_hardening_spec`)

   * Postman/newman collection runs:

     * valid token ✓200,
     * missing token ✓401,
     * tampered signature ✓403,
     * 6 rapid calls ✓1×429.

5. **Documentation**

   * `docs/api/jwt_auth.md` explains Cognito pool IDs, import script, and provides `curl` examples for each failure mode.

---

### **Technical Notes / Steps**:

* **Queue Configuration**:

  * Set up a **FIFO SQS Queue** for processing throttled jobs:

  ```hcl
  resource "aws_sqs_queue" "job_queue" {
    name                      = "job-queue.fifo"
    fifo_queue                = true
    content_based_deduplication = true
    visibility_timeout_seconds = 60  # Adjust based on job processing time
  }
  ```

* **API Gateway Lambda Integration**:

  * API Gateway will now integrate with Lambda to place requests into SQS.

  ```json
  {
    "QueueUrl": "${aws_sqs_queue.job_queue.url}",
    "MessageBody": "${event.body}",
    "MessageGroupId": "throttled-jobs"  # Ensures FIFO order
  }
  ```

---

## **API-004 · CORS & Structured JSON Logging**

### **Context**:

Frontend (Tkinter GUI and future mobile) is served from `localhost` and potentially file URLs; all other origins must be rejected. Audit RISK-note highlighted that default access logs are unstructured and retention unspecified.

### **Acceptance Criteria**:

1. **CORS Policy**

   * Allowed origins: `http://localhost:*` and `capacitor://*`.
   * Allowed methods: `POST, GET, OPTIONS`; headers: `Authorization, Content-Type`.
   * Pre-flight (`OPTIONS`) returns **204** under 100 ms.

2. **Structured Logging**

   * Enable JSON access logging with fields `requestId, ip, route, status, jwtSub, latencyMs, userAgent`.
   * Logs shipped to CloudWatch group `/apigw/tinyllama-access` with `retention_in_days = 30`.

3. **Cost Estimate** comment in Terraform: ≤ 100 MB/mo ≈ €0.00 (free tier); flag alert at 70 MB.

4. **Smoke Test**

   * CI sends `OPTIONS /infer` from disallowed origin → **403**.
   * Logs must contain `origin":"evil.com"` and `status":403`.

### **Technical Notes**:

* **CORS** headers remain unchanged but allow communication between API Gateway and **SQS**-integrated Lambda.

* **Structured Logging**:

  * Logs will now track SQS message statuses (sent, delivered, processed).
  * Example of SQS message log entry:

  ```json
  {
    "requestId": "abc123",
    "status": "queued",
    "timestamp": "2025-07-23T12:00:00Z",
    "queue": "job-queue.fifo"
  }
  ```

---

## **API-005 · GUI Login → Cognito OAuth**

### **Context**:

The Tkinter GUI now has a **“Login”** button (see `gui_view.py`). Pressing it must open the Cognito Hosted-UI, complete the OAuth code flow, and store the ID token in memory; no AWS keys are ever written to disk.

### **Acceptance Criteria**:

1. **Desktop Flow**

   * Button click opens system browser at `{COGNITO_DOMAIN}/oauth2/authorize?...` with `redirect_uri=http://127.0.0.1:8765/callback`.
   * Local HTTP server (embedded in `auth_controller.py`) listens once, captures `code`, exchanges for tokens via `grant_type=authorization_code`.
   * On success, AppState.auth\_status → `ok`; lamp turns green within 3 s.

2. **Token Handling**

   * Store `id_token` in memory only; **no refresh token** stored.
   * Automatically refresh by re-login when a 401 appears.

3. **Security**

   * `PKCE` (S256) required.
   * Loopback redirect uses random, non-privileged port; listener shuts down after 30 s.

4. **Tests**

   * `tests/gui/test_auth_controller.py` mocks Cognito endpoints and asserts state lamp transitions (`off→pending→ok`).
   * Integration test on CI uses headless Chrome + local Cognito stub.

5. **Docs**

   * `docs/gui/login_flow.md` includes sequence diagram and troubleshooting tips (e.g., Keychain pop-ups on macOS).

### **Technical Notes**:

* **env vars** in GUI: `COGNITO_DOMAIN`, `COGNITO_CLIENT_ID`.

* **After Login**: The system will now add the **job** to **SQS** for processing.

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(job_data),
      MessageGroupId="user-jobs"  # FIFO grouping
  )
  ```



## **LAMBDA EPIC: Lambda Job Processing with SQS**

### **Context:**

In this epic, we will replace any Redis-based job queueing with **SQS FIFO queues**. The job processing system will be restructured to use **SQS** for job state management, queuing, and communication between services (Lambda and EC2). **Lambda functions** will poll SQS queues for jobs, process them, and then delete them from the queue once processed.

---

### **Ticket: LAM-002 · SQS Enqueue with Message Attributes**

#### **Context:**

In the current system, Redis was used for job enqueueing and TTL management. With the shift to **SQS**, we need to replace Redis enqueue logic with SQS’s **`send_message`** method, making sure that the messages are ordered in **FIFO** fashion.

#### **Acceptance Criteria:**

1. **Job Enqueueing**

   * Jobs should be enqueued to **SQS FIFO queue** using the **`send_message`** method.
   * **MessageGroupId** should be used to ensure **FIFO** processing.
   * **MessageAttributes** will be used to add **job metadata** (e.g., idle time, job-specific details).

2. **TTL Management**

   * SQS’s **message retention policy** will replace Redis TTL management.
   * Messages will be deleted once successfully processed.

#### **Technical Notes**:

* **SQS Queue Configuration**:

  ```hcl
  resource "aws_sqs_queue" "job_queue" {
    name                      = "job-queue.fifo"
    fifo_queue                = true
    content_based_deduplication = true
    visibility_timeout_seconds = 60  # Adjust based on job processing time
  }
  ```

* **Lambda Job Enqueue Logic**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(job_data),
      MessageGroupId=str(uuid.uuid4()),  # Ensures FIFO ordering
      MessageAttributes={
          "IdleTime": {
              "DataType": "Number",
              "StringValue": str(idle_time)
          }
      }
  )
  ```

---

### **Ticket: LAM-003 · GPU Cold-Boot Logic with SQS**

#### **Context:**

In the previous system, Redis was used for tracking job status and triggering actions on the EC2 instance. With **SQS**, job state will be managed using **SQS message visibility** and **polling** by **Lambda**. If the EC2 instance is not running, the job will trigger a cold start.

#### **Acceptance Criteria:**

1. **EC2 Cold Start Check**

   * **Lambda** will poll **SQS** for jobs and check if the **EC2 instance** is running.
   * If the EC2 instance is stopped, Lambda will trigger the instance start.

2. **FIFO Job Processing**

   * Jobs will be processed in **FIFO order** using **SQS**.
   * Lambda will mark jobs as complete by deleting them from the queue once processed.

#### **Technical Notes**:

* **SQS Polling**:

  ```python
  sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )
  ```

* **EC2 Start Logic**:

  ```python
  ec2 = boto3.client("ec2")
  ec2.start_instances(InstanceIds=["gpu-instance-id"])
  ```

---

### **Ticket: LAM-004 · SQS Dead Letter Queue (DLQ) for Failed Jobs**

#### **Context:**

Failed jobs should be placed in a **Dead Letter Queue (DLQ)** for later inspection and reprocessing. When a job fails, it will be moved to the **DLQ**, which will allow better error handling and visibility into processing issues.

#### **Acceptance Criteria:**

1. **DLQ Configuration**

   * A **Dead Letter Queue (DLQ)** will be configured for the **SQS queue** to store failed jobs.
   * Failed jobs will be moved to the DLQ if they are not processed successfully after a configurable number of retries.

2. **Failure Notifications**

   * **CloudWatch** will trigger **SNS** notifications when jobs are moved to the DLQ.
   * The failed jobs will be monitored and tracked for reprocessing.

#### **Technical Notes**:

* **SQS DLQ Configuration**:

  ```hcl
  resource "aws_sqs_queue" "dlq_queue" {
    name                      = "failed-jobs-dlq.fifo"
    fifo_queue                = true
    content_based_deduplication = true
    message_retention_seconds = 86400  # Adjust based on retention needs
  }

  resource "aws_sqs_queue" "job_queue" {
    name                      = "job-queue.fifo"
    fifo_queue                = true
    redrive_policy = jsonencode({
      deadLetterTargetArn = aws_sqs_queue.dlq_queue.arn
      maxReceiveCount     = 3  # Retry 3 times before moving to DLQ
    })
  }
  ```

* **CloudWatch Monitoring** for DLQ:

  ```hcl
  resource "aws_cloudwatch_metric_alarm" "dlq_alarm" {
    metric_name = "NumberOfMessagesSent"
    namespace   = "AWS/SQS"
    statistic   = "Sum"
    dimensions = {
      QueueName = "failed-jobs-dlq"
    }
    threshold  = 1
    comparison = "GreaterThanThreshold"
    period     = 300
    evaluation_periods = 1
  }
  ```

---

## **SQS EPIC: SQS Job Queueing and Processing**

### **Context:**

In this epic, we will integrate **SQS** for managing job queues, replacing any previous job management systems. SQS will handle job enqueueing, visibility, and job state tracking while ensuring that jobs are processed in **FIFO order**. **Lambda** and **EC2** will consume the jobs from **SQS queues**.

---

### **Ticket: SQS-001 · SQS FIFO Job Queue Configuration**

#### **Context:**

The system needs to be configured to use **SQS FIFO queues** for job queuing and processing. FIFO queues ensure that messages are processed in the order they are received and guarantee exactly-once processing.

#### **Acceptance Criteria:**

1. **Queue Configuration**

   * Create an **SQS FIFO queue** for job management.
   * The queue should ensure **message deduplication** and **FIFO** processing.

2. **Message Retention and Visibility Timeout**

   * Set message retention policy and visibility timeout to match job processing time.

#### **Technical Notes**:

* **SQS FIFO Queue Configuration**:

  ```hcl
  resource "aws_sqs_queue" "job_queue" {
    name                      = "job-queue.fifo"
    fifo_queue                = true
    content_based_deduplication = true
    visibility_timeout_seconds = 60  # Adjust based on job processing time
  }
  ```

---

### **Ticket: SQS-002 · Job Enqueueing with SQS**

#### **Context:**

Job enqueueing will now be handled by **SQS**. Jobs will be pushed into **SQS FIFO queues** by **Lambda** or other services that generate jobs. Each job will contain relevant data, including any metadata, and will be processed in order.

#### **Acceptance Criteria:**

1. **Job Enqueueing**

   * Jobs should be enqueued into the **SQS FIFO queue** using the **send\_message** method.
   * Each job will include job metadata (e.g., idle time, processing information).

2. **MessageGroupId for FIFO Processing**

   * Use **MessageGroupId** to ensure that jobs are processed in sequence within the queue.

#### **Technical Notes**:

* **Lambda Job Enqueue Logic**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(job_data),
      MessageGroupId=str(uuid.uuid4()),  # Ensures FIFO order
      MessageAttributes={
          "IdleTime": {
              "DataType": "Number",
              "StringValue": str(idle_time)
          }
      }
  )
  ```

---

### **Ticket: SQS-003 · Job State Monitoring and Visibility**

#### **Context:**

We will track job states using **SQS message visibility**. Once a message is retrieved from the queue, it will become invisible to other consumers for a set duration (visibility timeout). This allows for better tracking of job processing states.

#### **Acceptance Criteria:**

1. **Visibility Timeout**

   * Set a visibility timeout for jobs to prevent multiple workers from processing the same job simultaneously.
   * Jobs will remain in the queue until the processing is completed.

2. **Message Deletion**

   * Once a job is processed successfully, it will be deleted from the queue.

#### **Technical Notes**:

* **SQS Visibility Timeout**:

  ```hcl
  resource "aws_sqs_queue" "job_queue" {
    name                      = "job-queue.fifo"
    fifo_queue                = true
    content_based_deduplication = true
    visibility_timeout_seconds = 60  # Adjust based on job processing time
  }
  ```

* **Lambda Polling and Message Deletion**:

  ```python
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      # Process message
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```

---

### **Ticket: SQS-004 · Dead Letter Queue (DLQ) for Failed Jobs**

#### **Context:**

Failed jobs should be placed in a **Dead Letter Queue (DLQ)** for later inspection and reprocessing. Jobs that cannot be processed successfully will be moved to the DLQ after a specified number of retries.

#### **Acceptance Criteria:**

1. **DLQ Configuration**

   * Configure a **Dead Letter Queue (DLQ)** for the **SQS queue** to store failed jobs.
   * Failed jobs will be moved to the DLQ after a configurable number of retries.

2. **Failure Notifications**

   * **CloudWatch** will trigger **SNS** notifications when jobs are moved to the DLQ.
   * The failed jobs will be monitored and tracked for reprocessing.

#### **Technical Notes**:

* **SQS DLQ Configuration**:

  ```hcl
  resource "aws_sqs_queue" "dlq_queue" {
    name                      = "failed-jobs-dlq.fifo"
    fifo_queue                = true
    content_based_deduplication = true
    message_retention_seconds = 86400  # Adjust based on retention needs
  }

  resource "aws_sqs_queue" "job_queue" {
    name                      = "job-queue.fifo"
    fifo_queue                = true
    redrive_policy = jsonencode({
      deadLetterTargetArn = aws_sqs_queue.dlq_queue.arn
      maxReceiveCount     = 3  # Retry 3 times before moving to DLQ
    })
  }
  ```

* **CloudWatch Monitoring** for DLQ:

  ```hcl
  resource "aws_cloudwatch_metric_alarm" "dlq_alarm" {
    metric_name = "NumberOfMessagesSent"
    namespace   = "AWS/SQS"
    statistic   = "Sum"
    dimensions = {
      QueueName = "failed-jobs-dlq"
    }
    threshold  = 1
    comparison = "GreaterThanThreshold"
    period     = 300
    evaluation_periods = 1
  }
  ```

---

## **EC2 EPIC: EC2 Instance Management with SQS**

### **Context:**

In this epic, we will handle EC2 instance management based on jobs queued in **SQS FIFO queues**. **Lambda** will poll **SQS** for jobs and trigger EC2 instances to start or stop based on the job data. **SQS** will manage the state and communication between Lambda and EC2 instances, ensuring jobs are processed in order.

---

### **Ticket: EC2-001 · Shape-Shifting Instance**

#### **Context:**

This ticket involves managing EC2 instances, specifically resizing them to a GPU-based instance (e.g., `g4dn.xlarge`) when needed. SQS will be used to trigger the resizing and monitor the instance status.

#### **Acceptance Criteria:**

1. **EC2 Resizing Based on Job Queue**

   * Lambda will poll **SQS** for jobs that require EC2 instance resizing.
   * **Lambda** will trigger EC2 resizing based on the job details.

2. **EC2 State Management**

   * The job will include information on whether to resize the instance or just start it based on the current instance state.

#### **Technical Notes**:

* **Lambda EC2 Resizing Logic**:

  ```python
  ec2 = boto3.client("ec2")
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      job = json.loads(message['Body'])
      instance_type = job["instance_type"]
      ec2.modify_instance_attribute(
          InstanceId=job["instance_id"],
          InstanceType={"Value": instance_type}
      )
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```

---

### **Ticket: EC2-002 · Admin Resize API**

#### **Context:**

This ticket allows administrators to manually trigger EC2 instance resizing through an API. The job data, including the target instance type, will be placed in **SQS FIFO queues** for Lambda to process.

#### **Acceptance Criteria:**

1. **Manual Instance Resizing**

   * The **admin API** will receive a request to resize EC2 instances based on the job data stored in **SQS**.
   * Lambda will process the job from SQS and perform the resize operation on the EC2 instance.

2. **Lambda Integration with SQS**

   * **Lambda** will retrieve the job from the SQS queue, modify the instance type, and return a success response.

#### **Technical Notes**:

* **API to Lambda EC2 Resize Logic**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(job_data),
      MessageGroupId="admin-resize"
  )
  ```

---

### **Ticket: EC2-003 · Idle Self-Stop Watchdog**

#### **Context:**

This ticket involves automatically stopping EC2 instances after a certain idle time if no jobs are queued in the **SQS** for processing. Lambda will monitor the **SQS queue** for activity, and if no jobs are found for a specified period, the EC2 instance will be stopped.

#### **Acceptance Criteria:**

1. **Idle Timeout Monitoring**

   * Lambda will check the **SQS queue** for jobs and stop the EC2 instance if no new jobs are found for the specified idle time.

2. **Auto-Stop EC2 Instance**

   * If the instance is idle for the specified time, Lambda will stop the EC2 instance.

#### **Technical Notes**:

* **Lambda Idle Monitoring**:

  ```python
  sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  if not response.get('Messages', []):
      ec2.stop_instances(InstanceIds=["gpu-instance-id"])
  ```

---

### **Ticket: EC2-004 · Docker Builder User-Data Bootstrap**

#### **Context:**

This ticket is for building EC2 instances that will automatically install Docker, SAM CLI, and other tools for building Lambda layers. The instance will be started by **Lambda**, with the job data managed through **SQS**.

#### **Acceptance Criteria:**

1. **EC2 Build Setup**

   * EC2 instances will be created with **user-data** scripts that set up the required environment for building Lambda layers.
   * **Lambda** will start the EC2 instance and trigger the build process.

2. **Instance Management**

   * Once the build process is complete, the EC2 instance will be stopped or terminated based on job completion.

#### **Technical Notes**:

* **EC2 Build Instance Management**:

  ```python
  ec2.run_instances(
      ImageId="ami-xxxxxxxx",
      InstanceType="t3.medium",
      UserData="file://user_data/bootstrap.sh",
      MinCount=1,
      MaxCount=1
  )
  ```


## **CI/CD EPIC: CI/CD Pipeline with SQS Integration**

### **Context:**

In this epic, we will integrate **SQS** for managing job queues in the CI/CD pipeline. Jobs such as builds, tests, and deployments will be enqueued in **SQS FIFO queues**, and the **Lambda functions** will be responsible for processing the jobs sequentially. **SQS** will ensure the correct order and management of build-related tasks.

---

### **Ticket: CI-001 · Quality Gate with SQS**

#### **Context:**

Quality checks, such as linting, unit testing, and code quality assessments, will be handled by **SQS queues**. The job data related to code quality will be placed in **SQS FIFO queues**, and **Lambda** will process the jobs sequentially.

#### **Acceptance Criteria:**

1. **Enqueue Quality Check Jobs**

   * Jobs related to quality checks (e.g., linting, unit tests) will be enqueued in the **SQS FIFO queue**.
   * **SQS send\_message** will be used for job queuing with necessary metadata (e.g., job type, status).

2. **Sequential Processing**

   * **Lambda** will process jobs sequentially from the **SQS queue**.

#### **Technical Notes**:

* **SQS Job Enqueue Logic**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(job_data),
      MessageGroupId="quality-gate"  # FIFO processing
  )
  ```

* **Lambda Processing**:

  ```python
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      # Process quality check job
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```

---

### **Ticket: CI-002 · SAM Build via SSM with SQS**

#### **Context:**

In this ticket, the EC2 instance responsible for building Lambda layers using **SAM CLI** will receive job data from an **SQS queue**. Once the job is completed, the EC2 instance will be stopped, and the result will be passed back.

#### **Acceptance Criteria:**

1. **Enqueue Build Jobs**

   * Build tasks will be enqueued in **SQS FIFO queues**.
   * **Lambda** will process the job from the queue and trigger the EC2 instance to start the build.

2. **Build Completion and Notification**

   * After the build, the EC2 instance will stop, and the results will be passed back to the queue.

#### **Technical Notes**:

* **SQS Integration with EC2 Build**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(build_data),
      MessageGroupId="sam-build"  # FIFO processing
  )
  ```

* **Lambda EC2 Start/Stop**:

  ```python
  ec2.run_instances(
      ImageId="ami-xxxxxxxx",
      InstanceType="t3.medium",
      UserData="file://user_data/bootstrap.sh",
      MinCount=1,
      MaxCount=1
  )
  ```

---

### **Ticket: CI-003 · End-to-End Smoke Test with SQS**

#### **Context:**

This ticket involves running an **end-to-end smoke test** to verify the complete pipeline. Jobs will be queued in **SQS**, and **Lambda** will be responsible for processing and verifying the test result.

#### **Acceptance Criteria:**

1. **Enqueue Test Jobs**

   * Smoke test jobs will be enqueued in the **SQS FIFO queue**.
   * **Lambda** will process each job sequentially, ensuring they are executed in order.

2. **Test Completion and Feedback**

   * After each test, the result will be checked, and the job will be removed from the queue once completed.

#### **Technical Notes**:

* **SQS Job Enqueue for Smoke Test**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(test_data),
      MessageGroupId="smoke-test"  # FIFO processing
  )
  ```

* **Lambda Smoke Test Processing**:

  ```python
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      # Execute smoke test job
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```

---

### **Ticket: CI-004 · Continuous Integration Monitoring with SQS**

#### **Context:**

Continuous integration monitoring will be done using **SQS** to queue test results, build results, and logs. The system will rely on **SQS** for managing and organizing CI task data.

#### **Acceptance Criteria:**

1. **Queue Monitoring Jobs**

   * Jobs related to build results, test results, and logs will be placed in **SQS FIFO queues** for monitoring purposes.

2. **Processing Job Results**

   * The results will be processed in sequence, and monitoring tasks will be completed in the FIFO order.

#### **Technical Notes**:

* **Queue Configuration for CI Monitoring**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(monitoring_data),
      MessageGroupId="ci-monitoring"  # FIFO processing
  )
  ```

* **Lambda Monitoring Job Processing**:

  ```python
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      # Process monitoring job results
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```
## **OPS EPIC: Cost and Operations Management with SQS**

### **Context:**

In this epic, **SQS** will be integrated for managing cost tracking and operations-related tasks. **SQS FIFO queues** will be used for job queuing, managing job results, and monitoring the cost and usage of AWS resources, ensuring efficient job processing and cost control. **Lambda functions** will poll these queues and execute the necessary actions based on the messages.

---

### **Ticket: OPS-001 · Monthly Budget Monitoring with SQS**

#### **Context:**

Budget management will now use **SQS** for tracking job costs and usage. **Lambda** will read the job details from **SQS**, calculate the job costs, and compare it with the set budget limits.

#### **Acceptance Criteria:**

1. **Track Job Costs**

   * Every job processed via **SQS** will include cost data, and **Lambda** will compute the cost based on the job's AWS resource usage.

2. **Cost Alerts**

   * **CloudWatch** will monitor **SQS usage** and trigger **SNS** notifications when the job costs exceed budget thresholds.

#### **Technical Notes**:

* **SQS Integration for Cost Tracking**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(cost_data),
      MessageGroupId="budget-tracking"  # FIFO processing
  )
  ```

* **Lambda Cost Tracking Logic**:

  ```python
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      cost_data = json.loads(message['Body'])
      job_cost = cost_data["job_cost"]
      
      # Compare job cost with budget
      if job_cost > budget_limit:
          # Trigger alert
          sns.publish(TopicArn=budget_alert_topic, Message="Cost exceeded budget")
      
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```

---

### **Ticket: OPS-002 · CloudWatch Dashboard with SQS Integration**

#### **Context:**

The CloudWatch dashboard will track and visualize job status, queue depth, and cost data via **SQS** integration. **Lambda** will consume messages from **SQS** and update CloudWatch metrics and alarms.

#### **Acceptance Criteria:**

1. **SQS Message Metrics**

   * CloudWatch will track **SQS** metrics, such as **queue length**, **message processing time**, and **message retention**.

2. **Custom Dashboards**

   * Create **CloudWatch dashboards** that visualize **SQS job metrics** like job queue depth and processing times.

#### **Technical Notes**:

* **CloudWatch Integration with SQS**:

  ```hcl
  resource "aws_cloudwatch_metric_alarm" "sqs_alarm" {
    metric_name = "ApproximateNumberOfMessagesVisible"
    namespace   = "AWS/SQS"
    statistic   = "Sum"
    dimensions = {
      QueueName = "job-queue.fifo"
    }
    threshold  = 100
    comparison = "GreaterThanThreshold"
    period     = 60
    evaluation_periods = 1
  }
  ```

* **Lambda to Update CloudWatch**:

  ```python
  cloudwatch = boto3.client('cloudwatch')
  cloudwatch.put_metric_data(
      Namespace='TinyLlama',
      MetricData=[
          {
              'MetricName': 'QueueDepth',
              'Value': queue_depth,
              'Unit': 'Count'
          }
      ]
  )
  ```

---

### **Ticket: OPS-003 · Daily Cost Summary via SNS with SQS**

#### **Context:**

Daily cost summaries will be sent via **SNS** notifications using job data from **SQS**. **Lambda** will calculate the daily cost of SQS-triggered jobs and send a summary email to stakeholders.

#### **Acceptance Criteria:**

1. **Cost Summary**

   * Every day, **Lambda** will process jobs from **SQS**, calculate the total cost, and send a **daily summary** to stakeholders via **SNS**.

2. **Cost Monitoring and Alerts**

   * **SNS** notifications will alert if job costs exceed a certain threshold (e.g., \$20/month).

#### **Technical Notes**:

* **SQS Job Cost Calculation**:

  ```python
  sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  total_cost = 0
  for message in response.get('Messages', []):
      cost_data = json.loads(message['Body'])
      total_cost += cost_data["job_cost"]
      
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )

  # Send daily summary via SNS
  sns.publish(TopicArn=daily_cost_topic, Message=f"Total Daily Cost: ${total_cost}")
  ```


## **TinyLlama EPIC: TinyLlama Job Queueing and Processing**

### **Context:**

In this epic, we will use **SQS FIFO queues** to handle the job queueing for **TinyLlama**. Jobs such as inference requests, model training, and EC2 instance management will be enqueued in **SQS**, and Lambda functions will process these jobs in a **FIFO** order. **SQS** will be responsible for ensuring jobs are executed sequentially, and job state will be managed through **SQS message visibility**.

---

### **Ticket: TL-001 · SQS Job Queue Configuration for TinyLlama**

#### **Context:**

We need to configure **SQS FIFO queues** for managing **TinyLlama** jobs. These queues will be used to enqueue jobs such as model inference requests and other job data for processing.

#### **Acceptance Criteria:**

1. **FIFO Queue Configuration**

   * Create an **SQS FIFO queue** to manage **TinyLlama** jobs.
   * The queue should support **message deduplication** and **FIFO processing**.

2. **Job Message Structure**

   * Each message will contain **job data** such as the task type (e.g., inference), job status, and necessary parameters (e.g., idle time, model details).

#### **Technical Notes**:

* **SQS FIFO Queue Configuration**:

  ```hcl
  resource "aws_sqs_queue" "tinyllama_job_queue" {
    name                      = "tinyllama-job-queue.fifo"
    fifo_queue                = true
    content_based_deduplication = true
    visibility_timeout_seconds = 60  # Adjust based on job processing time
  }
  ```

---

### **Ticket: TL-002 · Enqueue Job Requests in SQS**

#### **Context:**

Job requests such as inference requests will be enqueued in **SQS FIFO queues**. Each job will be submitted with relevant metadata (e.g., model type, input data), and **Lambda** will pick up these jobs from the queue for processing.

#### **Acceptance Criteria:**

1. **Enqueue Jobs**

   * Jobs will be enqueued in the **SQS FIFO queue** using **`send_message`** method.
   * The jobs will include metadata like model type and inference parameters.

2. **FIFO Processing**

   * Ensure jobs are processed sequentially in **FIFO** order using **MessageGroupId**.

#### **Technical Notes**:

* **Lambda Job Enqueue Logic**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(job_data),
      MessageGroupId="inference-jobs"  # FIFO processing
  )
  ```

---

### **Ticket: TL-003 · Job Processing with Lambda from SQS**

#### **Context:**

**Lambda** will process jobs sequentially from the **SQS FIFO queue**. Each job will be retrieved, processed (e.g., inference), and then deleted from the queue once it is completed.

#### **Acceptance Criteria:**

1. **Lambda Polling for Jobs**

   * **Lambda** will poll **SQS** to retrieve jobs for processing.
   * Once a job is processed, it will be deleted from the queue.

2. **Sequential Job Processing**

   * Jobs will be processed in **FIFO order**, ensuring sequential execution.

#### **Technical Notes**:

* **Lambda Polling Logic**:

  ```python
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      job_data = json.loads(message['Body'])
      # Process the job (e.g., model inference)
      
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```

---

### **Ticket: TL-004 · Dead Letter Queue (DLQ) for Failed Jobs**

#### **Context:**

Failed jobs should be moved to a **Dead Letter Queue (DLQ)** for inspection and reprocessing. When a job cannot be processed successfully, it will be moved to the DLQ after a configurable number of retries.

#### **Acceptance Criteria:**

1. **DLQ Configuration**

   * Configure a **Dead Letter Queue (DLQ)** to store failed jobs.
   * Jobs that fail to process after a set number of retries will be moved to the DLQ.

2. **Failure Notifications**

   * **CloudWatch** will monitor DLQ and send notifications when jobs are moved to DLQ.

#### **Technical Notes**:

* **DLQ Configuration**:

  ```hcl
  resource "aws_sqs_queue" "dlq_queue" {
    name                      = "failed-tinyllama-jobs-dlq.fifo"
    fifo_queue                = true
    content_based_deduplication = true
    message_retention_seconds = 86400  # Adjust based on retention needs
  }

  resource "aws_sqs_queue" "tinyllama_job_queue" {
    name                      = "tinyllama-job-queue.fifo"
    fifo_queue                = true
    redrive_policy = jsonencode({
      deadLetterTargetArn = aws_sqs_queue.dlq_queue.arn
      maxReceiveCount     = 3  # Retry 3 times before moving to DLQ
    })
  }
  ```

* **CloudWatch Monitoring for DLQ**:

  ```hcl
  resource "aws_cloudwatch_metric_alarm" "dlq_alarm" {
    metric_name = "NumberOfMessagesSent"
    namespace   = "AWS/SQS"
    statistic   = "Sum"
    dimensions = {
      QueueName = "failed-tinyllama-jobs-dlq"
    }
    threshold  = 1
    comparison = "GreaterThanThreshold"
    period     = 300
    evaluation_periods = 1
  }
  ```

## **CI/CD EPIC: Continuous Integration, Build, and Deployment with SQS**

### **Context:**

In this epic, we will integrate **SQS** for managing build, integration, and deployment jobs. Each of the build, test, and deployment tasks will be queued in **SQS FIFO queues**, ensuring that the jobs are processed sequentially. Lambda functions will process these tasks and send results back to SQS, with failure handling managed via **Dead Letter Queues (DLQs)**.

---

### **Ticket: CI-001 · Quality Gate with SQS Integration**

#### **Context:**

Quality checks, such as linting, unit testing, and code quality assessments, will be handled by **SQS queues**. The job data related to code quality will be placed in **SQS FIFO queues**, and **Lambda** will process the jobs sequentially. This ensures that code quality checks are performed in the correct order before proceeding to build or deployment.

#### **Acceptance Criteria:**

1. **Enqueue Quality Check Jobs**

   * Jobs related to quality checks (e.g., linting, unit tests) will be enqueued in **SQS FIFO queues**.
   * **SQS send\_message** will be used for job queuing with necessary metadata (e.g., job type, status).

2. **Sequential Processing**

   * **Lambda** will process jobs sequentially from the **SQS queue**.

#### **Technical Notes**:

* **SQS Job Enqueue Logic**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(job_data),
      MessageGroupId="quality-gate"  # FIFO processing
  )
  ```

* **Lambda Processing**:

  ```python
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      # Process quality check job
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```

---

### **Ticket: CI-002 · SAM Build via SSM with SQS Integration**

#### **Context:**

In this ticket, the EC2 instance responsible for building Lambda layers using **SAM CLI** will receive job data from an **SQS queue**. Once the job is completed, the EC2 instance will be stopped, and the result will be passed back to the SQS queue.

#### **Acceptance Criteria:**

1. **Enqueue Build Jobs**

   * Build tasks will be enqueued in **SQS FIFO queues**.
   * **Lambda** will process the job from the queue and trigger the EC2 instance to start the build.

2. **Build Completion and Notification**

   * After the build, the EC2 instance will stop, and the results will be passed back to the queue.

#### **Technical Notes**:

* **SQS Integration with EC2 Build**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(build_data),
      MessageGroupId="sam-build"  # FIFO processing
  )
  ```

* **Lambda EC2 Start/Stop**:

  ```python
  ec2.run_instances(
      ImageId="ami-xxxxxxxx",
      InstanceType="t3.medium",
      UserData="file://user_data/bootstrap.sh",
      MinCount=1,
      MaxCount=1
  )
  ```

---

### **Ticket: CI-003 · End-to-End Smoke Test with SQS Integration**

#### **Context:**

This ticket involves running an **end-to-end smoke test** to verify the complete pipeline. Jobs will be queued in **SQS**, and **Lambda** will be responsible for processing and verifying the test result.

#### **Acceptance Criteria:**

1. **Enqueue Test Jobs**

   * Smoke test jobs will be enqueued in the **SQS FIFO queue**.
   * **Lambda** will process each job sequentially, ensuring they are executed in order.

2. **Test Completion and Feedback**

   * After each test, the result will be checked, and the job will be removed from the queue once completed.

#### **Technical Notes**:

* **SQS Job Enqueue for Smoke Test**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(test_data),
      MessageGroupId="smoke-test"  # FIFO processing
  )
  ```

* **Lambda Smoke Test Processing**:

  ```python
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      # Execute smoke test job
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```

---

### **Ticket: CI-004 · Continuous Integration Monitoring with SQS Integration**

#### **Context:**

Continuous integration monitoring will be done using **SQS** to queue test results, build results, and logs. The system will rely on **SQS** for managing and organizing CI task data.

#### **Acceptance Criteria:**

1. **Queue Monitoring Jobs**

   * Jobs related to build results, test results, and logs will be placed in **SQS FIFO queues** for monitoring purposes.

2. **Processing Job Results**

   * The results will be processed in sequence, and monitoring tasks will be completed in the FIFO order.

#### **Technical Notes**:

* **Queue Configuration for CI Monitoring**:

  ```python
  sqs.send_message(
      QueueUrl=queue_url,
      MessageBody=json.dumps(monitoring_data),
      MessageGroupId="ci-monitoring"  # FIFO processing
  )
  ```

* **Lambda Monitoring Job Processing**:

  ```python
  response = sqs.receive_message(
      QueueUrl=queue_url,
      MaxNumberOfMessages=1,
      WaitTimeSeconds=20
  )

  for message in response.get('Messages', []):
      # Process monitoring job results
      sqs.delete_message(
          QueueUrl=queue_url,
          ReceiptHandle=message['ReceiptHandle']
      )
  ```



