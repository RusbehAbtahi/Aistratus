output "queue_url" {
  description = "URL of the SQS FIFO job queue"
  value       = aws_sqs_queue.job_queue.id
}

output "queue_arn" {
  description = "ARN of the SQS FIFO job queue"
  value       = aws_sqs_queue.job_queue.arn
}
