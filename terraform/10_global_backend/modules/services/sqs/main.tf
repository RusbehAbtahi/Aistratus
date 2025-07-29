resource "aws_sqs_queue" "job_queue" {
  name                        = "job-queue.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 60

  tags = {
    Project   = "tinyllama"
    Env       = var.env
    ManagedBy = "terraform"
  }
}
